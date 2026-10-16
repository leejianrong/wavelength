"""``WavelengthEngine``: cooperative two-player Wavelength as a framework
``GameEngine`` (ADR-0002, ADR-0003, ADR-0004).

Each round the *psychic* sees a hidden target on a 0-100 dial between two
opposite labels and gives a one-line clue; the *guesser* then sets the dial.
Roles alternate every round (``players[0]`` is psychic in round 1). Points are
shared; the match is won, by both players, if the total reaches
``target_score`` after the last round.

The whole round plan (spectrum and target for every round) is drawn once in
``initial_state`` from ``random.Random(seed)`` and kept in state, so the
engine is a pure function of its inputs and ``apply_action`` needs no RNG.
Only ``observation_for`` decides who may see a target; ``serialize`` is the
full save format and never a viewer format (ADR-0003).

Like every framework engine it never mutates a state it is handed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from agent_game_framework.core import FreeText, GameEngine, IllegalActionError, PlayerId

from wavelength.clue_rules import MAX_CHARS, MAX_WORDS, clue_problem
from wavelength.deck import Spectrum, load_deck

SCHEMA_VERSION = 1
DIAL_MIN = 0
DIAL_MAX = 100

DEFAULT_ROUNDS = 6
DEFAULT_TARGET_SCORE = 12
DEFAULT_BANDS: tuple[tuple[int, int], ...] = ((2, 4), (6, 3), (10, 2))
"""``(max distance, points)`` pairs, nearest first; farther than all scores 0."""

CLUE = "clue"
GUESS = "guess"

Action = str | int


@dataclass(frozen=True)
class RoundPlan:
    spectrum: Spectrum
    target: int


@dataclass(frozen=True)
class Reveal:
    """A finished round. Public once it exists, target included."""

    round: int
    psychic: PlayerId
    spectrum: Spectrum
    clue: str
    guess: int
    target: int
    points: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "psychic": self.psychic,
            "spectrum": self.spectrum.to_dict(),
            "clue": self.clue,
            "guess": self.guess,
            "target": self.target,
            "points": self.points,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Reveal:
        return Reveal(
            round=data["round"],
            psychic=data["psychic"],
            spectrum=Spectrum(**data["spectrum"]),
            clue=data["clue"],
            guess=data["guess"],
            target=data["target"],
            points=data["points"],
        )


@dataclass(frozen=True)
class WavelengthState:
    """``players`` is turn order. ``plan`` holds every round's hidden target.
    ``round_index`` is 0-based; the match is over when it reaches ``len(plan)``."""

    players: list[PlayerId]
    plan: list[RoundPlan]
    target_score: int
    bands: tuple[tuple[int, int], ...]
    round_index: int = 0
    clue: str | None = None
    history: list[Reveal] = field(default_factory=list)

    @property
    def rounds(self) -> int:
        return len(self.plan)

    @property
    def done(self) -> bool:
        return self.round_index >= len(self.plan)

    @property
    def phase(self) -> str | None:
        if self.done:
            return None
        return CLUE if self.clue is None else GUESS

    @property
    def total(self) -> int:
        return sum(r.points for r in self.history)

    def psychic(self) -> PlayerId:
        return self.players[self.round_index % 2]

    def guesser(self) -> PlayerId:
        return self.players[(self.round_index + 1) % 2]


def score_guess(guess: int, target: int, bands: tuple[tuple[int, int], ...]) -> int:
    """Points for a guess: the first band whose distance limit covers it."""
    distance = abs(guess - target)
    for limit, points in bands:
        if distance <= limit:
            return points
    return 0


def _parse_bands(raw: Any) -> tuple[tuple[int, int], ...]:
    try:
        bands = tuple((int(limit), int(points)) for limit, points in raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bands must be a list of [max_distance, points] pairs: {raw!r}") from exc
    if not bands or any(b[0] < 0 or b[1] < 0 for b in bands):
        raise ValueError(f"bands must be non-empty with non-negative numbers: {raw!r}")
    if any(a[0] >= b[0] for a, b in zip(bands, bands[1:], strict=False)):
        raise ValueError(f"bands must be ordered by increasing distance: {raw!r}")
    return bands


class WavelengthEngine:
    """The ``GameEngine`` for Wavelength. See the module docstring."""

    def initial_state(self, players: list[PlayerId], config: dict[str, Any]) -> WavelengthState:
        if len(players) != 2 or len(set(players)) != 2:
            raise ValueError(f"wavelength requires exactly 2 distinct players, got {players!r}")
        rounds = config.get("rounds", DEFAULT_ROUNDS)
        if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
            raise ValueError(f"rounds must be an int >= 1, got {rounds!r}")
        target_score = config.get("target_score", DEFAULT_TARGET_SCORE)
        if isinstance(target_score, bool) or not isinstance(target_score, int) or target_score < 0:
            raise ValueError(f"target_score must be an int >= 0, got {target_score!r}")
        bands = _parse_bands(config.get("bands", DEFAULT_BANDS))
        deck = load_deck(config.get("deck"))
        if rounds > len(deck):
            raise ValueError(f"rounds ({rounds}) exceeds the deck size ({len(deck)})")
        rng = random.Random(config.get("seed"))
        plan = [
            RoundPlan(spectrum=spectrum, target=rng.randint(DIAL_MIN, DIAL_MAX))
            for spectrum in rng.sample(deck, rounds)
        ]
        return WavelengthState(
            players=list(players), plan=plan, target_score=target_score, bands=bands
        )

    def current_players(self, state: WavelengthState) -> list[PlayerId]:
        if state.done:
            return []
        return [state.psychic() if state.phase == CLUE else state.guesser()]

    def legal_actions(self, state: WavelengthState, player: PlayerId) -> list[Any]:
        if player not in self.current_players(state):
            return []
        if state.phase == CLUE:
            return [FreeText(max_words=MAX_WORDS, max_chars=MAX_CHARS)]
        return list(range(DIAL_MIN, DIAL_MAX + 1))

    def apply_action(
        self, state: WavelengthState, player: PlayerId, action: Action
    ) -> WavelengthState:
        if player not in self.current_players(state):
            raise IllegalActionError(f"{player!r} may not act now; it is not their turn")
        current = state.plan[state.round_index]
        if state.phase == CLUE:
            problem = clue_problem(action, current.spectrum)
            if problem is not None:
                raise IllegalActionError(problem)
            assert isinstance(action, str)
            return WavelengthState(
                players=state.players,
                plan=state.plan,
                target_score=state.target_score,
                bands=state.bands,
                round_index=state.round_index,
                clue=action.strip(),
                history=state.history,
            )
        if isinstance(action, bool) or not isinstance(action, int):
            raise IllegalActionError(
                f"a guess must be a whole number {DIAL_MIN}-{DIAL_MAX}, got {action!r}"
            )
        if not DIAL_MIN <= action <= DIAL_MAX:
            raise IllegalActionError(f"a guess must be {DIAL_MIN}-{DIAL_MAX}, got {action}")
        assert state.clue is not None
        reveal = Reveal(
            round=state.round_index + 1,
            psychic=state.psychic(),
            spectrum=current.spectrum,
            clue=state.clue,
            guess=action,
            target=current.target,
            points=score_guess(action, current.target, state.bands),
        )
        return WavelengthState(
            players=state.players,
            plan=state.plan,
            target_score=state.target_score,
            bands=state.bands,
            round_index=state.round_index + 1,
            clue=None,
            history=[*state.history, reveal],
        )

    def is_terminal(self, state: WavelengthState) -> bool:
        return state.done

    def winners(self, state: WavelengthState) -> list[PlayerId]:
        if state.done and state.total >= state.target_score:
            return list(state.players)
        return []

    def observation_for(self, state: WavelengthState, player: PlayerId) -> dict[str, Any]:
        """The one place target visibility is decided (ADR-0003).

        Everyone sees finished rounds in ``history`` (target included). Only the
        current psychic also sees the *current* target; the guesser never does,
        and no observation carries the plan of rounds still to come.
        """
        obs: dict[str, Any] = {
            "you": player,
            "round": min(state.round_index + 1, state.rounds),
            "rounds": state.rounds,
            "phase": state.phase,
            "total_score": state.total,
            "target_score": state.target_score,
            "history": [r.to_dict() for r in state.history],
            "current_players": self.current_players(state),
        }
        if state.done:
            obs["role"] = None
            obs["won"] = state.total >= state.target_score
            obs["instructions"] = (
                f"The match is over: {state.total} points against a goal of {state.target_score}."
            )
            return obs
        spectrum = state.plan[state.round_index].spectrum
        obs["spectrum"] = spectrum.to_dict()
        obs["clue"] = state.clue
        if player == state.psychic():
            obs["role"] = "psychic"
            obs["target"] = state.plan[state.round_index].target
            obs["instructions"] = _psychic_instructions(spectrum, obs["target"])
        else:
            obs["role"] = "guesser"
            obs["instructions"] = _guesser_instructions(spectrum, state.clue)
        return obs

    def serialize(self, state: WavelengthState) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "players": list(state.players),
            "plan": [{"spectrum": p.spectrum.to_dict(), "target": p.target} for p in state.plan],
            "target_score": state.target_score,
            "bands": [list(b) for b in state.bands],
            "round_index": state.round_index,
            "clue": state.clue,
            "history": [r.to_dict() for r in state.history],
        }

    def deserialize(self, data: dict[str, Any]) -> WavelengthState:
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {data.get('schema_version')!r}")
        return WavelengthState(
            players=list(data["players"]),
            plan=[
                RoundPlan(spectrum=Spectrum(**p["spectrum"]), target=p["target"])
                for p in data["plan"]
            ],
            target_score=data["target_score"],
            bands=_parse_bands(data["bands"]),
            round_index=data["round_index"],
            clue=data["clue"],
            history=[Reveal.from_dict(r) for r in data["history"]],
        )


def _zones(spectrum: Spectrum) -> str:
    return "; ".join(f"{name}" for name in spectrum.regions)


def _psychic_instructions(spectrum: Spectrum, target: int) -> str:
    return (
        f"You are the psychic. The dial runs from 0 ('{spectrum.left}') to 100 "
        f"('{spectrum.right}'), in six zones from left to right: {_zones(spectrum)}. "
        f"The hidden target is {target}, in the zone '{spectrum.region(target)}'. "
        f"Give your partner a clue of "
        f"1-{MAX_WORDS} words that points at that spot between the two ends: something that "
        "sits that far along the way from one word to the other, in an ordinary person's mind. "
        "Do not use numbers, position words (left, right, middle...), the spectrum's own "
        "words, or the zone names (your partner can see them). Reply with the clue only; your "
        "banter is not shown on this turn."
    )


def _guesser_instructions(spectrum: Spectrum, clue: str | None) -> str:
    heard = f'Your partner\'s clue is: "{clue}". ' if clue else ""
    return (
        f"You are the guesser. The dial runs from 0 ('{spectrum.left}') to 100 "
        f"('{spectrum.right}'), in six zones from left to right: {_zones(spectrum)}. "
        f"Your partner, the psychic, can see a hidden target on it. "
        f"{heard}Guess a whole number from 0 to 100 for where the target is: closer scores "
        "more (within 2 points is a bullseye). Past rounds in `history` show how this "
        "partner's clues have mapped onto the dial."
    )


_: GameEngine[WavelengthState, Action, dict[str, Any]] = WavelengthEngine()
