"""Engine rules: scoring, setup validation, visibility, serialization."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agent_game_framework.core import FreeText, IllegalActionError

from wavelength.engine import (
    DEFAULT_BANDS,
    WavelengthEngine,
    WavelengthState,
    score_guess,
)

ENGINE = WavelengthEngine()
PLAYERS = ["A", "B"]


def start(**config: Any) -> WavelengthState:
    config.setdefault("seed", 1)
    return ENGINE.initial_state(PLAYERS, config)


def target_of(state: WavelengthState) -> int:
    return state.plan[state.round_index].target


@pytest.mark.parametrize(
    ("distance", "points"),
    [(0, 4), (2, 4), (3, 3), (6, 3), (7, 2), (10, 2), (11, 0), (100, 0)],
)
def test_scoring_at_every_band_edge(distance: int, points: int) -> None:
    assert score_guess(50 + distance, 50, DEFAULT_BANDS) == points
    assert score_guess(50 - distance, 50, DEFAULT_BANDS) == points


def test_scoring_at_the_dial_ends() -> None:
    assert score_guess(0, 0, DEFAULT_BANDS) == 4
    assert score_guess(100, 100, DEFAULT_BANDS) == 4
    assert score_guess(0, 100, DEFAULT_BANDS) == 0


@pytest.mark.parametrize("players", [["A"], ["A", "B", "C"], ["A", "A"]])
def test_roster_must_be_two_distinct_players(players: list[str]) -> None:
    with pytest.raises(ValueError, match="2 distinct players"):
        ENGINE.initial_state(players, {})


@pytest.mark.parametrize(
    "config",
    [
        {"rounds": 0},
        {"rounds": True},
        {"rounds": "6"},
        {"rounds": 10_000},
        {"target_score": -1},
        {"bands": []},
        {"bands": [[6, 3], [2, 4]]},
        {"bands": "nope"},
    ],
)
def test_bad_config_is_rejected(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ENGINE.initial_state(PLAYERS, config)


def test_same_seed_same_plan_and_different_seed_differs() -> None:
    assert start(seed=3).plan == start(seed=3).plan
    assert start(seed=3).plan != start(seed=4).plan


def test_targets_stay_on_the_dial_and_spectra_do_not_repeat() -> None:
    plan = start(seed=9, rounds=30).plan
    assert all(0 <= p.target <= 100 for p in plan)
    assert len({p.spectrum for p in plan}) == 30


def test_phases_hand_the_turn_to_the_right_seat() -> None:
    state = start()
    assert ENGINE.current_players(state) == ["A"]
    assert ENGINE.legal_actions(state, "B") == []
    assert ENGINE.legal_actions(state, "A") == [FreeText(max_words=6, max_chars=80)]

    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    assert ENGINE.current_players(state) == ["B"]
    assert ENGINE.legal_actions(state, "B") == list(range(101))


def test_a_full_round_scores_and_reveals() -> None:
    state = start(rounds=2)
    target = target_of(state)
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    state = ENGINE.apply_action(state, "B", target)

    assert state.total == 4
    assert state.history[0].target == target
    assert state.history[0].psychic == "A"
    assert ENGINE.current_players(state) == ["B"]  # roles swapped: B is now psychic
    assert not ENGINE.is_terminal(state)


def test_roles_alternate_and_match_ends_after_the_last_round() -> None:
    state = start(rounds=3)
    psychics = []
    for _ in range(3):
        psychics.append(ENGINE.current_players(state)[0])
        state = ENGINE.apply_action(state, psychics[-1], "a lazy afternoon")
        state = ENGINE.apply_action(state, ENGINE.current_players(state)[0], 50)
    assert psychics == ["A", "B", "A"]
    assert ENGINE.is_terminal(state)
    assert ENGINE.current_players(state) == []


def test_winners_follow_the_threshold_exactly() -> None:
    def play(guess_offset: int, target_score: int) -> WavelengthState:
        state = start(rounds=1, target_score=target_score)
        t = target_of(state)
        guess = min(100, t + guess_offset) if t < 50 else max(0, t - guess_offset)
        state = ENGINE.apply_action(state, "A", "a lazy afternoon")
        return ENGINE.apply_action(state, "B", guess)

    assert ENGINE.winners(play(0, 4)) == PLAYERS  # 4 >= 4
    assert ENGINE.winners(play(0, 5)) == []  # 4 < 5
    assert ENGINE.winners(play(50, 0)) == PLAYERS  # 0 >= 0


@pytest.mark.parametrize("bad", [101, -1, True, "50", 5.5, None])
def test_bad_guesses_are_rejected_and_state_is_untouched(bad: Any) -> None:
    state = ENGINE.apply_action(start(), "A", "a lazy afternoon")
    before = ENGINE.serialize(state)
    with pytest.raises(IllegalActionError):
        ENGINE.apply_action(state, "B", bad)
    assert ENGINE.serialize(state) == before


def test_bad_clue_and_out_of_turn_are_rejected_and_state_is_untouched() -> None:
    state = start()
    before = ENGINE.serialize(state)
    with pytest.raises(IllegalActionError, match="digits"):
        ENGINE.apply_action(state, "A", "about 70")
    with pytest.raises(IllegalActionError, match="not their turn"):
        ENGINE.apply_action(state, "B", "a lazy afternoon")
    with pytest.raises(IllegalActionError):
        ENGINE.apply_action(state, "A", 50)  # a guess in the clue phase
    assert ENGINE.serialize(state) == before


def test_actions_after_the_end_are_rejected() -> None:
    state = start(rounds=1)
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    state = ENGINE.apply_action(state, "B", 50)
    with pytest.raises(IllegalActionError):
        ENGINE.apply_action(state, "A", "one more")


def test_the_guesser_never_sees_the_current_target_or_any_future_one() -> None:
    state = start(rounds=3, seed=5)
    for phase_action in (None, "a lazy afternoon"):
        if phase_action:
            state = ENGINE.apply_action(state, "A", phase_action)
        guesser_obs = ENGINE.observation_for(state, "B")
        text = json.dumps(guesser_obs)
        assert "target" not in guesser_obs
        assert "plan" not in guesser_obs
        # no future round's spectrum leaks either
        for later in state.plan[1:]:
            assert later.spectrum.left not in text
    psychic_obs = ENGINE.observation_for(state, "A")
    assert psychic_obs["target"] == target_of(state)
    assert "plan" not in psychic_obs


def test_a_revealed_target_becomes_public_but_only_after_the_guess() -> None:
    state = start(rounds=2)
    first_target = target_of(state)
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    assert first_target not in [r["target"] for r in ENGINE.observation_for(state, "B")["history"]]
    state = ENGINE.apply_action(state, "B", 50)
    assert ENGINE.observation_for(state, "B")["history"][0]["target"] == first_target


def test_round_trip_mid_round_and_unknown_schema_version() -> None:
    state = ENGINE.apply_action(start(rounds=2), "A", "a lazy afternoon")
    data = ENGINE.serialize(state)
    assert data["schema_version"] == 1
    assert ENGINE.serialize(ENGINE.deserialize(json.loads(json.dumps(data)))) == data
    data["schema_version"] = 99
    with pytest.raises(ValueError, match="schema_version"):
        ENGINE.deserialize(data)


def test_finished_observation_reports_the_result() -> None:
    state = start(rounds=1, target_score=0)
    state = ENGINE.apply_action(state, "A", "a lazy afternoon")
    state = ENGINE.apply_action(state, "B", 50)
    obs = ENGINE.observation_for(state, "B")
    assert obs["phase"] is None
    assert obs["won"] is True
