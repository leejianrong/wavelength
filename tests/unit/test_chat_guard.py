"""The chat context is an allow-list projection of the observation (ADR-0005)."""

from __future__ import annotations

from typing import Any

import pytest

from wavelength.chat_guard import chat_context
from wavelength.engine import WavelengthEngine, WavelengthState

ENGINE = WavelengthEngine()


def seeded(low: int = 31, high: int = 99, **config: Any) -> WavelengthState:
    """A match whose first target is a number that cannot appear by accident
    in round/score text, so ``str(target) in text`` is a real leak check."""
    for seed in range(500):
        state = ENGINE.initial_state(["A", "B"], {"seed": seed, **config})
        if low <= state.plan[0].target <= high and all(
            not (low <= p.target <= high) or p.target != state.plan[0].target
            for p in state.plan[1:]
        ):
            return state
    raise AssertionError("no suitable seed")


def test_the_psychic_gets_no_chat_context_at_all() -> None:
    state = seeded()
    assert chat_context(ENGINE.observation_for(state, "A")) is None
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    assert chat_context(ENGINE.observation_for(state, "A")) is None  # still psychic mid-round


def test_the_guesser_context_has_the_spectrum_and_clue_but_never_the_target() -> None:
    state = seeded()
    target = state.plan[0].target
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    text = chat_context(ENGINE.observation_for(state, "B"))

    assert text is not None
    assert state.plan[0].spectrum.left in text and state.plan[0].spectrum.right in text
    assert '"a lazy afternoon"' in text
    assert str(target) not in text
    assert "target" not in text.lower().replace("target was", "").replace("target_score", "")


def test_before_the_clue_the_guesser_is_told_there_is_none_yet() -> None:
    state = seeded()
    # B is the guesser in round 1; its observation exists even before the clue
    text = chat_context(ENGINE.observation_for(state, "B"))
    assert text is not None and "has not given a clue yet" in text


def test_a_revealed_round_is_public_and_comes_with_its_target() -> None:
    state = seeded(rounds=2)
    first_target = state.plan[0].target
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    state = ENGINE.apply_action(state, "B", 50)
    # round 2: B is psychic (no chat), A is the guesser and may hear about round 1
    assert chat_context(ENGINE.observation_for(state, "B")) is None
    text = chat_context(ENGINE.observation_for(state, "A"))
    assert text is not None
    assert f"target was {first_target}" in text
    assert str(state.plan[1].target) not in text  # the new round's target stays hidden


def test_the_finished_match_context_is_open_to_both_seats() -> None:
    state = seeded(rounds=1)
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    state = ENGINE.apply_action(state, "B", 50)
    for who in ("A", "B"):
        text = chat_context(ENGINE.observation_for(state, who))
        assert text is not None and "The match is over" in text


def test_only_listed_observation_fields_reach_the_text() -> None:
    """A field added to the observation later must not show up in chat."""
    state = seeded()
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    obs = ENGINE.observation_for(state, "B")
    obs["secret_note"] = "ZEBRA-4242"
    obs["plan"] = [{"target": 77}]
    text = chat_context(obs)
    assert text is not None and "ZEBRA-4242" not in text and "77" not in text


@pytest.mark.parametrize("role", ["psychic"])
def test_a_psychic_role_in_any_phase_is_silent(role: str) -> None:
    assert chat_context({"role": role, "phase": "guess"}) is None
