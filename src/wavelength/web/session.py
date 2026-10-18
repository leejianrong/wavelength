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
from collections.abc import Callable
from functools import partial
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
from wavelength.needle import DIAL_MAX, DIAL_MIN, public_thoughts, walk
from wavelength.needle_seat import Step
from wavelength.prompts import MAX_NOTES_CHARS, reaction_line, reaction_prompt
from wavelength.voice import Line, VoiceTap
from wavelength.web.broadcast import Broadcaster
from wavelength.web.moves import Move, MoveRejected, parse_move

log = logging.getLogger("wavelength.web")

MAX_REFUSED_IN_A_ROW = 5
MAX_CHAT_CHARS = 500
MAX_TALK_ENTRIES = 60
MAX_STEP_LINES = 6  # the running list of a guesser's steps kept for a page
DRAFT_GAP = 0.1  # seconds; a human's needle drafts closer together than this are dropped


VoiceConnect = Callable[
    [list[PlayerId], dict[PlayerId, str], Callable[[Line | None], None], Callable[[str], None]],
    VoiceTap,
]


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
        voice_hub: str | None = None,
        voice_connect: VoiceConnect | None = None,
        voices: dict[PlayerId, str] | None = None,
        walk_pause: float = 0.0,
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
        self._voice_hub = voice_hub
        self._voice_connect = voice_connect
        self._voices = voices or {}
        self._voice_seats: list[str | None] | None = None
        self._voice: VoiceTap | None = None
        self._voice_status = "none" if voice_connect is None else "off"
        self._voice_line: Line | None = None
        self._walk_pause = walk_pause
        self._last_draft = 0.0
        self._step_round: Any = None
        self._step_lines: list[str] = []
        self._closed = threading.Event()
        self._finished = threading.Event()
        seats: dict[PlayerId, SeatController[Any, Any]] = dict(controllers)
        if human is not None:
            seats[human] = BrowserSeat(self)
        self._seats = seats
        self.match = BoundMatch(
            WavelengthEngine(), players, {"rounds": rounds, "seed": seed}, seats
        )
        # A guesser that works the needle itself (ADR-0012) sends its steps as they happen.
        self._stepping: set[PlayerId] = set()
        for pid, seat in seats.items():
            bind = getattr(seat, "bind_steps", None)
            if callable(bind) and bind(partial(self._on_step, pid)):
                self._stepping.add(pid)
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
        if self._voice_connect is not None:
            self._voice = self._voice_connect(
                self.players, self._voices, self._on_voice_line, self._on_voice_status
            )
            self._voice_seats = [self._voice.personas.get(p) for p in self.players]
            # After the personas are known, so the page frames the right avatars.
            self._on_voice_status("on" if self._voice.active else "off")
        self._publish()  # before any thread runs, so the page sees the first round at once
        self._voice_clue_turn()
        self._live.start()
        self._watcher.start()

    def close(self) -> None:
        self._closed.set()
        if self._voice is not None:
            self._voice.close()

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
        is_guess = isinstance(decision.action, int) and not isinstance(decision.action, bool)
        stepped = is_guess and player in self._stepping  # its needle is already on show
        if not stepped:
            self._emit_draft(player, None)  # a new turn starts with no needle on show
        if is_guess and self.kinds.get(player) == "llm" and not stepped:
            self._show_guess_thinking(player, int(decision.action))
        self._voice_turn(player, decision)
        # Banter belongs to a guess. A clue turn carries none (GuardedSeat drops it, and the
        # psychic knows the target), so refuse it here as well: the type of the action decides.
        banter = decision.banter
        if isinstance(decision.action, int) and not isinstance(decision.action, bool) and banter:
            self._add_talk(player, banter, "banter")
        self._publish()
        if is_guess:
            self._voice_after_reveal()
            self._psychic_reacts()

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

    def draft(self, value: Any) -> None:
        """A human guesser's tentative needle position, shown to the page and nowhere else: it
        is a public number the guesser chose, never an action and never given to a seat
        (ADR-0011). Drafts closer together than ``DRAFT_GAP`` are dropped without an error."""
        if self.human is None:
            raise MoveRejected("there is no human player in this match")
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not DIAL_MIN <= value <= DIAL_MAX
        ):
            raise MoveRejected(f"a needle position is a whole number {DIAL_MIN}-{DIAL_MAX}")
        with self._lock:
            awaiting = self._awaiting
            if awaiting == "guess":
                now = time.monotonic()
                if now - self._last_draft < DRAFT_GAP:
                    return
                self._last_draft = now
        if awaiting != "guess":
            raise MoveRejected("it is not time to move the needle")
        self._emit_draft(self.human, value)

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
        # A psychic's reply is the fixed refusal, not something to say aloud.
        if self._voice is not None and isinstance(reply, TextTurn) and self._partner_is_guesser():
            self._voice.reply(target, reply.text, kind="table_talk")

    def _chat_target(self) -> PlayerId | None:
        if self.human is None:
            return None
        others = [p for p in self.players if p != self.human and p in self._chattable]
        return others[0] if others else None

    def _partner_is_guesser(self) -> bool:
        with self._lock:
            obs = self._snapshot.get(self.human or "", {})
        return obs.get("role") == "psychic"

    # -- the thinking people may watch (ADR-0011) -----------------------------

    def _emit_draft(self, seat: PlayerId, value: int | None, final: bool = False) -> None:
        if self._closed.is_set():
            return
        self._broadcaster.emit(
            "draft",
            {"type": "draft", "seat": seat, "value": value, "final": final},
            remember=True,
        )

    def _notes_of(self, player: PlayerId) -> dict[str, Any] | None:
        seat = self._seats.get(player)
        notes = getattr(seat, "notes", None)
        return notes() if callable(notes) else None

    def _show_guess_thinking(self, player: PlayerId, guess: int) -> None:
        """Match thread, an AI guesser has decided but the page has not seen the reveal: show its
        thoughts, then walk the needle to the guess and lock it. A guesser's notes are built from
        the clue and the history only, so they are public; the role is decided by the type of the
        move, as for banter. Nothing here reads a psychic's notes."""
        voice = self._voice
        if voice is not None:
            voice.wait()  # the clue is over before the guesser talks
        notes = self._notes_of(player)
        text = public_thoughts(notes["text"]) if notes and notes.get("role") == "guesser" else ""
        round_no = self.match.observation_for(player).get("round")
        if text:
            self._emit_thinking(player, round_no, [text])
            if voice is not None:
                voice.reply(player, text, kind="banter")
                voice.wait()
        for value in walk(guess, int(round_no or 0), self.seed):
            self._emit_draft(player, value)
            self._pause()
        self._emit_draft(player, guess, final=True)
        self._pause()

    def _emit_thinking(self, player: PlayerId, round_no: Any, lines: list[str]) -> None:
        self._broadcaster.emit(
            "thinking",
            {
                "type": "thinking",
                "seat": player,
                "round": round_no,
                "text": lines[-1],
                "steps": lines,
            },
            remember=True,
        )

    def _on_step(self, player: PlayerId, step: Step) -> None:
        """Match thread, inside an AI guesser's move: one step of it working the needle. Public by
        construction (its prompt held the guesser's own allow-list only). The needle moves, the
        line is shown and spoken, and the next model call waits until it has been."""
        if self._closed.is_set():
            raise SessionClosed
        voice = self._voice
        if voice is not None and step.index == 1:
            voice.wait()  # the clue is over before the guesser talks
        round_no = self.match.observation_for(player).get("round")
        if round_no != self._step_round:
            self._step_round, self._step_lines = round_no, []
        self._emit_draft(player, step.needle, final=step.final)
        if step.say:
            self._step_lines = [*self._step_lines, step.say][-MAX_STEP_LINES:]
            self._emit_thinking(player, round_no, self._step_lines)
            if voice is not None:
                voice.reply(player, step.say, kind="banter")
                voice.wait()
                return
        self._pause()

    def _pause(self) -> None:
        if self._walk_pause and self._closed.wait(self._walk_pause):
            raise SessionClosed

    def _psychic_reacts(self) -> None:
        """Match thread, after the reveal is on every page: an AI psychic reacts once. The target
        is public now, so its own notes may be released with the reaction, from here only.
        The call goes through the seat's meter; a failure leaves the silent face."""
        history = self.match.observation_for(self.players[0]).get("history") or []
        if not history:
            return
        last = history[-1]
        psychic = last["psychic"]
        if self.kinds.get(psychic) != "llm" or self._closed.is_set():
            return
        seat = self._seats.get(psychic)
        reflect = getattr(seat, "reflect", None)
        if not callable(reflect):
            return
        notes = self._notes_of(psychic)
        held = notes["text"] if notes and notes.get("role") == "psychic" else None
        line = ""
        try:
            line = reaction_line(reflect(reaction_prompt(last, held)))
        except CallCapExceeded:
            log.warning("no reaction from %s: the call limit was reached", psychic)
        except Exception as exc:  # noqa: BLE001 - the silent face stands in
            log.warning("%s could not react: %r", psychic, exc)
        if self._closed.is_set() or not (line or held):
            return
        self._broadcaster.emit(
            "reaction",
            {
                "type": "reaction",
                "seat": psychic,
                "round": last["round"],
                "text": line or None,
                "notes": held[:MAX_NOTES_CHARS] if held else None,
            },
            remember=True,
        )
        if line and self._voice is not None:
            self._voice.reply(psychic, line, kind="banter")
            self._voice.wait()

    # -- voice ---------------------------------------------------------------
    # Only text the page may already show (a clue, a guess's banter, a chat reply) and the
    # round's public points go to the tap. It is never given an observation.

    def _roles(self) -> dict[PlayerId, str | None]:
        return {p: self.match.observation_for(p).get("role") for p in self.players}

    def _voice_clue_turn(self) -> None:
        """The next psychic starts thinking."""
        if self._voice is None:
            return
        for p, role in self._roles().items():
            if role == "psychic":
                self._voice.thinking(p)

    def _voice_turn(self, player: PlayerId, decision: SeatDecision[Any]) -> None:
        """Match thread, before the move is shown: speak it, and hold the reveal back until the
        lines before it are over (or the tap's timeout), so the page does not show the result
        while the clue is still being said."""
        voice = self._voice
        if voice is None:
            return
        action = decision.action
        if isinstance(action, str):  # a clue
            voice.clue(player, action)
            other = next((p for p in self.players if p != player), None)
            if other is not None:
                voice.thinking(other)
            return
        voice.wait()  # the clue is over
        if decision.banter:
            voice.reply(player, decision.banter, kind="banter")
            voice.wait()

    def _voice_after_reveal(self) -> None:
        voice = self._voice
        obs = self.match.observation_for(self.players[0])
        history = obs.get("history") or []
        if voice is None or not history:
            return
        last = history[-1]
        best = max((points for _within, points in self.match.state.bands), default=0)
        psychic = last["psychic"]
        guesser = next((p for p in self.players if p != psychic), psychic)
        voice.reveal(guesser, psychic, int(last["points"]), best)
        if obs.get("phase") is not None:
            self._voice_clue_turn()

    def _on_voice_line(self, line: Line | None) -> None:
        self._voice_line = line
        self._emit_voice()

    def _on_voice_status(self, status: str) -> None:
        self._voice_status = status
        self._emit_voice()

    def _emit_voice(self) -> None:
        if self._closed.is_set():
            return
        self._broadcaster.emit(
            "voice",
            {
                "type": "voice",
                "status": self._voice_status,
                "line": self._voice_line,
                "seats": self._voice_seats,
            },
            remember=True,
        )

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
                "voice_hub": self._voice_hub,
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
