"""Acceptance tests for V1: drive the installed ``wavelength`` script."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from wavelength.engine import WavelengthEngine

PLAY = ["wavelength", "play", "wavelength"]


def run(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=60)


def one_round(*extra: str, stdin: str = "a lazy afternoon\n") -> subprocess.CompletedProcess[str]:
    return run(
        [*PLAY, "--config", "rounds=1", "--seat", "A=human", "--seat", "B=bot:wl-random", *extra],
        stdin,
    )


def test_a_scripted_round_plays_to_the_end_and_shows_the_dial() -> None:
    result = one_round("--config", "seed=7")

    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert re.search(r"\[[.GTX]{41}\]", out)  # the dial
    assert re.search(r"Guess \d+, target \d+: \d points?", out)
    assert "Match over" in out


def test_the_same_seed_gives_an_identical_transcript() -> None:
    first = one_round("--config", "seed=7")
    second = one_round("--config", "seed=7")
    other = one_round("--config", "seed=8")

    assert first.stdout == second.stdout
    assert first.stdout != other.stdout


def test_a_clue_that_gives_away_position_is_rejected_and_the_turn_does_not_advance() -> None:
    result = one_round("--config", "seed=7", stdin="about 70\nleft of centre\na lazy afternoon\n")

    assert result.returncode == 0, result.stderr
    assert "digits" in result.stdout
    assert "left" in result.stdout
    assert result.stdout.count("B plays") == 1  # the guesser only moved after a fair clue
    assert 'clue "a lazy afternoon"' in result.stdout


def _seed_with_target_between(low: int, high: int) -> tuple[int, int]:
    engine = WavelengthEngine()
    for seed in range(1000):
        state = engine.initial_state(["A", "B"], {"rounds": 1, "seed": seed})
        if low <= state.plan[0].target <= high:
            return seed, state.plan[0].target
    raise AssertionError("no suitable seed")


def test_a_human_guesser_never_sees_the_target_before_guessing() -> None:
    seed, target = _seed_with_target_between(31, 99)
    result = run(
        [
            *PLAY,
            "--config",
            "rounds=1",
            "--config",
            f"seed={seed}",
            "--seat",
            "A=bot:wl-random",
            "--seat",
            "B=human",
            "--json",
        ],
        "50\n",
    )

    assert result.returncode == 0, result.stderr
    before_guess = result.stdout.split("Your move: ")[0]
    # the prompt lists every legal guess 0-100, which is not a leak
    scanned = "\n".join(
        line for line in before_guess.splitlines() if not line.startswith("Legal actions:")
    )
    assert '"target"' not in scanned
    assert not re.search(rf"\b{target}\b", scanned)
    events = [
        json.loads(line[line.index('{"type"') :])
        for line in result.stdout.splitlines()
        if '{"type"' in line
    ]
    clue_turn = next(e for e in events if e["type"] == "turn" and e["seat"] == "A")
    assert "target" not in clue_turn["state"]
    assert "plan" not in clue_turn["state"]
    # the reveal after the guess is public by the rules
    assert events[-1]["state"]["history"][0]["target"] == target


def test_omniscient_flag_is_an_explicit_opt_in_for_the_full_dump() -> None:
    seed, target = _seed_with_target_between(31, 99)
    result = run(
        [
            *PLAY,
            "--config",
            "rounds=1",
            "--config",
            f"seed={seed}",
            "--seat",
            "A=bot:wl-random",
            "--seat",
            "B=human",
            "--json",
            "--omniscient",
        ],
        "50\n",
    )

    first: dict[str, Any] = json.loads(
        result.stdout[result.stdout.index('{"type"') :].splitlines()[0]
    )
    assert first["state"]["plan"][0]["target"] == target


def test_unknown_game_settings_are_usage_errors_not_tracebacks() -> None:
    result = run(
        [*PLAY, "--config", "rounds=0", "--seat", "A=bot:wl-random", "--seat", "B=bot:wl-random"]
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "rounds" in result.stdout


def test_installs_into_a_clean_venv_and_registers_itself(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    uv = shutil.which("uv")
    assert uv is not None
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", str(venv), "--python", sys.executable], check=True)
    subprocess.run(
        [uv, "pip", "install", "--python", str(venv / "bin" / "python"), str(repo)],
        check=True,
        capture_output=True,
    )

    result = run([str(venv / "bin" / "wavelength"), "play", "--help"])

    assert result.returncode == 0, result.stderr
    assert "wavelength" in result.stdout  # the registered game is a valid choice
