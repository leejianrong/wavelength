"""V15 (ADR-0012): a guesser that works the needle in steps. A scripted fake model; no network."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agent_game_framework.core import FreeText, Match, SeatDecision, TextTurn, is_free_text

from wavelength.engine import WavelengthEngine
from wavelength.eval import CallCapExceeded, Meter, metered
from wavelength.needle_seat import NeedleSeat, Step, parse_step
from wavelength.seats import guard

CLUE = "a lazy afternoon"
OBS = {
    "round": 1,
    "rounds": 3,
    "role": "guesser",
    "phase": "guess",
    "clue": CLUE,
    "spectrum": {"left": "Busy", "right": "Calm"},
    "history": [],
    "total_score": 0,
}
LEGAL = list(range(101))


def reply(say: str, needle: Any, lock: bool = False) -> str:
    return json.dumps({"say": say, "needle": needle, "lock": lock})


class Scripted:
    """Answers each plain call with the next scripted text; records what it was shown."""

    def __init__(self, texts: list[Any]) -> None:
        self.texts = list(texts)
        self.respond_calls: list[tuple[int, str]] = []  # (history length, prompt)
        self.decide_calls = 0

    def respond(self, history: Any, incoming: Any) -> TextTurn:
        self.respond_calls.append((len(history), incoming.text))
        nxt = self.texts.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return TextTurn(text=nxt)

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        self.decide_calls += 1
        return SeatDecision(action=CLUE if is_free_text(legal_actions) else 44, banter="fallback")


def run(texts: list[Any], meter: Meter | None = None) -> tuple[Any, Scripted, list[Step], Meter]:
    meter = meter or Meter()
    model = Scripted(texts)
    seat = NeedleSeat(metered(model, meter))  # type: ignore[arg-type]
    steps: list[Step] = []
    seat.bind_steps(steps.append)
    decision = seat.decide(OBS, LEGAL)
    return decision, model, steps, meter


def test_steps_end_in_a_lock_and_the_locked_needle_is_the_move() -> None:
    decision, model, steps, meter = run(
        [reply("Sounds calm.", 70), reply("A touch calmer.", 78), reply("Good.", 78, True)]
    )
    assert decision.action == 78 and decision.banter is None
    assert [(s.index, s.needle, s.final) for s in steps] == [
        (1, 70, False),
        (2, 78, False),
        (3, 78, True),
    ]
    assert [s.say for s in steps][0] == "Sounds calm."
    assert meter.calls == 3  # every step is a counted call
    assert model.decide_calls == 0


def test_each_step_sees_its_own_earlier_steps_as_history() -> None:
    _, model, _, _ = run([reply("a", 30), reply("b", 31, True)])
    assert [h for h, _ in model.respond_calls] == [0, 2]
    assert "The needle is at 30." in model.respond_calls[1][1]


def test_the_last_allowed_step_is_told_to_lock_and_does_lock() -> None:
    decision, model, steps, _ = run(
        [reply("a", 10), reply("b", 20), reply("c", 30), reply("d", 40)]
    )
    assert len(model.respond_calls) == 4
    assert "last step" in model.respond_calls[3][1]
    assert decision.action == 40 and steps[-1].final and not any(s.final for s in steps[:-1])


def test_a_needle_off_the_dial_is_clamped() -> None:
    decision, _, steps, _ = run([reply("far", 150, True)])
    assert decision.action == 100 and steps[0].needle == 100


def test_an_unparseable_first_step_falls_back_to_the_ordinary_move() -> None:
    decision, model, steps, _ = run(["I think maybe fifty?"])
    assert decision.action == 44 and model.decide_calls == 1 and steps == []


def test_a_step_that_fails_after_a_needle_locks_where_the_needle_is() -> None:
    decision, _, steps, _ = run([reply("first", 61), RuntimeError("the model is down")])
    assert decision.action == 61
    assert [(s.needle, s.final) for s in steps] == [(61, False), (61, True)]


def test_a_reply_with_no_needle_after_one_keeps_the_last_needle() -> None:
    decision, _, steps, _ = run([reply("first", 61), json.dumps({"say": "hm", "lock": True})])
    assert decision.action == 61 and steps[-1].final


def test_a_call_cap_is_never_swallowed() -> None:
    with pytest.raises(CallCapExceeded):
        run([reply("a", 30), reply("b", 31)], meter=Meter(max_calls=1))


def test_parse_step_reads_a_step_out_of_surrounding_text() -> None:
    assert parse_step('Sure! {"say": "ok", "needle": "42", "lock": true} done', 0, 100) == (
        "ok",
        42,
        True,
    )
    assert parse_step('{"say": "x", "needle": true}', 0, 100) == ("x", None, False)
    assert parse_step("no json here", 0, 100) is None
    assert parse_step("[1, 2]", 0, 100) is None


def test_a_rejected_guess_is_re_asked_with_the_ordinary_move_call() -> None:
    model = Scripted([])
    seat = NeedleSeat(metered(model, Meter()))  # type: ignore[arg-type]
    decision = seat.decide({**OBS, "previous_guess_rejected": 200}, LEGAL)
    assert decision.action == 44 and model.respond_calls == []


def test_a_psychic_thinks_as_before_and_never_steps() -> None:
    model = Scripted(["NOTES the target is far left"])
    seat = NeedleSeat(metered(model, Meter()))  # type: ignore[arg-type]
    steps: list[Step] = []
    seat.bind_steps(steps.append)
    clue_obs = {**OBS, "role": "psychic", "phase": "clue", "target": 7}
    decision = seat.decide(clue_obs, [FreeText(max_words=6, max_chars=80)])
    assert decision.action == CLUE and steps == []
    assert seat.last is not None and seat.last["role"] == "psychic"


def test_a_guesser_step_prompt_never_holds_this_rounds_target() -> None:
    class Model:
        def __init__(self) -> None:
            self.guesser_prompts: list[str] = []

        def respond(self, history: Any, incoming: Any) -> TextTurn:
            if "You are the guesser" in incoming.text:
                self.guesser_prompts.append(incoming.text)
                return TextTurn(text=reply("calm", 60, True))
            return TextTurn(text="NOTES a clue near the middle")

        def decide(
            self, observation: dict[str, Any], legal_actions: list[Any]
        ) -> SeatDecision[Any]:
            return SeatDecision(action=CLUE if is_free_text(legal_actions) else 40, banter="x")

    models = {"a": Model(), "b": Model()}
    meter = Meter()
    match: Match[Any, Any, Any] = Match(
        WavelengthEngine(),
        players=["a", "b"],
        config={"rounds": 3, "seed": 5},
        seats={p: guard(NeedleSeat(metered(m, meter))) for p, m in models.items()},  # type: ignore[arg-type]
    )
    match.run_to_completion()
    prompts = [p for m in models.values() for p in m.guesser_prompts]
    assert prompts
    for text in prompts:
        situation = json.loads(text.split("The situation:\n", 1)[1].split("\n\nYou may take", 1)[0])
        assert "target" not in situation  # past rounds list revealed targets only
