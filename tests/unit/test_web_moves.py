"""What the browser may send is checked before the engine sees it."""

from __future__ import annotations

from typing import Any

import pytest

from wavelength.web.moves import MAX_CLUE_CHARS, Move, MoveRejected, parse_move


def test_a_clue_and_a_guess_are_parsed() -> None:
    assert parse_move({"type": "clue", "text": "a lazy afternoon"}) == Move(
        "clue", "a lazy afternoon"
    )
    assert parse_move({"type": "guess", "value": 40}) == Move("guess", 40)
    assert parse_move({"type": "guess", "value": 0}) == Move("guess", 0)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "clue",
        {},
        {"type": "chat", "text": "hi"},
        {"type": "clue"},
        {"type": "clue", "text": ""},
        {"type": "clue", "text": "   "},
        {"type": "clue", "text": 7},
        {"type": "clue", "text": "x" * (MAX_CLUE_CHARS + 1)},
        {"type": "guess"},
        {"type": "guess", "value": "40"},
        {"type": "guess", "value": 40.0},
        {"type": "guess", "value": True},
        {"type": "guess", "value": None},
    ],
)
def test_anything_else_is_rejected_with_a_readable_reason(payload: Any) -> None:
    with pytest.raises(MoveRejected) as excinfo:
        parse_move(payload)
    assert str(excinfo.value)


def test_the_engine_not_the_parser_judges_range_and_clue_rules() -> None:
    assert parse_move({"type": "guess", "value": 500}) == Move("guess", 500)
    assert parse_move({"type": "clue", "text": "about 70"}).value == "about 70"
