"""One match shown to one browser seat.

The match runs on a background thread. The human seat is a ``BrowserSeat`` that
waits for a move submitted over HTTP. Everything a browser receives is built in
``WebSession._view`` from ``Match.observation_for(seat)`` and nothing else
(ADR-0003, ADR-0006): never ``serialize``, never another seat's observation. A
view is built on the match thread, which is the only thread allowed to read
match state, then handed to subscribers as an already-encoded string.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any

from agent_game_framework.core import (
    AgentTimeoutError,
    FreeText,
    IllegalActionError,
    Match,
    PlayerId,
    SeatController,
    SeatDecision,
    is_free_text,
)

from wavelength.engine import WavelengthEngine
from wavelength.web.moves import Move, MoveRejected, parse_move

HUMAN: PlayerId = "you"
OPPONENT: PlayerId = "bot"
MAX_REFUSED_IN_A_ROW = 5


class SessionClosed(Exception):
    """The session was shut down while a seat was waiting."""


class Subscriber:
    """A browser connection's mailbox of ``(event, json)`` pairs."""

    def __init__(self, seat: PlayerId) -> None:
        self.seat = seat
        self.mailbox: queue.Queue[tuple[str, str]] = queue.Queue()

    def get(self, timeout: float) -> tuple[str, str]:
        return self.mailbox.get(timeout=timeout)


class BrowserSeat:
    """The human seat: ``decide`` publishes the view, then waits for a move."""

    def __init__(self, session: WebSession, player: PlayerId) -> None:
        self._session = session
        self._player = player

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        free_text = is_free_text(legal_actions)
        kind = "clue" if free_text is not None else "guess"
        return SeatDecision(action=self._session.wait_for_move(kind, free_text))


class DelayedSeat:
    """Waits before the wrapped seat answers, so a scripted opponent does not
    reply faster than a person can read."""

    def __init__(self, inner: SeatController[Any, Any], delay: float) -> None:
        self._inner = inner
        self._delay = delay

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        time.sleep(self._delay)
        return self._inner.decide(observation, legal_actions)


class WebSession:
    def __init__(
        self,
        opponent: SeatController[Any, Any],
        *,
        rounds: int = 6,
        seed: int = 1,
        human: PlayerId = HUMAN,
        opponent_id: PlayerId = OPPONENT,
        opponent_delay: float = 0.0,
    ) -> None:
        self.human = human
        self.seed = seed
        self._opponent_id = opponent_id
        self._lock = threading.Lock()
        self._subscribers: list[Subscriber] = []
        self._latest: dict[PlayerId, tuple[str, str]] = {}
        self._moves: queue.Queue[Move] = queue.Queue()
        self._awaiting: str | None = None
        self._limits: dict[str, int | None] | None = None
        self._refused = 0
        self._closed = threading.Event()
        seat = DelayedSeat(opponent, opponent_delay) if opponent_delay else opponent
        self.match: Match[Any, Any, Any] = Match(
            WavelengthEngine(),
            players=[human, opponent_id],
            config={"rounds": rounds, "seed": seed},
            seats={human: BrowserSeat(self, human), opponent_id: seat},
        )
        self._thread = threading.Thread(target=self._run, name="wavelength-match", daemon=True)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._closed.set()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def _run(self) -> None:
        try:
            self.match.run_to_completion(
                on_turn=self._on_turn,
                on_illegal_action=self._on_illegal,
                on_agent_error=self._on_agent_error,
            )
        except SessionClosed:
            return
        except AgentTimeoutError as exc:
            self._emit_error(f"The match stopped: {exc}")
        except Exception as exc:  # a bug must reach the player, not die silently on a thread
            self._emit_error(f"The match crashed: {exc!r}")

    # -- match-thread hooks ------------------------------------------------

    def _on_turn(self, player: PlayerId, decision: SeatDecision[Any]) -> None:
        self._refused = 0
        self._publish()

    def _on_illegal(
        self, player: PlayerId, decision: SeatDecision[Any], exc: IllegalActionError
    ) -> None:
        if player == self.human:
            with self._lock:
                self._awaiting = self.match.observation_for(self.human).get("phase")
            self._emit(self.human, "problem", {"type": "problem", "reason": str(exc)})
            return
        self._refused += 1
        if self._refused >= MAX_REFUSED_IN_A_ROW:
            raise AgentTimeoutError(f"{player} sent {self._refused} refused moves in a row: {exc}")

    def _on_agent_error(self, player: PlayerId, exc: Exception) -> None:
        if player != self.human:
            self._emit_error(f"The opponent had a problem and is trying again: {exc}")

    def wait_for_move(self, kind: str, free_text: FreeText | None) -> str | int:
        """Called on the match thread when the human is to move."""
        with self._lock:
            if free_text is not None:
                self._limits = {"max_words": free_text.max_words, "max_chars": free_text.max_chars}
            self._awaiting = kind
        self._publish()
        while True:
            try:
                move = self._moves.get(timeout=0.2)
            except queue.Empty:
                if self._closed.is_set():
                    raise SessionClosed from None
                continue
            if move.kind == kind:  # a stale double-click for an earlier turn is dropped
                with self._lock:
                    self._awaiting = None
                return move.value

    # -- what a browser may do ----------------------------------------------

    def submit(self, seat: PlayerId, payload: Any) -> None:
        """Queue a move from the browser. Raises ``MoveRejected`` with a reason a
        player can read; accepting a move changes nothing until the engine has
        judged it, and its verdict arrives as a ``state`` or ``error`` event."""
        if seat != self.human:
            raise MoveRejected("that is not your seat")
        move = parse_move(payload)
        with self._lock:
            awaiting = self._awaiting
        if awaiting != move.kind:
            raise MoveRejected(
                "it is not time to give a clue"
                if move.kind == "clue"
                else "it is not time to make a guess"
            )
        self._moves.put(move)

    def subscribe(self, seat: PlayerId) -> Subscriber:
        if seat != self.human:
            raise KeyError(seat)
        sub = Subscriber(seat)
        with self._lock:
            self._subscribers.append(sub)
            if seat in self._latest:  # a reload sees the current state at once
                sub.mailbox.put(self._latest[seat])
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    # -- views ---------------------------------------------------------------

    def _view(self, seat: PlayerId) -> dict[str, Any]:
        """The only message body a browser gets about the game: the seat's own
        observation, plus public configuration. Match thread only."""
        obs = self.match.observation_for(seat)
        phase = obs.get("phase")
        awaiting = phase if seat in obs["current_players"] and phase in ("clue", "guess") else None
        return {
            "type": "state",
            "seat": seat,
            "players": [self.human, self._opponent_id],
            "observation": obs,
            "awaiting": awaiting,
            "clue_limits": self._limits,
            "scoring": [{"within": w, "points": p} for w, p in self.match.state.bands],
        }

    def _publish(self) -> None:
        view = json.dumps(self._view(self.human), sort_keys=True)
        with self._lock:
            if self._latest.get(self.human) is not None and self._latest[self.human][1] == view:
                return
            self._latest[self.human] = ("state", view)
        self._deliver(self.human, "state", view)

    def _emit(self, seat: PlayerId, event: str, body: dict[str, Any]) -> None:
        self._deliver(seat, event, json.dumps(body, sort_keys=True))

    def _emit_error(self, reason: str) -> None:
        self._emit(self.human, "problem", {"type": "problem", "reason": reason})

    def _deliver(self, seat: PlayerId, event: str, data: str) -> None:
        with self._lock:
            targets = [s for s in self._subscribers if s.seat == seat]
        for sub in targets:
            sub.mailbox.put((event, data))
