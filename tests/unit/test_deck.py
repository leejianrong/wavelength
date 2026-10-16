from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wavelength.bots import STOCK_CLUES
from wavelength.clue_rules import clue_problem
from wavelength.deck import (
    REGION_COUNT,
    Spectrum,
    generated_regions,
    load_deck,
    parse_deck,
    region_index,
)


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
        _deck(("Cold", "Hot"), fmt=3),
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


GOLDEN = json.loads((Path(__file__).parent.parent / "data" / "region_index.json").read_text())
ZONES = ["Silent", "Hushed", "Soft-spoken", "Noticeable", "Loud", "Deafening"]


def test_the_zone_of_every_dial_value_matches_the_golden_table() -> None:
    assert [region_index(v) for v in range(101)] == GOLDEN
    assert region_index(-5) == 0 and region_index(500) == REGION_COUNT - 1


def test_a_format_2_spectrum_carries_its_written_zones_in_order() -> None:
    deck = parse_deck(
        {"format": 2, "spectra": [{"left": "Quiet", "right": "Loud", "regions": ZONES}]}
    )
    spectrum = deck[0]
    assert spectrum.regions == tuple(ZONES)
    assert [spectrum.region(v) for v in (0, 16, 17, 49, 50, 83, 84, 100)] == [
        "Silent", "Silent", "Hushed", "Soft-spoken", "Noticeable", "Loud", "Deafening", "Deafening",
    ]  # fmt: skip


def test_a_spectrum_without_zones_gets_generated_ones_so_it_always_has_six() -> None:
    spectrum = parse_deck(_deck(("Quiet", "Loud"), fmt=1))[0]
    assert spectrum.regions == generated_regions("Quiet", "Loud")
    assert len(spectrum.regions) == REGION_COUNT
    assert spectrum.region(0) == "Far toward Quiet" and spectrum.region(100) == "Far toward Loud"
    assert parse_deck(_deck(("Quiet", "Loud"), fmt=2))[0].regions == spectrum.regions


def test_a_spectrum_survives_the_trip_through_an_observation() -> None:
    spectrum = Spectrum("Quiet", "Loud", tuple(ZONES))
    assert Spectrum(**spectrum.to_dict()) == spectrum
    assert spectrum.to_dict()["regions"] == ZONES
    old_dump = {"left": "Quiet", "right": "Loud"}  # saved before zones existed
    assert Spectrum(**old_dump).regions == generated_regions("Quiet", "Loud")


@pytest.mark.parametrize(
    "regions",
    [
        ZONES[:5],
        [*ZONES, "Extra"],
        "Silent",
        [*ZONES[:5], ""],
        [*ZONES[:5], "   "],
        [*ZONES[:5], 7],
        [*ZONES[:5], "silent"],  # a duplicate, ignoring case
        [*ZONES[:5], "x" * 29],
    ],
)
def test_bad_zone_lists_are_rejected(regions: Any) -> None:
    deck = {"format": 2, "spectra": [{"left": "Quiet", "right": "Loud", "regions": regions}]}
    with pytest.raises(ValueError, match="regions"):
        parse_deck(deck)


def test_every_bundled_spectrum_has_six_distinct_zones_that_do_not_repeat_its_ends() -> None:
    for spectrum in load_deck():
        assert len(set(n.lower() for n in spectrum.regions)) == REGION_COUNT, spectrum
        assert all(1 <= len(n) <= 28 for n in spectrum.regions), spectrum
