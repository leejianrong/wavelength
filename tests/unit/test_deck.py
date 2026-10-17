from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wavelength.bots import STOCK_CLUES
from wavelength.clue_rules import clue_problem
from wavelength.deck import load_deck, parse_deck


def _deck(*pairs: tuple[str, str], fmt: int = 1) -> dict[str, Any]:
    return {"format": fmt, "spectra": [{"left": a, "right": b} for a, b in pairs]}


def test_bundled_deck_is_valid_and_big_enough() -> None:
    deck = load_deck()
    assert len(deck) >= 60


def test_every_stock_clue_is_usable_on_some_bundled_spectrum() -> None:
    deck = load_deck()
    assert all(any(clue_problem(c, s) is None for s in deck) for c in STOCK_CLUES)
    # and the bot always has a valid clue for every bundled spectrum
    assert all(any(clue_problem(c, s) is None for c in STOCK_CLUES) for s in deck)


def test_duplicate_spectrum_is_rejected_even_when_flipped() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        parse_deck(_deck(("Cold", "Hot"), ("hot", "COLD")))


@pytest.mark.parametrize(
    "data",
    [
        _deck(("Cold", "Hot"), fmt=2),
        {"format": 1, "spectra": []},
        {"format": 1},
        _deck(("", "Hot")),
        _deck(("Cold", "  ")),
        {"format": 1, "spectra": [{"left": "Cold"}]},
        {"format": 1, "spectra": ["Cold/Hot"]},
        "not an object",
    ],
)
def test_malformed_decks_are_rejected(data: Any) -> None:
    with pytest.raises(ValueError):
        parse_deck(data)


def test_load_deck_from_a_file_and_errors(tmp_path: Path) -> None:
    good = tmp_path / "deck.json"
    good.write_text(json.dumps(_deck(("Cold", "Hot"))))
    assert [s.left for s in load_deck(good)] == ["Cold"]

    with pytest.raises(ValueError, match="cannot read"):
        load_deck(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_deck(bad)
