"""``bot:wl-random``: a scripted seat for both roles, for tests and demos.

As psychic it gives the first stock clue that is valid for the current spectrum
(it ignores the target, so it is a poor psychic by design); as guesser it
guesses uniformly at random. It is *not* a baseline for LLM quality beyond
"better than random": its clues carry no information (QUESTIONS Q17).
"""

from __future__ import annotations

import random
from typing import Any

from agent_game_framework.core import SeatDecision, is_free_text

from wavelength.clue_rules import clue_problem
from wavelength.deck import Spectrum

STOCK_CLUES = (
    "hard to say",
    "depends who you ask",
    "pretty typical",
    "somewhere in between",
    "a classic example",
    "my gut feeling",
)


class RandomWavelengthBot:
    def __init__(self, rng: random.Random | None = None) -> None:
        """With no ``rng`` the guess is derived from the observation (round,
        spectrum, clue), so a seeded match replays identically (R4)."""
        self._rng = rng

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        if is_free_text(legal_actions) is not None:
            spectrum = Spectrum(**observation["spectrum"])
            for clue in STOCK_CLUES:
                if clue_problem(clue, spectrum) is None:
                    return SeatDecision(action=clue, banter=None)
            raise RuntimeError("no stock clue is valid for this spectrum")
        rng = self._rng
        if rng is None:
            key = (observation.get("round"), observation.get("spectrum"), observation.get("clue"))
            rng = random.Random(repr(key))
        return SeatDecision(action=rng.choice(legal_actions), banter=None)
