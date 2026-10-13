"""Acceptance tests for V2: whole matches through the installed script."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

PLAY = ["wavelength", "play", "wavelength"]


def run(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=60)


def recap_rows(out: str) -> list[list[str]]:
    """The end-of-match table's rows as ``[round, psychic, ..., points]``."""
    rows = []
    for line in out.splitlines():
        match = re.match(r"\s*(\d+)\s+(\w+)\s+.*?(\d+)\s+(\d+)\s+(\d+)\s*$", line)
        if match and "Round" not in line:
            rows.append(list(match.groups()))
    return rows


def all_bots(*extra: str) -> subprocess.CompletedProcess[str]:
    return run([*PLAY, "--seat", "A=bot:wl-random", "--seat", "B=bot:wl-random", *extra])


def test_an_all_bot_match_needs_no_input_and_ends_with_a_recap_and_a_verdict() -> None:
    result = all_bots("--config", "seed=3")

    assert result.returncode == 0, result.stderr
    rows = recap_rows(result.stdout)
    assert [r[0] for r in rows] == ["1", "2", "3", "4", "5", "6"]
    total = sum(int(r[4]) for r in rows)
    assert f"Match over: {total} / 12 points." in result.stdout


def test_a_win_and_a_loss_both_exit_zero_and_say_which_it_was() -> None:
    won = all_bots("--config", "seed=3", "--config", "target_score=0")
    lost = all_bots("--config", "seed=3", "--config", "target_score=999")

    assert won.returncode == 0 and "You won!" in won.stdout
    assert lost.returncode == 0 and "You did not reach the goal." in lost.stdout


def test_a_human_is_psychic_in_odd_rounds_and_guesser_in_even_rounds() -> None:
    # round 1 clue, 2 guess, 3 clue, 4 guess, 5 clue, 6 guess
    stdin = "a lazy afternoon\n50\nsomething cosy\n50\nbrisk and bright\n50\n"
    result = run(
        [*PLAY, "--config", "seed=5", "--seat", "you=human", "--seat", "bot=bot:wl-random"],
        stdin,
    )

    assert result.returncode == 0, result.stderr
    rows = recap_rows(result.stdout)
    assert [r[1] for r in rows] == ["you", "bot", "you", "bot", "you", "bot"]


def test_a_json_match_never_shows_the_guesser_the_target_in_any_round() -> None:
    stdin = "a lazy afternoon\n50\nsomething cosy\n50\nbrisk and bright\n50\n"
    result = run(
        [
            *PLAY,
            "--config",
            "seed=5",
            "--seat",
            "you=human",
            "--seat",
            "bot=bot:wl-random",
            "--json",
        ],
        stdin,
    )

    assert result.returncode == 0, result.stderr
    events: list[dict[str, Any]] = [
        json.loads(line[line.index('{"type"') :])
        for line in result.stdout.splitlines()
        if '{"type"' in line
    ]
    states = [e["state"] for e in events if e["type"] in ("turn", "result")]
    guesser_views = [s for s in states if s.get("role") == "guesser"]
    assert len(guesser_views) >= 3  # the human really was the guesser in some rounds
    assert all("target" not in s for s in guesser_views)
    assert all("plan" not in s for s in states)
    # and the finished match reports a verdict
    assert events[-1]["type"] == "result"
