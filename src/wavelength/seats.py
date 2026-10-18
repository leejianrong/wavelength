"""Seat guard for LLM controllers.

The framework re-asks a seat without limit after an illegal action (fw
``Match.play_turn``), and tells it nothing about why. For an LLM psychic that
keeps sending a clue the rules reject, that is an unbounded loop of paid calls.
``GuardedSeat`` checks the clue itself, gives the model the rejection reason on
the next attempt, and after ``MAX_ATTEMPTS`` raises, which the framework turns
into a clean ``AgentTimeoutError`` (CLI exit code 3).

A guess gets the same bound. Models often send the number as a string
(``"35"``) although the schema asks for an int; that is coerced, and any other
illegal guess is retried with the reason (built from the legal range only, so
it cannot carry the target) before raising.
"""

from __future__ import annotations

import re
from typing import Any

from agent_game_framework.core import (
    Conversable,
    ConversationInput,
    ConversationOutput,
    ConversationTurn,
    Match,
    PlayerId,
    SeatController,
    SeatDecision,
    TextTurn,
    is_free_text,
)

from wavelength.chat_guard import PSYCHIC_REFUSAL, chat_context
from wavelength.clue_rules import clue_problem
from wavelength.deck import Spectrum

MAX_ATTEMPTS = 3


_QUOTES = "\"'`“”‘’"


def normalize_clue(raw: Any) -> Any:
    """Tidy what a model wraps around a clue: surrounding whitespace and one
    layer of quote marks. Anything that is not text is returned unchanged so
    the clue rules reject it."""
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    while len(text) >= 2 and text[0] in _QUOTES and text[-1] in _QUOTES:
        text = text[1:-1].strip()
    return text


_INT_TEXT = re.compile(r"[+-]?\d+")


def normalize_guess(raw: Any) -> Any:
    """Turn what a model sends for a number into an int where that is
    unambiguous: a digit string (``"35"``, `` " 35\n"``) or an integral float
    (``35.0``). Anything else, including bools, is returned unchanged for the
    legality check to reject."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and _INT_TEXT.fullmatch(raw.strip()):
        return int(raw.strip())
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    return raw


class MoveRejected(Exception):
    """The controller never produced a move the game accepts."""


class ClueRejected(MoveRejected):
    """The controller never produced a clue the rules accept."""


class GuessRejected(MoveRejected):
    """The controller never produced a legal guess."""


class GuardedSeat:
    def __init__(self, inner: SeatController[Any, Any]) -> None:
        self._inner = inner

    def notes(self) -> dict[str, Any] | None:
        """The wrapped seat's latest working notes (``ThinkingSeat.last``), or None. Who may
        see them is the caller's call (ADR-0011)."""
        last = getattr(self._inner, "last", None)
        return last if isinstance(last, dict) else None

    def bind_steps(self, sink: Any) -> bool:
        """Hand the wrapped seat somewhere to send each needle step (V15); False when it does
        not take steps."""
        bind = getattr(self._inner, "bind_steps", None)
        if bind is None:
            return False
        bind(sink)
        return True

    def reflect(self, prompt: str) -> str:
        """One plain model call outside a move (V13's reaction after a reveal); counted by the
        wrapped seat's meter. Empty when the seat cannot converse."""
        respond = getattr(self._inner, "respond", None)
        if respond is None:
            return ""
        reply = respond([], TextTurn(text=prompt))
        return reply.text if isinstance(reply, TextTurn) else ""

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        if is_free_text(legal_actions) is None:
            return self._decide_guess(observation, legal_actions)
        spectrum = Spectrum(**observation["spectrum"])
        attempt_obs = observation
        problem = ""
        for _ in range(MAX_ATTEMPTS):
            decision = self._inner.decide(attempt_obs, legal_actions)
            clue = normalize_clue(decision.action)
            problem = clue_problem(clue, spectrum) or ""
            if not problem:
                # The psychic knows the target and the framework prints banter to
                # the guesser's terminal, so a clue turn carries none (ADR-0003).
                return SeatDecision(action=clue, banter=None)
            attempt_obs = {
                **observation,
                "previous_clue_rejected": decision.action,
                "rejection_reason": problem,
            }
        raise ClueRejected(f"no acceptable clue after {MAX_ATTEMPTS} attempts; last: {problem}")

    def _decide_guess(
        self, observation: dict[str, Any], legal_actions: list[Any]
    ) -> SeatDecision[Any]:
        if not legal_actions or not all(
            isinstance(a, int) and not isinstance(a, bool) for a in legal_actions
        ):
            return self._inner.decide(observation, legal_actions)
        reason = f"a guess must be a whole number {min(legal_actions)}-{max(legal_actions)}"
        attempt_obs = observation
        for _ in range(MAX_ATTEMPTS):
            decision = self._inner.decide(attempt_obs, legal_actions)
            guess = normalize_guess(decision.action)
            if guess in legal_actions and not isinstance(guess, bool):
                return SeatDecision(action=guess, banter=decision.banter)
            attempt_obs = {
                **observation,
                "previous_guess_rejected": decision.action,
                "rejection_reason": reason,
            }
        raise GuessRejected(f"no legal guess after {MAX_ATTEMPTS} attempts; {reason}")


class GuardedConversableSeat(GuardedSeat):
    """``GuardedSeat`` that stays chat-capable when the wrapped seat is, so the
    framework's chat wiring still recognises it as ``Conversable``.

    Once ``bind`` has told it which match and seat it is, a chat reply is given
    the game context from ``chat_guard.chat_context`` and, while the seat is
    the psychic, is refused without calling the model (ADR-0005). Unbound, it
    is a plain pass-through.
    """

    _match: Match[Any, Any, Any] | None = None
    _player: PlayerId | None = None

    def bind(self, match: Match[Any, Any, Any], player: PlayerId) -> None:
        self._match, self._player = match, player

    def respond(
        self, history: list[ConversationTurn], incoming: ConversationInput
    ) -> ConversationOutput:
        assert isinstance(self._inner, Conversable)
        if self._match is None or self._player is None:
            return self._inner.respond(history, incoming)
        context = chat_context(self._match.observation_for(self._player))
        if context is None:
            return TextTurn(text=PSYCHIC_REFUSAL)
        return self._inner.respond(history, TextTurn(text=f"{context}\n\n{incoming.text}"))


def guard(controller: SeatController[Any, Any]) -> SeatController[Any, Any]:
    if isinstance(controller, Conversable):
        return GuardedConversableSeat(controller)
    return GuardedSeat(controller)
