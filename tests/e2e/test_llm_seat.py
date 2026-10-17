"""The ``llm:openrouter/<model>`` seat in both roles, against a mocked endpoint.

These prove the wiring a human plays through with ``make play`` (free-text clue
out of an LLM, a guess out of an LLM, banter shown) and, crucially, what the
model is *shown*: an LLM guesser's request must not contain the target.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from _mock_openrouter import BANTER, CHAT_REPLY, CLUE, mock_openrouter

from wavelength.chat_guard import PSYCHIC_REFUSAL
from wavelength.engine import WavelengthEngine

LLM = "llm:openrouter/test/model"


def play(
    base_url: str, seats: list[str], stdin: str, *extra: str
) -> subprocess.CompletedProcess[str]:
    args = ["wavelength", "play", "wavelength", "--config", "rounds=1", *extra]
    for seat in seats:
        args += ["--seat", seat]
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key", "OPENROUTER_BASE_URL": base_url}
    return subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=60, env=env)


def observation_sent(request: dict[str, Any]) -> dict[str, Any]:
    """The observation the model was shown (the user message's JSON)."""
    sent: dict[str, Any] = json.loads(request["messages"][1]["content"])["observation"]
    return sent


def assert_chat_is_safe(events: list[dict[str, Any]], requests: list[dict[str, Any]]) -> None:
    """Since framework PR #40 two AI seats reply to each other's banter. A reply is either the
    fixed psychic refusal or a model's answer; a model is only ever asked as a guesser (the
    chat context says so), never while it holds an unrevealed target."""
    assert {e["text"] for e in events if e["type"] == "chat"} <= {PSYCHIC_REFUSAL, CHAT_REPLY}
    for request in (r for r in requests if not r.get("tools")):
        text = json.dumps(request)
        assert "You are the guesser." in text or "The match is over" in text


def target_for(seed: int) -> int:
    return WavelengthEngine().initial_state(["A", "B"], {"rounds": 1, "seed": seed}).plan[0].target


def test_an_llm_guesser_answers_a_human_clue_and_never_sees_the_target() -> None:
    seed = 4
    target = target_for(seed)
    with mock_openrouter() as (url, requests):
        result = play(url, ["A=human", f"B={LLM}"], f"{CLUE}\n", "--config", f"seed={seed}")

    assert result.returncode == 0, result.stderr
    assert f'B plays 50  ("{BANTER}")' in result.stdout
    assert "Match over" in result.stdout
    moves = [r for r in requests if r.get("tools")]
    assert len(moves) == 1
    seen = observation_sent(moves[0])
    assert seen["clue"] == CLUE  # it was given the clue
    assert "target" not in seen and "plan" not in seen
    assert str(target) not in json.dumps(seen)
    assert str(target) not in moves[0]["messages"][0]["content"]  # nor in the system prompt
    schema = moves[0]["tools"][0]["function"]["parameters"]["properties"]["action"]
    assert schema["enum"] == list(range(101))


def test_an_llm_psychic_gives_a_free_text_clue_that_the_engine_accepts() -> None:
    seed = 4
    target = target_for(seed)
    with mock_openrouter() as (url, requests):
        result = play(url, [f"A={LLM}", "B=human"], "50\n", "--config", f"seed={seed}")

    assert result.returncode == 0, result.stderr
    # the psychic knows the target, so its banter is never shown on a clue turn
    assert f"A plays {CLUE!r}" in result.stdout
    assert f'A plays {CLUE!r}  ("' not in result.stdout
    moves = [r for r in requests if r.get("tools")]
    schema = moves[0]["tools"][0]["function"]["parameters"]["properties"]["action"]
    assert schema["type"] == "string" and "enum" not in schema
    # the psychic is the one seat that is told the target
    assert observation_sent(moves[0])["target"] == target
    # and the human guesser's terminal never showed it before the guess
    before_guess = result.stdout.split("Your move: ")[0]
    assert '"target"' not in before_guess


def test_two_llm_seats_play_a_whole_match_with_no_human() -> None:
    with mock_openrouter() as (url, requests):
        result = play(url, [f"A={LLM}", f"B={LLM}"], "", "--config", "seed=2", "--json")

    assert result.returncode == 0, result.stderr
    events: list[dict[str, Any]] = [json.loads(line) for line in result.stdout.splitlines() if line]
    assert [e["type"] for e in events if e["type"] != "chat"] == ["turn", "turn", "result"]
    assert_chat_is_safe(events, requests)
    assert len([r for r in requests if r.get("tools")]) == 2


def test_an_llm_psychic_that_never_sends_a_legal_clue_stops_instead_of_looping() -> None:
    with mock_openrouter(clue="about 70") as (url, requests):
        result = play(url, [f"A={LLM}", "B=human"], "50\n")

    assert result.returncode == 3, result.stderr
    assert "failed to respond" in result.stdout
    moves = [r for r in requests if r.get("tools")]
    assert len(moves) <= 6  # 3 guarded attempts, each retried once by the framework
    # from the second attempt on the model was told why it was rejected
    told = [r["messages"][1]["content"] for r in moves]
    assert any("rejection_reason" in m and "digits" in m for m in told)


def test_a_guess_sent_as_text_is_coerced_and_played() -> None:
    with mock_openrouter(guess="50") as (url, requests):
        result = play(url, ["A=human", f"B={LLM}"], f"{CLUE}\n")

    assert result.returncode == 0, result.stderr
    assert f'B plays 50  ("{BANTER}")' in result.stdout
    assert len([r for r in requests if r.get("tools")]) == 1  # no retry needed


def test_an_llm_guesser_that_never_sends_a_legal_guess_stops_without_leaking() -> None:
    seed = 4
    target = target_for(seed)
    with mock_openrouter(guess="no idea") as (url, requests):
        result = play(url, ["A=human", f"B={LLM}"], f"{CLUE}\n", "--config", f"seed={seed}")

    assert result.returncode == 3, result.stderr
    assert "failed to respond" in result.stdout
    moves = [r for r in requests if r.get("tools")]
    assert 3 <= len(moves) <= 6  # 3 guarded attempts, each retried once by the framework
    told = [observation_sent(r) for r in moves]
    assert any(
        "whole number 0-100" in o.get("rejection_reason", "") and "target" not in o for o in told
    )
    for r in moves:  # the reason is new text for the guesser: the target is in none of it
        assert "target" not in observation_sent(r)
        assert f'"target": {target}' not in json.dumps(r)


def test_a_clue_wrapped_in_quotes_is_tidied_before_the_engine_sees_it() -> None:
    with mock_openrouter(clue=f'  "{CLUE}"  ') as (url, _):
        result = play(url, [f"A={LLM}", "B=human"], "50\n")

    assert result.returncode == 0, result.stderr
    assert f"A plays {CLUE!r}" in result.stdout


def test_two_llm_seats_play_six_rounds_and_the_guesser_is_never_shown_a_target() -> None:
    with mock_openrouter() as (url, requests):
        result = play(
            url,
            [f"A={LLM}", f"B={LLM}"],
            "",
            "--config",
            "rounds=6",
            "--config",
            "seed=2",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    events: list[dict[str, Any]] = [json.loads(line) for line in result.stdout.splitlines() if line]
    assert [e["type"] for e in events if e["type"] != "chat"] == ["turn"] * 12 + ["result"]
    assert_chat_is_safe(events, requests)
    moves = [r for r in requests if r.get("tools")]
    assert len(moves) == 12
    guesser_requests = [m for m in moves if "enum" in json.dumps(m["tools"])]
    psychic_requests = [m for m in moves if m not in guesser_requests]
    assert len(guesser_requests) == len(psychic_requests) == 6
    for m in guesser_requests:
        seen = observation_sent(m)
        assert seen["role"] == "guesser"
        assert "target" not in seen and "plan" not in seen
    for m in psychic_requests:
        assert observation_sent(m)["role"] == "psychic"
        assert "target" in observation_sent(m)


def test_the_eval_command_reports_points_per_round_against_the_baseline() -> None:
    with mock_openrouter() as (url, _):
        env = {**os.environ, "OPENROUTER_API_KEY": "test-key", "OPENROUTER_BASE_URL": url}
        result = subprocess.run(
            ["python", "-m", "wavelength.eval", "--model", "test/model", "--rounds", "6"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    assert result.returncode == 0, result.stderr
    assert "rounds played: 6/6" in result.stdout
    assert "uniform-random guesser: 0.57" in result.stdout


def eval_cmd(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key", "OPENROUTER_BASE_URL": url}
    return subprocess.run(
        ["python", "-m", "wavelength.eval", "--model", "test/model", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_the_eval_command_plays_several_seeds_and_reports_the_guard_counts() -> None:
    with mock_openrouter(guess=50) as (url, requests):
        result = eval_cmd(url, "--rounds", "2", "--seeds", "3", "--table")

    assert result.returncode == 0, result.stderr
    assert "rounds played: 6/6" in result.stdout
    assert "model calls: 12 (clue 6, guess 6)" in result.stdout
    assert "guesses not sent as a plain int: 0" in result.stdout
    assert "seed round psychic" in result.stdout
    assert len([r for r in requests if r.get("tools")]) == 12


def test_the_eval_command_stops_at_the_call_cap_and_still_reports() -> None:
    with mock_openrouter() as (url, requests):
        result = eval_cmd(url, "--rounds", "6", "--seeds", "2", "--max-calls", "5")

    assert result.returncode == 0, result.stderr
    assert "call cap reached" in result.stdout
    assert len([r for r in requests if r.get("tools")]) == 5


def test_the_eval_command_survives_a_model_that_sends_guesses_as_text() -> None:
    with mock_openrouter(guess="50") as (url, _):
        result = eval_cmd(url, "--rounds", "2")

    assert result.returncode == 0, result.stderr
    assert "rounds played: 2/2" in result.stdout
    assert "guesses not sent as a plain int: 2" in result.stdout
    assert "moves the engine refused: 0" in result.stdout
