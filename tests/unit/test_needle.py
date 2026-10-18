from __future__ import annotations

import pytest

from wavelength.needle import MAX_THOUGHTS_CHARS, public_thoughts, walk
from wavelength.prompts import MAX_REACTION_WORDS, reaction_line, reaction_prompt


@pytest.mark.parametrize("final", [0, 3, 22, 50, 81, 100])
def test_a_walk_is_on_the_dial_never_the_final_and_never_repeats(final: int) -> None:
    for round_no in range(1, 12):
        points = walk(final, round_no, seed=7)
        assert len(points) <= 3
        assert all(0 <= p <= 100 for p in points)
        assert final not in points
        assert all(a != b for a, b in zip([50, *points], points, strict=False))


def test_a_walk_is_fixed_by_the_final_guess_the_round_and_the_seed() -> None:
    assert walk(22, 3, 9) == walk(22, 3, 9)
    assert walk(22, 3, 9) != walk(22, 4, 9) or walk(22, 3, 9) != walk(22, 3, 10)


def test_a_walk_toward_a_guess_in_the_middle_can_be_empty_but_never_fails() -> None:
    assert isinstance(walk(50, 1, 1), list)


def test_thoughts_are_cut_at_a_sentence_when_one_ends_in_range() -> None:
    long = "It sounds warm. " * 40
    out = public_thoughts(long)
    assert len(out) <= MAX_THOUGHTS_CHARS and out.endswith(".")


def test_thoughts_with_no_sentence_end_are_cut_at_a_word() -> None:
    out = public_thoughts("word " * 200)
    assert out.endswith("…") and len(out) <= MAX_THOUGHTS_CHARS + 1


def test_short_thoughts_pass_through_with_whitespace_collapsed() -> None:
    assert public_thoughts("  a\n b  ") == "a b"


def test_the_reaction_prompt_holds_only_the_public_result_and_its_own_notes() -> None:
    reveal = {
        "round": 1,
        "psychic": "ai-1",
        "spectrum": {"left": "Smooth", "right": "Bumpy"},
        "clue": "a gravel road",
        "guess": 70,
        "target": 64,
        "points": 3,
    }
    text = reaction_prompt(reveal, "my notes")
    assert "64" in text and "70" in text and "3 points" in text and "my notes" in text
    assert "my notes" not in reaction_prompt(reveal, None)


def test_a_reaction_line_is_trimmed_to_a_short_line() -> None:
    assert len(reaction_line("word " * 100).split()) == MAX_REACTION_WORDS
    assert reaction_line('  "Nice one!"  ') == "Nice one!"
