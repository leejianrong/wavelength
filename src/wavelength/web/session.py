"""One match shown to the browser: a human playing, or a spectator watching.

The match runs on a background thread (the framework's ``LiveMatch``, which also
carries chat). A human seat is a ``BrowserSeat`` that waits for a move submitted
over HTTP. Everything a browser receives is built in ``WebSession._render`` from
``Match.observation_for`` snapshots and nothing else (ADR-0003, ADR-0006): never
``serialize``, and never raw exception text, which can hold a model's output.

Snapshots are taken on the match thread, the only thread allowed to read match
state, and cached; a peek toggle re-renders from the cache without touching the
match. A spectator's default view is the *guesser's* observation, so the target
stays hidden until the reveal; peek swaps in the psychic's, and is refused
whenever a human is seated (a human guesser must never be handed the target).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

from agent_game_framework.core import (
    AgentTimeoutError,
    Conversable,
    FreeText,
    IllegalActionError,
    LiveMatch,
    PlayerId,
    SeatController,
    SeatDecision,
    TextTurn,
    is_free_text,
)

from wavelength.cli import BoundMatch
from wavelength.engine import WavelengthEngine
from wavelength.eval import CallCapExceeded, Meter
from wavelength.web.broadcast import Broadcaster
from wavelength.web.moves import Move, MoveRejected, parse_move

log = logging.getLogger("wavelength.web")

MAX_REFUSED_IN_A_ROW = 5
MAX_CHAT_CHARS = 500
MAX_TALK_ENTRIES = 60


class SessionClosed(Exception):
    """The session was shut down while a seat was waiting."""


class BrowserSeat:
    """The human seat: ``decide`` publishes the view, then waits for a move."""

    def __init__(self, session: WebSession) -> None:
        self._session = session

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
        players: list[PlayerId],
        controllers: dict[PlayerId, SeatController[Any, Any]],
        *,
        broadcaster: Broadcaster,
        human: PlayerId | None = None,
        names: dict[PlayerId, str] | None = None,
        kinds: dict[PlayerId, str] | None = None,
        rounds: int = 6,
        seed: int = 1,
        meter: Meter | None = None,
    ) -> None:
        self.players = players
        self.human = human
        self.seed = seed
        self.names = names or {p: p for p in players}
        self.kinds = kinds or {}
        self._broadcaster = broadcaster
        self._meter = meter
        self._lock = threading.Lock()
        self._moves: queue.Queue[Move] = queue.Queue()
        self._awaiting: str | None = None
        self._limits: dict[str, int | None] | None = None
        self._snapshot: dict[PlayerId, dict[str, Any]] = {}
        self._scoring: list[dict[str, int]] = []
        self._peek = False
        self._talk: list[dict[str, Any]] = []
        self._refused = 0
        self._closed = threading.Event()
        self._finished = threading.Event()
        seats: dict[PlayerId, SeatController[Any, Any]] = dict(controllers)
        if human is not None:
            seats[human] = BrowserSeat(self)
        self.match = BoundMatch(
            WavelengthEngine(), players, {"rounds": rounds, "seed": seed}, seats
        )
        self._chattable: dict[PlayerId, Conversable] = {
            p: s for p, s in seats.items() if isinstance(s, Conversable)
        }
        self._live: LiveMatch[Any, Any, Any] = LiveMatch(
            self.match,
            self._chattable,
            on_turn=self._on_turn,
            on_illegal_action=self._on_illegal,
            on_agent_error=self._on_agent_error,
        )
        self._watcher = threading.Thread(target=self._watch, name="wavelength-watch", daemon=True)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._publish()  # before any thread runs, so the page sees the first round at once
        self._live.start()
        self._watcher.start()

    def close(self) -> None:
        self._closed.set()

    def join(self, timeout: float | None = None) -> None:
        self._watcher.join(timeout)

    def is_active(self) -> bool:
        return not self._finished.is_set() and not self._closed.is_set()

    def _watch(self) -> None:
        try:
            self._live.join()
        except BaseException as exc:  # noqa: BLE001 - nothing may escape a thread unreported
            if self._closed.is_set():
                return  # stopped on purpose; the exception is just the seats unwinding
            log.warning("match stopped: %r", exc, exc_info=True)  # details stay in the server log
            capped = self._meter is not None and self._meter.capped
            if capped:
                self._problem("The call limit for this match was reached, so it stopped.")
            elif isinstance(exc, AgentTimeoutError):
                self._problem("A player did not respond, so the match stopped.")
            else:
                self._problem("The match crashed. Details are in the server log.")
        finally:
            self._finished.set()

    # -- match-thread hooks ------------------------------------------------

    def _on_turn(self, player: PlayerId, decision: SeatDecision[Any]) -> None:
        if self._closed.is_set():
            raise SessionClosed
        self._refused = 0
        # Banter belongs to a guess. A clue turn carries none (GuardedSeat drops it, and the
        # psychic knows the target), so refuse it here as well: the type of the action decides.
        banter = decision.banter
        if isinstance(decision.action, int) and not isinstance(decision.action, bool) and banter:
            self._add_talk(player, banter, "banter")
        self._publish()

    def _on_illegal(
        self, player: PlayerId, decision: SeatDecision[Any], exc: IllegalActionError
    ) -> None:
        if player == self.human:
            with self._lock:
                self._awaiting = self.match.observation_for(player).get("phase")
            # The engine's own refusal (a clue rule, the dial range): safe by construction.
            self._problem(str(exc))
            return
        self._refused += 1
        log.warning("%s sent a refused move: %s", player, exc)
        if self._refused >= MAX_REFUSED_IN_A_ROW:
            raise AgentTimeoutError(f"{player} sent {self._refused} refused moves in a row")

    def _on_agent_error(self, player: PlayerId, exc: Exception) -> None:
        if self._closed.is_set():
            return  # a stopped match unwinding, not a failure
        log.warning("%s failed once and is being retried: %r", player, exc)

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

    def submit(self, payload: Any) -> None:
        """Queue a move from the browser. Raises ``MoveRejected`` with a reason a player can
        read; the engine's verdict arrives as a ``state`` or ``problem`` event."""
        if self.human is None:
            raise MoveRejected("there is no human player in this match")
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

    def set_peek(self, on: bool) -> None:
        if self.human is not None:
            raise MoveRejected("peeking is only for matches with no human player")
        self._peek = bool(on)
        self._emit_view()

    def chat(self, text: str) -> None:
        """Say something to the AI partner and wait for its reply (blocks on a model call).
        A partner that is the psychic of this round answers with a fixed refusal and no
        model call (``GuardedConversableSeat``, ADR-0005)."""
        target = self._chat_target()
        if self.human is None or target is None:
            raise MoveRejected("there is nobody here to chat with")
        text = text.strip()
        if not text or len(text) > MAX_CHAT_CHARS:
            raise MoveRejected(f"say something of 1 to {MAX_CHAT_CHARS} characters")
        self._add_talk(self.human, text, "chat")
        try:
            reply = self._live.send_chat(target, text)
        except CallCapExceeded:
            raise MoveRejected("the call limit for this match was reached") from None
        except Exception as exc:  # a model or network failure must not reveal its text
            log.warning("chat with %s failed: %r", target, exc)
            raise MoveRejected("the AI could not answer right now") from None
        self._add_talk(target, reply.text if isinstance(reply, TextTurn) else "…", "chat")

    def _chat_target(self) -> PlayerId | None:
        if self.human is None:
            return None
        others = [p for p in self.players if p != self.human and p in self._chattable]
        return others[0] if others else None

    # -- views ---------------------------------------------------------------

    def _publish(self) -> None:
        """Match thread: snapshot what the viewer may be shown, then send it."""
        ids = [self.human] if self.human is not None else self.players
        snapshot = {p: self.match.observation_for(p) for p in ids}
        scoring = [{"within": w, "points": pts} for w, pts in self.match.state.bands]
        with self._lock:
            self._snapshot = snapshot
            self._scoring = scoring
        self._emit_view()

    def _emit_view(self) -> None:
        if self._closed.is_set():
            return  # a stopped match must not repaint the page over the start screen
        with self._lock:
            snapshot, scoring = self._snapshot, self._scoring
            awaiting_now, limits, peek = self._awaiting, self._limits, self._peek
        if not snapshot:
            return
        seat = self._viewed_seat(snapshot, peek)
        obs = snapshot[seat]
        phase = obs.get("phase")
        awaiting = awaiting_now if self.human is not None and phase is not None else None
        self._broadcaster.emit(
            "state",
            {
                "type": "state",
                "seat": seat,
                "players": self.players,
                "names": self.names,
                "kinds": self.kinds,
                "viewer": {
                    "mode": "player" if self.human is not None else "spectator",
                    "peek": peek and self.human is None,
                    "peek_allowed": self.human is None,
                },
                "observation": obs,
                "awaiting": awaiting,
                "clue_limits": limits,
                "scoring": scoring,
                "chat_with": self._chat_target(),
            },
            remember=True,
        )

    def _viewed_seat(self, snapshot: dict[PlayerId, dict[str, Any]], peek: bool) -> PlayerId:
        """The one seat whose observation goes out. A human sees their own. A spectator
        sees the guesser's, or, with peek on, the psychic's; both come from the engine."""
        if self.human is not None:
            return self.human
        roles = {p: o.get("role") for p, o in snapshot.items()}
        wanted = "psychic" if peek else "guesser"
        return next((p for p, r in roles.items() if r == wanted), self.players[0])

    # -- talk and problems -----------------------------------------------------

    def _add_talk(self, seat: PlayerId, text: str, kind: str) -> None:
        if self._closed.is_set():
            return
        entry = {
            "seat": seat,
            "text": text.strip()[:400],
            "kind": kind,
            "round": self._snapshot.get(self.human or self.players[0], {}).get("round"),
        }
        with self._lock:
            self._talk = [*self._talk, entry][-MAX_TALK_ENTRIES:]
            messages = list(self._talk)
        self._broadcaster.emit("talk", {"type": "talk", "messages": messages}, remember=True)

    def _problem(self, reason: str) -> None:
        self._broadcaster.emit("problem", {"type": "problem", "reason": reason})
