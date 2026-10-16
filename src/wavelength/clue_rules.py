"""Deterministic clue validation (ADR-0004).

Only the mechanical part of the rule "do not give away the position" is
enforced; whether a clue is *fair* is not judged. Every rejection names the
rule so an LLM can fix it on the framework's one retry.
"""

from __future__ import annotations

import re

from wavelength.deck import Spectrum

MAX_WORDS = 6
MAX_CHARS = 80

POSITION_WORDS = frozenset(
    {"left", "right", "middle", "center", "centre", "halfway", "half", "percent", "dial", "target"}
)
NUMBER_WORDS = frozenset(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy "
    "eighty ninety hundred".split()
)
_IGNORED_LABEL_WORDS = frozenset({"the", "and", "for", "not", "with", "than"})
_TOKEN = re.compile(r"[a-z']+")


def _words(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _label_words(spectrum: Spectrum) -> set[str]:
    return {
        w
        for label in (spectrum.left, spectrum.right)
        for w in _words(label)
        if len(w) > 2 and w not in _IGNORED_LABEL_WORDS
    }


def _zone_used(words: list[str], spectrum: Spectrum) -> str | None:
    """A zone name the clue contains: the word for a one-word name, the whole phrase otherwise."""
    for name in spectrum.regions:
        needle = _words(name)
        if needle and any(
            words[i : i + len(needle)] == needle for i in range(len(words) - len(needle) + 1)
        ):
            return name
    return None


def clue_problem(clue: object, spectrum: Spectrum) -> str | None:
    """Why ``clue`` is not allowed for ``spectrum``, or ``None`` if it is."""
    if not isinstance(clue, str):
        return f"the clue must be text, got {type(clue).__name__}"
    text = clue.strip()
    if not text:
        return "the clue is empty; give one to six words"
    if "\n" in text or "\r" in text:
        return "the clue must be a single line"
    if len(text) > MAX_CHARS:
        return f"the clue is {len(text)} characters; the limit is {MAX_CHARS}"
    tokens = text.split()
    if len(tokens) > MAX_WORDS:
        return f"the clue is {len(tokens)} words; the limit is {MAX_WORDS}"
    if any(ch.isdigit() for ch in text):
        return "the clue must not contain digits"
    words = _words(text)
    spelled = sorted(set(words) & NUMBER_WORDS)
    if spelled:
        return f"the clue must not contain numbers ({', '.join(spelled)})"
    position = sorted(set(words) & POSITION_WORDS)
    if position:
        return f"the clue must not say where the target is ({', '.join(position)})"
    used = sorted(set(words) & _label_words(spectrum))
    if used:
        return f"the clue must not use the spectrum's own words ({', '.join(used)})"
    zone = _zone_used(words, spectrum)
    if zone:
        return f"the clue must not use a zone name ('{zone}'): the guesser can see them"
    return None
