"""The eval harness, exercised with scripted seats (no API)."""

from __future__ import annotations

from typing import Any

import pytest
from agent_game_framework.core import SeatDecision

from wavelength.bots import RandomWavelengthBot
from wavelength.eval import EvalResult, Meter, MeteredSeat, random_baseline, run_eval
from wavelength.seats import guard


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


class Typed:
    """A guesser/psychic whose replies are scripted per kind of request."""

    def __init__(self, clues: list[Any], guesses: list[Any]) -> None:
        self.clues, self.guesses = clues, guesses

    def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        queue = self.guesses if isinstance(legal_actions[0], int) else self.clues
        return SeatDecision(action=queue.pop(0) if queue else queue_default(legal_actions))


def queue_default(legal_actions: list[Any]) -> Any:
    return 50 if isinstance(legal_actions[0], int) else "a lazy afternoon"


def test_the_meter_counts_calls_rejected_clues_and_guesses_that_were_not_ints() -> None:
    meter = Meter()
    seat = guard(MeteredSeat(Typed(["about 70", "a lazy afternoon"], ["35", 40]), meter))
    other = guard(MeteredSeat(Typed([], []), meter))
    result = run_eval(seat, other, rounds=2, seed=1, meter=meter)

    assert result.error is None and result.rounds_played == 2
    assert result.clue_rejections == 1  # "about 70" was refused and asked again
    assert result.guess_not_int == 1  # "35" arrived as text and was coerced
    assert result.calls == meter.calls == result.clue_calls + result.guess_calls
    assert result.clue_calls == 3 and result.guess_calls == 2
    report = result.report()
    assert "clue attempts rejected by the rules: 1" in report
    assert "guesses not sent as a plain int: 1" in report


def test_an_unguarded_illegal_move_is_re_asked_counted_and_cannot_loop_forever() -> None:
    class Stubborn:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            return SeatDecision(action="no idea" if isinstance(legal_actions[0], int) else "calm")

    result = run_eval(RandomWavelengthBot(), Stubborn(), rounds=2, seed=1)

    assert result.rounds_played == 0
    assert result.illegal_moves == 5
    assert result.error is not None and "5 refused moves in a row" in result.error


def test_the_call_cap_stops_the_run_and_reports_what_was_played() -> None:
    meter = Meter(max_calls=5)
    seat = MeteredSeat(RandomWavelengthBot(), meter)
    result = run_eval(
        seat, MeteredSeat(RandomWavelengthBot(), meter), rounds=10, seed=2, meter=meter
    )

    assert meter.capped and meter.calls == 5
    assert result.rounds_played == 2  # 4 moves = 2 rounds; the 5th call was refused
    assert result.error is not None and "call cap reached" in result.error


def test_combine_adds_matches_and_the_table_lists_every_round() -> None:
    a = run_eval(RandomWavelengthBot(), RandomWavelengthBot(), rounds=3, seed=1)
    b = run_eval(RandomWavelengthBot(), RandomWavelengthBot(), rounds=3, seed=2)
    total = EvalResult.combine([a, b])

    assert total.rounds_played == 6
    assert total.total_points == a.total_points + b.total_points
    lines = total.report(table=True).splitlines()
    assert lines[-7].startswith("seed round")
    assert len(lines) - lines.index(next(x for x in lines if x.startswith("seed round"))) == 7
    assert "table" not in total.report() and "seed round" not in total.report()


def provider_403() -> Any:
    import httpx2

    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx2.Response(
        403,
        json={"error": {"message": "Key limit exceeded (daily)", "code": 403}},
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792800000", "other": "no"},
        request=request,
    )
    return httpx2.HTTPStatusError(
        "Client error '403 Forbidden' for url 'https://openrouter.ai/api/v1/chat/completions'",
        request=request,
        response=response,
    )


def test_a_provider_error_is_reported_with_its_status_body_and_rate_limit_headers() -> None:
    from wavelength.eval import explain_provider_errors

    class Refused:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            raise provider_403()

    result = run_eval(explain_provider_errors(Refused()), RandomWavelengthBot(), rounds=5, seed=1)

    assert result.rounds_played == 0 and result.error is not None
    for part in ("provider returned 403", "Key limit exceeded (daily)", "x-ratelimit-remaining: 0"):
        assert part in result.error
    assert "other:" not in result.error  # only the headers that explain a refusal
    assert "stopped early: provider returned 403" in result.report()


def test_the_provider_error_keeps_the_key_out_of_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from wavelength.eval import explain_provider_errors

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-value")

    class Echo:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            import httpx2

            request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
            response = httpx2.Response(401, text="bad key sk-or-secret-value", request=request)
            raise httpx2.HTTPStatusError("401", request=request, response=response)

    result = run_eval(explain_provider_errors(Echo()), RandomWavelengthBot(), rounds=2, seed=1)
    assert result.error is not None and "sk-or-secret-value" not in result.error
    assert "401" in result.error


def test_a_seat_that_works_is_not_changed_by_the_wrapper() -> None:
    from wavelength.eval import explain_provider_errors

    a = run_eval(RandomWavelengthBot(), RandomWavelengthBot(), rounds=6, seed=4)
    b = run_eval(
        explain_provider_errors(RandomWavelengthBot()), RandomWavelengthBot(), rounds=6, seed=4
    )
    assert a == b
