"""Manual LLM evaluation: two seats play a long match and we report points per
round against what a uniformly random guesser would score (QUESTIONS Q19).

``python -m wavelength.eval --model A --model2 B`` calls the real OpenRouter API
(needs ``OPENROUTER_API_KEY``) and costs money, so it is a local ``make``
target and never part of CI. ``run_eval`` takes any two seats, which is what
the tests exercise.

Besides points it reports what the guard saw: model calls, clue attempts the
rules rejected, guesses that arrived as something other than a plain int, and
moves the engine refused. ``--max-calls`` is a hard cap on model calls (the
framework does not expose token usage, so there is no spend cap; calls are the
bound). A run that hits the cap, a guard limit or a failing model stops and
still reports what was played.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

from agent_game_framework.core import (
    AgentTimeoutError,
    Conversable,
    ConversationInput,
    ConversationTurn,
    Match,
    SeatController,
    SeatDecision,
    is_free_text,
)

from wavelength.clue_rules import clue_problem
from wavelength.deck import Spectrum
from wavelength.engine import DEFAULT_BANDS, WavelengthEngine, score_guess
from wavelength.seats import guard, normalize_clue

MAX_ILLEGAL_STREAK = 5


def random_baseline() -> float:
    """Mean points per round of a uniformly random guesser, computed exactly
    over every (guess, target) pair."""
    cells = [(g, t) for g in range(101) for t in range(101)]
    return sum(score_guess(g, t, DEFAULT_BANDS) for g, t in cells) / len(cells)


class CallCapExceeded(Exception):
    """The run asked the model for more calls than ``--max-calls`` allows."""


@dataclass
class Meter:
    """Counts what a seat's model is asked and what it answers. Shared by both
    seats so ``max_calls`` bounds the whole run."""

    max_calls: int | None = None
    calls: int = 0
    clue_calls: int = 0
    guess_calls: int = 0
    clue_rejections: int = 0  # clue attempts the rules refused (the guard re-asks)
    guess_not_int: int = 0  # guesses that were not a plain legal int (coerced or refused)
    capped: bool = False


class MeteredSeat:
    """Wrap a raw seat (inside ``guard``) so every model call is counted."""

    def __init__(self, inner: SeatController[Any, Any], meter: Meter) -> None:
        self._inner = inner
        self._meter = meter

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        m = self._meter
        if m.max_calls is not None and m.calls >= m.max_calls:
            m.capped = True
            raise CallCapExceeded(f"call cap of {m.max_calls} reached")
        m.calls += 1
        decision = self._inner.decide(observation, legal_actions)
        if is_free_text(legal_actions) is not None:
            m.clue_calls += 1
            spectrum = Spectrum(**observation["spectrum"])
            if clue_problem(normalize_clue(decision.action), spectrum):
                m.clue_rejections += 1
        else:
            m.guess_calls += 1
            action = decision.action
            if type(action) is not int or action not in legal_actions:
                m.guess_not_int += 1
        return decision


class MeteredConversableSeat(MeteredSeat):
    """``MeteredSeat`` for a chat-capable seat: a chat reply is a model call too, so it counts
    against the same cap. A separate class because ``Conversable`` is checked by attribute, and
    a seat that cannot chat must not look as if it can (see ``seats.guard``)."""

    def respond(self, history: list[ConversationTurn], incoming: ConversationInput) -> Any:
        m = self._meter
        if m.max_calls is not None and m.calls >= m.max_calls:
            m.capped = True
            raise CallCapExceeded(f"call cap of {m.max_calls} reached")
        m.calls += 1
        return self._inner.respond(history, incoming)  # type: ignore[attr-defined]


def metered(inner: SeatController[Any, Any], meter: Meter) -> SeatController[Any, Any]:
    if isinstance(inner, Conversable):
        return MeteredConversableSeat(inner, meter)
    return MeteredSeat(inner, meter)


@dataclass(frozen=True)
class EvalResult:
    rounds_requested: int
    rounds_played: int
    total_points: int
    bullseyes: int
    error: str | None
    calls: int = 0
    clue_calls: int = 0
    guess_calls: int = 0
    clue_rejections: int = 0
    guess_not_int: int = 0
    illegal_moves: int = 0  # moves the engine refused and the run asked for again
    rows: tuple[dict[str, Any], ...] = ()

    @property
    def mean(self) -> float:
        return self.total_points / self.rounds_played if self.rounds_played else 0.0

    @staticmethod
    def combine(results: list[EvalResult]) -> EvalResult:
        return EvalResult(
            rounds_requested=sum(r.rounds_requested for r in results),
            rounds_played=sum(r.rounds_played for r in results),
            total_points=sum(r.total_points for r in results),
            bullseyes=sum(r.bullseyes for r in results),
            error=next((r.error for r in results if r.error), None),
            calls=sum(r.calls for r in results),
            clue_calls=sum(r.clue_calls for r in results),
            guess_calls=sum(r.guess_calls for r in results),
            clue_rejections=sum(r.clue_rejections for r in results),
            guess_not_int=sum(r.guess_not_int for r in results),
            illegal_moves=sum(r.illegal_moves for r in results),
            rows=tuple(row for r in results for row in r.rows),
        )

    def report(self, table: bool = False) -> str:
        base = random_baseline()
        lines = [
            f"rounds played: {self.rounds_played}/{self.rounds_requested}",
            f"points per round: {self.mean:.2f}  (uniform-random guesser: {base:.2f})",
            f"bullseyes: {self.bullseyes}",
            f"model calls: {self.calls} (clue {self.clue_calls}, guess {self.guess_calls})",
            f"clue attempts rejected by the rules: {self.clue_rejections}",
            f"guesses not sent as a plain int: {self.guess_not_int}",
            f"moves the engine refused: {self.illegal_moves}",
        ]
        if self.error:
            lines.append(f"stopped early: {self.error}")
        if table and self.rows:
            lines.append("seed round psychic  target guess pts  clue")
            for r in self.rows:
                lines.append(
                    f"{r['seed']:>4} {r['round']:>5} {r['psychic']:<8} {r['target']:>6} "
                    f"{r['guess']:>5} {r['points']:>3}  {r['clue']}"
                )
        return "\n".join(lines)


def run_eval(
    first: SeatController[Any, Any],
    second: SeatController[Any, Any],
    *,
    rounds: int = 30,
    seed: int = 1,
    meter: Meter | None = None,
) -> EvalResult:
    """Play ``rounds`` rounds, each seat psychic for every other round. A seat
    that fails, a call cap, or ``MAX_ILLEGAL_STREAK`` refused moves in a row
    ends the run early; what was played is still reported. ``meter`` is the
    one the seats were wrapped with, read here for the counts."""
    match: Match[Any, Any, Any] = Match(
        WavelengthEngine(),
        players=["first", "second"],
        config={"rounds": rounds, "seed": seed},
        seats={"first": first, "second": second},
    )
    error: str | None = None
    illegal = 0
    streak = 0

    def on_illegal(player: str, decision: SeatDecision[Any], exc: Exception) -> None:
        nonlocal illegal, streak
        illegal += 1
        streak += 1
        if streak >= MAX_ILLEGAL_STREAK:
            raise AgentTimeoutError(
                f"{player} gave {streak} refused moves in a row; last: {exc}"
            ) from exc

    def on_turn(player: str, decision: SeatDecision[Any]) -> None:
        nonlocal streak
        streak = 0

    before = Meter() if meter is None else Meter(**vars(meter))
    try:
        match.run_to_completion(on_illegal_action=on_illegal, on_turn=on_turn)
    except AgentTimeoutError as exc:
        cause = exc.__cause__
        error = f"call cap reached ({cause})" if isinstance(cause, CallCapExceeded) else str(exc)
    history = match.observation_for("first")["history"]
    bands_top = DEFAULT_BANDS[0][1]
    now = meter or Meter()
    return EvalResult(
        rounds_requested=rounds,
        rounds_played=len(history),
        total_points=sum(r["points"] for r in history),
        bullseyes=sum(1 for r in history if r["points"] == bands_top),
        error=error,
        calls=now.calls - before.calls,
        clue_calls=now.clue_calls - before.clue_calls,
        guess_calls=now.guess_calls - before.guess_calls,
        clue_rejections=now.clue_rejections - before.clue_rejections,
        guess_not_int=now.guess_not_int - before.guess_not_int,
        illegal_moves=illegal,
        rows=tuple({"seed": seed, **r} for r in history),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wavelength.eval", description=__doc__)
    parser.add_argument("--model", required=True, help="OpenRouter slug for the first seat")
    parser.add_argument("--model2", help="slug for the second seat (default: same as --model)")
    parser.add_argument("--rounds", type=int, default=30, help="rounds per match")
    parser.add_argument("--seed", type=int, default=1, help="first seed")
    parser.add_argument("--seeds", type=int, default=1, help="matches to play (seed, seed+1, ...)")
    parser.add_argument(
        "--max-calls", type=int, default=400, help="hard cap on model calls for the whole run"
    )
    parser.add_argument("--table", action="store_true", help="print every round")
    args = parser.parse_args(argv)
    if args.rounds < 1 or args.seeds < 1 or args.max_calls < 1:
        print("--rounds, --seeds and --max-calls must be at least 1", file=sys.stderr)
        return 2

    from agent_game_framework.agents import OpenRouterBackend

    meter = Meter(max_calls=args.max_calls)
    try:
        first = guard(MeteredSeat(OpenRouterBackend(model=args.model), meter))
        second = guard(MeteredSeat(OpenRouterBackend(model=args.model2 or args.model), meter))
    except ValueError as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    print(
        f"{args.model} vs {args.model2 or args.model}, {args.rounds} rounds x {args.seeds} "
        f"match(es) from seed {args.seed}, at most {args.max_calls} model calls"
    )
    results: list[EvalResult] = []
    for seed in range(args.seed, args.seed + args.seeds):
        result = run_eval(first, second, rounds=args.rounds, seed=seed, meter=meter)
        results.append(result)
        if meter.capped:
            break
    print(EvalResult.combine(results).report(table=args.table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
