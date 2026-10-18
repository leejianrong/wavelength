"""Players that think first (V12): the notes call, its metering, and what it may know."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agent_game_framework.core import AgentTimeoutError, Match, SeatDecision, TextTurn, is_free_text

from wavelength.engine import WavelengthEngine
from wavelength.eval import Meter, metered
from wavelength.prompts import GUESSER_CHECKLIST, PSYCHIC_CHECKLIST, thinking_context
from wavelength.seats import guard
from wavelength.thinking import ThinkingSeat

CLUE = "a lazy afternoon"


class FakeBackend:
    """A stand-in model: records every prompt it is sent, writes notes that name what it saw."""

    def __init__(self, name: str, fail_notes: bool = False) -> None:
        self.name = name
        self.fail_notes = fail_notes
        self.calls: list[tuple[str, str]] = []  # ("respond" | "decide", everything it was shown)

    def respond(self, history: Any, incoming: Any) -> TextTurn:
        self.calls.append(("respond", incoming.text))
        if self.fail_notes:
            raise RuntimeError("the model is down")
        return TextTurn(text=f"NOTES-{self.name} I will go with it")

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        self.calls.append(("decide", json.dumps(observation)))
        return SeatDecision(action=CLUE if is_free_text(legal_actions) else 40, banter="ok")


def seat(backend: FakeBackend, meter: Meter) -> Any:
    return guard(ThinkingSeat(metered(backend, meter)))


def play(rounds: int, a: FakeBackend, b: FakeBackend, meter: Meter | None = None) -> Meter:
    meter = meter or Meter()
    match: Match[Any, Any, Any] = Match(
        WavelengthEngine(),
        players=["a", "b"],
        config={"rounds": rounds, "seed": 5},
        seats={"a": seat(a, meter), "b": seat(b, meter)},
    )
    match.run_to_completion()
    return meter


def test_each_move_is_notes_then_the_move_with_the_notes_in_the_instructions() -> None:
    a, b = FakeBackend("a"), FakeBackend("b")
    meter = play(2, a, b)
    for backend in (a, b):
        kinds = [k for k, _ in backend.calls]
        assert kinds == ["respond", "decide"] * (len(kinds) // 2)
    # The move call was shown the notes the same model had just written.
    decide = next(text for k, text in a.calls if k == "decide")
    assert "NOTES-a" in decide
    assert meter.calls == len(a.calls) + len(b.calls)  # both kinds of call are counted
    assert meter.clue_calls == 2 and meter.guess_calls == 2


def test_the_checklists_are_what_the_model_is_asked_to_follow() -> None:
    a, b = FakeBackend("a"), FakeBackend("b")
    play(1, a, b)
    first = next(text for k, text in a.calls if k == "respond")  # a is the psychic of round 1
    assert first.startswith(PSYCHIC_CHECKLIST)
    second = next(text for k, text in b.calls if k == "respond")
    assert second.startswith(GUESSER_CHECKLIST)


def test_a_psychics_notes_never_reach_the_guesser_and_the_guessers_prompt_has_no_target() -> None:
    a, b = FakeBackend("a"), FakeBackend("b")
    play(4, a, b)
    # a and b swap roles every round; whichever was the guesser must never be shown the other's
    # notes, and a guesser's own situation has no target.
    for backend, other in ((a, "NOTES-b"), (b, "NOTES-a")):
        assert all(other not in text for _, text in backend.calls)
    for backend in (a, b):
        for kind, text in backend.calls:
            if kind == "respond" and text.startswith(GUESSER_CHECKLIST):
                situation = json.loads(text.split("The situation:\n", 1)[1])
                assert "target" not in situation


def test_the_thinking_context_for_a_guesser_is_built_from_an_allow_list() -> None:
    obs = {
        "round": 2,
        "rounds": 6,
        "spectrum": {"left": "Cold", "right": "Hot"},
        "clue": CLUE,
        "target": 77,  # a guesser's observation has none; if one ever did, it must not be copied
        "plan": [1, 2, 3],
        "history": [{"round": 1, "clue": "x", "guess": 3, "target": 9, "points": 0, "secret": "s"}],
    }
    context = json.loads(thinking_context("guesser", obs))
    assert "target" not in context and "plan" not in context
    assert context["past_rounds"] == [
        {"round": 1, "clue": "x", "guess": 3, "target": 9, "points": 0}
    ]
    assert json.loads(thinking_context("psychic", obs))["target"] == 77


def test_a_rejected_clue_is_retried_without_thinking_again() -> None:
    class BadThenGood(FakeBackend):
        def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> Any:
            self.calls.append(("decide", json.dumps(observation)))
            if is_free_text(legal_actions) is None:
                return SeatDecision(action=40, banter="ok")
            bad = sum(1 for k, _ in self.calls if k == "decide") == 1
            return SeatDecision(action="the left end" if bad else CLUE, banter=None)

    a, b = BadThenGood("a"), FakeBackend("b")
    play(1, a, b)
    kinds = [k for k, _ in a.calls]
    assert kinds == ["respond", "decide", "decide"]  # one set of notes, two attempts


def test_a_failed_notes_call_does_not_stop_the_move() -> None:
    a, b = FakeBackend("a", fail_notes=True), FakeBackend("b")
    play(1, a, b)
    decide = next(text for k, text in a.calls if k == "decide")
    assert "NOTES" not in decide


def test_the_call_cap_is_not_swallowed_by_the_thinking_step() -> None:
    a, b = FakeBackend("a"), FakeBackend("b")
    meter = Meter(max_calls=3)
    # The framework reports a seat's failure as a timeout; the meter says it was the cap.
    with pytest.raises(AgentTimeoutError):
        play(3, a, b, meter)
    assert meter.capped and meter.calls == 3


def test_chat_still_goes_through_to_the_model_unchanged() -> None:
    a = FakeBackend("a")
    thinking = ThinkingSeat(metered(a, Meter()))
    reply = thinking.respond([], TextTurn(text="hello"))
    assert isinstance(reply, TextTurn) and a.calls == [("respond", "hello")]


def test_the_notes_are_kept_for_later_and_capped() -> None:
    a = FakeBackend("a")
    seat_ = ThinkingSeat(metered(a, Meter()))
    seat_.decide({"round": 1, "spectrum": {"left": "A", "right": "B"}, "target": 10}, ["x"])  # type: ignore[list-item]
    assert seat_.last is not None and seat_.last["role"] in ("psychic", "guesser")
