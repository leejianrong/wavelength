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

from _mock_openrouter import BANTER, CLUE, mock_openrouter

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
    assert f'A plays {CLUE!r}  ("{BANTER}")' in result.stdout
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
    assert [e["type"] for e in events] == ["turn", "turn", "result"]
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
