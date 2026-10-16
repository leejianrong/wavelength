"""Each clue rule (ADR-0004) rejects what it says it rejects, with a reason."""

from __future__ import annotations

import pytest

from wavelength.clue_rules import MAX_CHARS, clue_problem
from wavelength.deck import Spectrum

HOT_COLD = Spectrum("Cold", "Hot")
MOVIES = Spectrum("Bad movie", "Good movie")


@pytest.mark.parametrize("clue", ["a cup of tea", "lukewarm", "  padded clue  ", "Sunday morning"])
def test_fair_clues_are_accepted(clue: str) -> None:
    assert clue_problem(clue, HOT_COLD) is None


@pytest.mark.parametrize(
    ("clue", "fragment"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("two\nlines", "single line"),
        ("one two three four five six seven", "7 words"),
        ("x" * (MAX_CHARS + 1), "characters"),
        ("about 70 ish", "digits"),
        ("seventy ish", "numbers"),
        ("Fifty fifty", "numbers"),
        ("left of centre", "left"),
        ("dead MIDDLE", "middle"),
        ("halfway there", "halfway"),
        ("near the target", "target"),
        ("so cold", "spectrum's own words"),
        ("HOT stuff", "spectrum's own words"),
    ],
)
def test_each_rule_rejects_with_its_reason(clue: str, fragment: str) -> None:
    problem = clue_problem(clue, HOT_COLD)
    assert problem is not None
    assert fragment in problem


def test_endpoint_words_come_from_the_current_spectrum_only() -> None:
    assert clue_problem("a good time", HOT_COLD) is None
    assert "good" in (clue_problem("a good time", MOVIES) or "")


def test_short_label_words_do_not_block_common_words() -> None:
    assert clue_problem("a lot of fun", Spectrum("Work of art", "Waste of time")) is None


def test_non_text_is_rejected() -> None:
    assert clue_problem(7, HOT_COLD) is not None
    assert clue_problem(None, HOT_COLD) is not None


def test_a_zone_name_is_not_a_clue_because_the_guesser_can_see_them() -> None:
    zoned = Spectrum(
        "Quiet", "Loud", ("Silent", "Hushed", "Soft-spoken", "Noticeable", "Rowdy", "Deafening")
    )
    assert "zone name" in (clue_problem("deafening", zoned) or "")
    assert "'Deafening'" in (clue_problem("pretty DEAFENING stuff", zoned) or "")
    assert clue_problem("a jet taking off", zoned) is None
    assert clue_problem("rowdy football crowd", zoned) is not None  # a one-word zone, whole word
    assert clue_problem("rowdyish", zoned) is None  # only whole words count
    assert clue_problem("a soft spoken librarian", zoned) is not None  # the whole phrase
    assert clue_problem("a soft pillow", zoned) is None  # half of a phrase is fine
