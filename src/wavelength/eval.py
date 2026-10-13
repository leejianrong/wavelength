"""Manual LLM evaluation: two seats play a long match and we report points per
round against what a uniformly random guesser would score (QUESTIONS Q19).

``python -m wavelength.eval --model A --model2 B`` calls the real OpenRouter API
(needs ``OPENROUTER_API_KEY``) and costs money, so it is a local ``make``
target and never part of CI. ``run_eval`` takes any two seats, which is what
the tests exercise.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

from agent_game_framework.core import AgentTimeoutError, Match, SeatController

from wavelength.engine import DEFAULT_BANDS, WavelengthEngine, score_guess
from wavelength.seats import guard


def random_baseline() -> float:
    """Mean points per round of a uniformly random guesser, computed exactly
    over every (guess, target) pair."""
    cells = [(g, t) for g in range(101) for t in range(101)]
    return sum(score_guess(g, t, DEFAULT_BANDS) for g, t in cells) / len(cells)


@dataclass(frozen=True)
class EvalResult:
    rounds_requested: int
    rounds_played: int
    total_points: int
    bullseyes: int
    error: str | None

    @property
    def mean(self) -> float:
        return self.total_points / self.rounds_played if self.rounds_played else 0.0

    def report(self) -> str:
        base = random_baseline()
        lines = [
            f"rounds played: {self.rounds_played}/{self.rounds_requested}",
            f"points per round: {self.mean:.2f}  (uniform-random guesser: {base:.2f})",
            f"bullseyes: {self.bullseyes}",
        ]
        if self.error:
            lines.append(f"stopped early: {self.error}")
        return "\n".join(lines)


def run_eval(
    first: SeatController[Any, Any],
    second: SeatController[Any, Any],
    *,
    rounds: int = 30,
    seed: int = 1,
) -> EvalResult:
    """Play ``rounds`` rounds, each seat psychic for every other round. A seat
    that fails ends the run early; what was played is still reported."""
    match: Match[Any, Any, Any] = Match(
        WavelengthEngine(),
        players=["first", "second"],
        config={"rounds": rounds, "seed": seed},
        seats={"first": first, "second": second},
    )
    error: str | None = None
    try:
        match.run_to_completion()
    except AgentTimeoutError as exc:
        error = str(exc)
    history = match.observation_for("first")["history"]
    bands_top = DEFAULT_BANDS[0][1]
    return EvalResult(
        rounds_requested=rounds,
        rounds_played=len(history),
        total_points=sum(r["points"] for r in history),
        bullseyes=sum(1 for r in history if r["points"] == bands_top),
        error=error,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wavelength.eval", description=__doc__)
    parser.add_argument("--model", required=True, help="OpenRouter slug for the first seat")
    parser.add_argument("--model2", help="slug for the second seat (default: same as --model)")
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)

    from agent_game_framework.agents import OpenRouterBackend

    try:
        first = guard(OpenRouterBackend(model=args.model))
        second = guard(OpenRouterBackend(model=args.model2 or args.model))
    except ValueError as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    print(f"{args.model} vs {args.model2 or args.model}, {args.rounds} rounds, seed {args.seed}")
    result = run_eval(first, second, rounds=args.rounds, seed=args.seed)
    print(result.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
