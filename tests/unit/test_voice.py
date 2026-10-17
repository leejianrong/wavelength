from __future__ import annotations

import pytest

from wavelength.voice import hub_seat_ids, reaction_for
from wavelength.web.hub import HubError, voice_config


def test_hub_seats_follow_the_order_of_our_seats() -> None:
    assert hub_seat_ids(["you", "bot"]) == {"you": "seat-1", "bot": "seat-2"}


@pytest.mark.parametrize(
    ("points", "best", "expected"),
    [(4, 4, ("happy", "nod")), (0, 4, ("sad", "shake")), (2, 4, ("neutral", "nod"))],
)
def test_the_reaction_comes_from_the_points_alone(
    points: int, best: int, expected: tuple[str, str]
) -> None:
    reaction = reaction_for(points, best)
    assert (reaction["emotion"], reaction["gesture"]) == expected


def test_a_hub_address_becomes_a_page_origin_and_a_socket() -> None:
    config = voice_config("http://localhost:8787/", token="t")
    assert config.http_origin == "http://localhost:8787"
    assert config.ws_url == "ws://localhost:8787/ws"
    assert config.token == "t"


@pytest.mark.parametrize(
    "bad",
    [
        "http://192.168.1.5:8787",  # the hub refuses a Host that is not local
        "http://127.0.0.1:8787/avatar",
        "ftp://127.0.0.1:8787",
        "http://user@127.0.0.1:8787",
        "127.0.0.1:8787",
        "http://127.0.0.1:8787?token=x",
    ],
)
def test_a_hub_address_that_is_not_a_bare_local_origin_is_refused(bad: str) -> None:
    with pytest.raises(HubError):
        voice_config(bad)
