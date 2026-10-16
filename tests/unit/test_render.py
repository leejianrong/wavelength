"""The terminal renderer shows only what the observation holds."""

from __future__ import annotations

from typing import Any

from wavelength.engine import WavelengthEngine
from wavelength.render import render_dial, render_observation

ENGINE = WavelengthEngine()


def play_to_the_end(rounds: int = 2) -> Any:
    state = ENGINE.initial_state(["A", "B"], {"rounds": rounds, "seed": 1})
    for _ in range(rounds):
        state = ENGINE.apply_action(state, ENGINE.current_players(state)[0], "a lazy afternoon")
        state = ENGINE.apply_action(state, ENGINE.current_players(state)[0], 50)
    return state


def test_dial_marks_guess_target_and_a_shared_cell() -> None:
    both = render_dial("L", "R", guess=0, target=100)
    assert both.count("G") == 1 and both.count("T") == 1
    same = render_dial("L", "R", guess=50, target=50)
    assert "X" in same and "G" not in same and "T" not in same


def test_the_guesser_view_never_prints_a_target_before_the_guess() -> None:
    state = ENGINE.initial_state(["A", "B"], {"rounds": 1, "seed": 1})
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    text = render_observation(ENGINE.observation_for(state, "B"))
    assert "target" not in text.lower()
    assert "T" not in text.split("[")[1].split("]")[0]  # no marker on the dial


def test_the_psychic_view_prints_the_target() -> None:
    state = ENGINE.initial_state(["A", "B"], {"rounds": 1, "seed": 1})
    text = render_observation(ENGINE.observation_for(state, "A"))
    assert f"({state.plan[0].target} on a dial" in text


def test_the_final_view_has_one_recap_row_per_round_and_a_verdict() -> None:
    state = play_to_the_end(2)
    text = render_observation(ENGINE.observation_for(state, "A"))
    assert text.count("a lazy afternoon") == 3  # the last reveal, then one recap row per round
    assert "Match over" in text
