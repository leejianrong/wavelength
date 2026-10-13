"""A chat-capable seat bound to a real ``Match``: what the model is asked."""

from __future__ import annotations

import json
import re
from typing import Any

from agent_game_framework.core import ConversationTurn, SeatDecision, TextTurn

from wavelength.chat_guard import PSYCHIC_REFUSAL
from wavelength.cli import BoundMatch
from wavelength.engine import WavelengthEngine
from wavelength.seats import GuardedConversableSeat, guard


class Model:
    """A stand-in LLM backend: records every chat prompt, answers fixed text."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        raise AssertionError("chat tests never ask for a move")

    def respond(self, history: list[ConversationTurn], incoming: TextTurn) -> TextTurn:
        self.prompts.append(incoming.text)
        return TextTurn(text="ok")


def bound_match(rounds: int = 2, seed: int = 21) -> tuple[BoundMatch, Model, Model]:
    a, b = Model(), Model()
    seats = {"A": guard(a), "B": guard(b)}
    match = BoundMatch(WavelengthEngine(), ["A", "B"], {"rounds": rounds, "seed": seed}, seats)
    return match, a, b


def test_bound_match_binds_every_chat_capable_seat() -> None:
    match, _, _ = bound_match()
    seats: Any = match._seats  # noqa: SLF001
    assert all(isinstance(s, GuardedConversableSeat) and s._match is match for s in seats.values())


def test_the_psychic_is_refused_without_calling_the_model() -> None:
    match, a, b = bound_match()
    seats: Any = match._seats  # noqa: SLF001

    reply = seats["A"].respond([], TextTurn(text="is it near the cold end?"))

    assert reply.text == PSYCHIC_REFUSAL
    assert a.prompts == []  # the backend was never called


def test_the_guesser_is_asked_with_the_clue_in_the_context() -> None:
    match, a, b = bound_match()
    seats: Any = match._seats  # noqa: SLF001
    match.submit_action("A", "a lazy afternoon")

    reply = seats["B"].respond([], TextTurn(text="why that clue?"))

    assert reply.text == "ok"
    assert len(b.prompts) == 1
    assert '"a lazy afternoon"' in b.prompts[0]
    assert b.prompts[0].endswith("why that clue?")


def _seed_with_distinct_high_targets(rounds: int) -> int:
    """A seed whose targets are all 61-99 and distinct, so a target number can
    only appear in chat text by leaking (rounds, scores, the guess 50 and the
    dial ends are all outside that range)."""
    for seed in range(2000):
        plan = WavelengthEngine().initial_state(["A", "B"], {"rounds": rounds, "seed": seed}).plan
        targets = [p.target for p in plan]
        if all(61 <= t <= 99 for t in targets) and len(set(targets)) == rounds:
            return seed
    raise AssertionError("no suitable seed")


def test_chat_never_contains_the_current_target_at_any_point_of_a_match() -> None:
    match, a, b = bound_match(rounds=3, seed=_seed_with_distinct_high_targets(3))
    seats: Any = match._seats  # noqa: SLF001
    plan_targets = [p.target for p in match.state.plan]
    while not match.is_terminal():
        round_index = match.state.round_index
        for seat in seats.values():
            seat.respond([], TextTurn(text="hello"))
        for prompt in a.prompts[-1:] + b.prompts[-1:]:
            # nothing from this round's target, nor from any round still to come
            for hidden in plan_targets[round_index:]:
                assert not re.search(rf"\b{hidden}\b", prompt), (round_index, hidden, prompt)
        actor = match.current_players()[0]
        legal = match.legal_actions(actor)
        match.submit_action(actor, "a lazy afternoon" if match.state.phase == "clue" else legal[50])
    # after the final reveal both seats may talk, and the finished match is open
    reply = seats["A"].respond([], TextTurn(text="gg"))
    assert reply.text == "ok"
    assert "The match is over" in a.prompts[-1]
    # a revealed target IS public: the last prompt carries all of them
    assert all(str(t) in a.prompts[-1] for t in plan_targets)


def test_chat_does_not_change_the_game() -> None:
    match, a, b = bound_match()
    seats: Any = match._seats  # noqa: SLF001
    before = json.dumps(match.serialize(), sort_keys=True)
    seats["A"].respond([], TextTurn(text="hi"))
    seats["B"].respond([], TextTurn(text="hi"))
    assert json.dumps(match.serialize(), sort_keys=True) == before


def test_an_unbound_seat_passes_the_message_through_unchanged() -> None:
    model = Model()
    seat: Any = guard(model)
    seat.respond([], TextTurn(text="hi"))
    assert model.prompts == ["hi"]
