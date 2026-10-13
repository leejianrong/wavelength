"""Seat guard for LLM controllers.

The framework re-asks a seat without limit after an illegal action (fw
``Match.play_turn``), and tells it nothing about why. For an LLM psychic that
keeps sending a clue the rules reject, that is an unbounded loop of paid calls.
``GuardedSeat`` checks the clue itself, gives the model the rejection reason on
the next attempt, and after ``MAX_ATTEMPTS`` raises, which the framework turns
into a clean ``AgentTimeoutError`` (CLI exit code 3).
"""

from __future__ import annotations

from typing import Any

from agent_game_framework.core import (
    Conversable,
    ConversationInput,
    ConversationOutput,
    ConversationTurn,
    SeatController,
    SeatDecision,
    is_free_text,
)

from wavelength.clue_rules import clue_problem
from wavelength.deck import Spectrum

MAX_ATTEMPTS = 3


class ClueRejected(Exception):
    """The controller never produced a clue the rules accept."""


class GuardedSeat:
    def __init__(self, inner: SeatController[Any, Any]) -> None:
        self._inner = inner

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        if is_free_text(legal_actions) is None:
            return self._inner.decide(observation, legal_actions)
        spectrum = Spectrum(**observation["spectrum"])
        attempt_obs = observation
        problem = ""
        for _ in range(MAX_ATTEMPTS):
            decision = self._inner.decide(attempt_obs, legal_actions)
            problem = clue_problem(decision.action, spectrum) or ""
            if not problem:
                return decision
            attempt_obs = {
                **observation,
                "previous_clue_rejected": decision.action,
                "rejection_reason": problem,
            }
        raise ClueRejected(f"no acceptable clue after {MAX_ATTEMPTS} attempts; last: {problem}")


class GuardedConversableSeat(GuardedSeat):
    """``GuardedSeat`` that stays chat-capable when the wrapped seat is, so the
    framework's chat wiring still recognises it as ``Conversable``."""

    def respond(
        self, history: list[ConversationTurn], incoming: ConversationInput
    ) -> ConversationOutput:
        assert isinstance(self._inner, Conversable)
        return self._inner.respond(history, incoming)


def guard(controller: SeatController[Any, Any]) -> SeatController[Any, Any]:
    if isinstance(controller, Conversable):
        return GuardedConversableSeat(controller)
    return GuardedSeat(controller)
