"""What V13 shows of the guesser's thinking, as pure functions (ADR-0011).

``walk`` is the needle's path to a guess an AI has already made: a few tentative positions,
fixed by the final guess, the round and the seed. It adds no information and calls no model, so
it is a presentation of a public number (V15 replaces it with steps the model takes itself).
"""

from __future__ import annotations

import random
import re

DIAL_MIN, DIAL_MAX = 0, 100
START = 50
MAX_THOUGHTS_CHARS = 280


def walk(final: int, round_no: int, seed: int, steps: int = 3) -> list[int]:
    """Up to ``steps`` tentative positions from the middle toward ``final``, the last of them
    short of it. Never contains ``final`` itself and never the same number twice in a row."""
    rng = random.Random(f"{seed}:{round_no}:{final}")
    gap = final - START
    fractions = [0.55, 1.15, 0.9][:steps]
    points: list[int] = []
    previous = START
    for fraction in fractions:
        value = round(START + gap * fraction + rng.uniform(-6, 6))
        value = max(DIAL_MIN, min(DIAL_MAX, value))
        if value not in (previous, final):
            points.append(value)
            previous = value
    return points


_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def public_thoughts(notes: str, limit: int = MAX_THOUGHTS_CHARS) -> str:
    """A guesser's notes cut for a subtitle: whitespace collapsed, ended at a sentence when one
    ends within ``limit``, otherwise at a word with an ellipsis."""
    text = " ".join(notes.split())
    if len(text) <= limit:
        return text
    head = text[:limit]
    ends = [m.end() for m in _SENTENCE_END.finditer(head)]
    if ends and ends[-1] >= limit // 2:
        return head[: ends[-1]]
    return head.rsplit(" ", 1)[0].rstrip(",;:") + "…"
