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


MAX_REACTION_WORDS = 25


def reaction_prompt(reveal: dict[str, Any], notes: str | None) -> str:
    """Asked of an AI psychic once, after the reveal. Everything here is public by then (the
    target, the guess, the points); the notes are the seat's own and go back to the same model."""
    spectrum = reveal.get("spectrum") or {}
    lines = [
        "The round is over. Here is what happened:",
        f"- The dial ran from 0 = {spectrum.get('left')} to 100 = {spectrum.get('right')}.",
        f"- Your clue was: {reveal.get('clue')!r}.",
        f"- The target was {reveal.get('target')}. Your partner guessed {reveal.get('guess')} "
        f"and scored {reveal.get('points')} points.",
    ]
    if notes:
        lines.append(f"- Your own notes from before the clue:\n{notes}")
    lines.append(
        f"React out loud in one short line, at most {MAX_REACTION_WORDS} words, as you would "
        "to your partner: pleased, rueful, teasing, whatever fits. Answer with the line only."
    )
    return "\n".join(lines)


def reaction_line(raw: str) -> str:
    """The reply cut to one line of at most ``MAX_REACTION_WORDS`` words."""
    words = raw.strip().strip("\"'").split()
    return " ".join(words[:MAX_REACTION_WORDS])


MAX_NEEDLE_STEPS = 4

NEEDLE_PROTOCOL = """\
You are the guesser, and you will work the dial's needle the way a person does: think aloud, \
move the needle, ask whether to nudge it from where it is, and lock it in when you are satisfied.

Each time, reply with one JSON object and nothing else:
{"say": "<one or two sentences, out loud: what you make of the clue, why you move the needle, \
or what you are weighing>", "needle": <whole number 0-100>, "lock": <true or false>}

How to think:
1. First say what the clue literally means and which end of the dial it points toward, then \
put the needle at a first guess.
2. After each move, look at where the needle is. Ask what the giver could have said instead (a \
stronger or weaker clue) and what that tells you about where the target is not. Treat a modifier \
("a little", "after one glass") as deliberate: move by it.
3. If past rounds are listed, compare your earlier guesses with their targets and correct for \
the way you tend to miss.
4. Nudge the needle only for a reason you can say. When another nudge would only be fiddling, \
set "lock" to true. Locking is final: "needle" is your guess."""


def needle_first_prompt(observation: dict[str, Any]) -> str:
    return (
        f"{NEEDLE_PROTOCOL}\n\nThe situation:\n{thinking_context('guesser', observation)}\n\n"
        f"You may take up to {MAX_NEEDLE_STEPS} steps. Make your first move."
    )


def needle_next_prompt(needle: int, last: bool) -> str:
    where = f"The needle is at {needle}."
    if last:
        return f'{where} This is your last step: set "lock" to true and give your final number.'
    return f'{where} Nudge it, or lock it in with "lock": true.'
