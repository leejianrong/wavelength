"""The eval harness, exercised with scripted seats (no API)."""

from __future__ import annotations

from typing import Any

import pytest
from agent_game_framework.core import SeatDecision

from wavelength.bots import RandomWavelengthBot
from wavelength.eval import EvalResult, random_baseline, run_eval


def test_the_baseline_is_the_exact_random_guesser_mean() -> None:
    assert random_baseline() == pytest.approx(0.5678, abs=1e-4)


def test_two_bots_play_the_requested_rounds_and_the_report_names_the_baseline() -> None:
    result = run_eval(RandomWavelengthBot(), RandomWavelengthBot(), rounds=20, seed=3)

    assert result.rounds_played == 20 and result.error is None
    assert result.mean == result.total_points / 20
    assert 0 <= result.bullseyes <= 20
    assert "uniform-random guesser: 0.57" in result.report()


def test_the_same_seed_gives_the_same_result() -> None:
    a = run_eval(RandomWavelengthBot(), RandomWavelengthBot(), rounds=10, seed=9)
    b = run_eval(RandomWavelengthBot(), RandomWavelengthBot(), rounds=10, seed=9)
    assert a == b


def test_a_seat_that_always_fails_stops_the_run_and_what_was_played_is_reported() -> None:
    class Broken:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            raise RuntimeError("model unavailable")

    result = run_eval(Broken(), RandomWavelengthBot(), rounds=5, seed=1)

    assert result.rounds_played == 0
    assert result.error is not None and "model unavailable" in result.error
    assert "stopped early" in result.report()


def test_an_empty_run_has_a_zero_mean_not_a_division_error() -> None:
    assert EvalResult(5, 0, 0, 0, "x").mean == 0.0
