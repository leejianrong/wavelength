from pathlib import Path
from typing import Any

import pytest

from wavelength.players import PlayersError, find_player, load_players, parse_players
from wavelength.web.moves import MoveRejected
from wavelength.web.seatspec import parse_seat, parse_seat_flag

GOOD = {"name": "Dry", "model": "a/b", "personality": "Be dry."}


def test_the_example_file_loads_with_two_different_players() -> None:
    players = load_players(Path(__file__).parents[2] / "players.example.toml")
    assert [p.name for p in players] == ["Dry Sceptic", "Bright Optimist"]
    assert players[0].personality != players[1].personality


def test_a_player_is_found_by_name_ignoring_case_and_padding() -> None:
    players = parse_players({"player": [GOOD]})
    assert find_player(players, "  dry ") == players[0]
    assert find_player(players, "other") is None


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"colour": "red"}, "unknown field"),
        ({"name": None}, "'name'"),
        ({"name": "  "}, "'name'"),
        ({"name": "x" * 25}, "longer than 24"),
        ({"model": None}, "'model'"),
        ({"model": "gpt"}, "provider/model"),
        ({"personality": None}, "'personality'"),
        ({"personality": "x" * 1201}, "longer than 1200"),
    ],
)
def test_a_bad_player_is_rejected_with_a_reason(change: dict[str, Any], match: str) -> None:
    item = {**GOOD, **change}
    item = {k: v for k, v in item.items() if v is not None}
    with pytest.raises(PlayersError, match=match):
        parse_players({"player": [item]})


@pytest.mark.parametrize("data", [{}, {"player": []}, {"player": ["x"]}, []])
def test_a_file_without_players_is_rejected(data: Any) -> None:
    with pytest.raises(PlayersError):
        parse_players(data)


def test_two_players_may_not_share_a_name() -> None:
    with pytest.raises(PlayersError, match="twice"):
        parse_players({"player": [GOOD, {**GOOD, "name": "DRY"}]})


def test_bad_toml_and_a_missing_file_are_reported_not_raised_raw(tmp_path: Path) -> None:
    bad = tmp_path / "p.toml"
    bad.write_text("[[player")
    with pytest.raises(PlayersError, match="not valid TOML"):
        load_players(bad)
    with pytest.raises(PlayersError, match="cannot read"):
        load_players(tmp_path / "missing.toml")


def test_a_seat_can_name_a_player_and_gets_its_model_and_personality() -> None:
    players = parse_players({"player": [GOOD]})
    spec = parse_seat({"kind": "llm", "player": "dry"}, "x/default", players)
    assert (spec.model, spec.name, spec.personality) == ("a/b", "Dry", "Be dry.")
    assert parse_seat_flag("llm:player/Dry", "x/default", players) == spec
    with pytest.raises(MoveRejected, match="not in the players file"):
        parse_seat({"kind": "llm", "player": "Nobody"}, "x/default", players)
    with pytest.raises(MoveRejected, match="not in the players file"):
        parse_seat({"kind": "llm", "player": "Dry"}, "x/default")  # no file loaded


def test_a_plain_model_seat_has_no_personality() -> None:
    spec = parse_seat({"kind": "llm", "model": "a/b"}, "x/default")
    assert spec.name is None and spec.personality is None
