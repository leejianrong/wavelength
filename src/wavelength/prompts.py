"""What a player is asked to think about before a move (V12, ADR-0010).

The checklists come from Jian's own worked examples (2026-10-18): how a good psychic picks a
clue, and how a good guesser reads one. They are plain text and deterministic, so they are
unit tested and can be changed without touching the game.

``thinking_context`` is an allow-list over the seat's *own* observation: what it may know, and
nothing a guesser must not (a guesser's observation has no target to copy).
"""

from __future__ import annotations

import json
from typing import Any

MAX_NOTES_CHARS = 1500

PSYCHIC_CHECKLIST = """\
You are the psychic. Before you give your clue, think it through in short notes:
1. Place the target in plain words: where does it sit between the two ends (near an end, a little \
off the middle, the middle)?
2. Brainstorm three or four candidate clues. Include at least one that sits near each end, so you \
have seen the whole range. Prefer concrete things an ordinary person already ranks on this scale.
3. For each candidate ask: what other positions could the same clue fit? Drop any that fit two \
places far apart (a clue that could mean "halfway" or "all the way" is a bad clue).
4. To hit a point near an end, take something that sits at that end and add a small modifier that \
pulls it off the end; the size of the modifier is the distance. To hit the middle, choose a clue \
that holds both ends at once (a journey, a trade-off, a contradiction).
5. Imagine a stranger who knows only your clue. What do they think of first? If that lands far \
from the target, change the clue. Consider what they will remember most, not what you know.
6. Check the rules: one to six words; no digits or number words; none of left, right, middle, \
center, halfway, half, percent, dial, target; none of the spectrum's own words.
7. If past rounds are listed, see how your partner read your earlier clues and adjust for it.
Write your notes in under 200 words as plain text. End with the clue you will give. Do not \
answer with anything else."""

GUESSER_CHECKLIST = """\
You are the guesser. Before you guess, think it through in short notes:
1. Say what the clue literally means and which end of this spectrum it points toward.
2. Ask what the giver could have said instead (a stronger clue, a weaker one) and what that tells \
you about where the target is not.
3. Treat any modifier ("a little", "after one glass", "or two") as deliberate: the giver added it \
to move off the obvious end. Move by it. Do not talk yourself out of it with real-world sense.
4. If the clue holds both ends at once, expect the middle. For a famous thing, remember what \
stands out first about it, then correct for any modifier.
5. If past rounds are listed, compare your earlier guesses with their targets: do you stay too \
near the middle, or too near the ends? Correct for it.
6. Name your best number, and which direction you are more afraid of being wrong in.
Write your notes in under 200 words as plain text. End with your number. Do not answer with \
anything else."""


def thinking_context(role: str, observation: dict[str, Any]) -> str:
    """The seat's own situation as JSON, from an allow-list of its own observation."""
    spectrum = observation.get("spectrum") or {}
    context: dict[str, Any] = {
        "role": role,
        "round": observation.get("round"),
        "of_rounds": observation.get("rounds"),
        "dial": {"0": spectrum.get("left"), "100": spectrum.get("right")},
        "score": observation.get("total_score"),
    }
    if role == "psychic" and observation.get("target") is not None:
        context["target"] = observation["target"]
    if role == "guesser" and observation.get("clue"):
        context["clue"] = observation["clue"]
    past = [
        {k: r.get(k) for k in ("round", "clue", "guess", "target", "points")}
        for r in observation.get("history") or []
    ]
    if past:
        context["past_rounds"] = past
    return json.dumps(context, ensure_ascii=False)


def thinking_prompt(role: str, observation: dict[str, Any]) -> str:
    checklist = PSYCHIC_CHECKLIST if role == "psychic" else GUESSER_CHECKLIST
    return f"{checklist}\n\nThe situation:\n{thinking_context(role, observation)}"
