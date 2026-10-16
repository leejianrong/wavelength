"""The lobby: what a start request may ask for, and the start/stop life cycle."""

from __future__ import annotations

import json
from typing import Any

import pytest

from wavelength.bots import RandomWavelengthBot
from wavelength.web import host as host_module
from wavelength.web.host import Host, display_names
from wavelength.web.moves import MoveRejected
from wavelength.web.seatspec import SeatSpec, parse_seat, parse_seat_flag, seat_ids

HUMAN = {"kind": "human"}
BOT = {"kind": "bot"}
LLM = {"kind": "llm", "model": "deepseek/deepseek-v4.1-flash"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """An AI seat is a fake bot here: nothing in this file may call a model."""
    monkeypatch.setattr(host_module, "build_controller", lambda spec, meter: RandomWavelengthBot())


def new_host(**kwargs: Any) -> Host:
    kwargs.setdefault("llm_available", True)
    kwargs.setdefault("bot_delay", 0)
    return Host(**kwargs)


@pytest.mark.parametrize(
    "request_body",
    [
        None,
        [],
        {},
        {"seats": [HUMAN]},
        {"seats": [HUMAN, BOT, BOT]},
        {"seats": [HUMAN, {"kind": "robot"}]},
        {"seats": [HUMAN, "bot"]},
        {"seats": [HUMAN, HUMAN]},
        {"seats": [HUMAN, {"kind": "llm", "model": "no-slash"}]},
        {"seats": [HUMAN, {"kind": "llm", "model": "a/b; rm -rf"}]},
        {"seats": [HUMAN, BOT], "rounds": 0},
        {"seats": [HUMAN, BOT], "rounds": 21},
        {"seats": [HUMAN, BOT], "rounds": True},
        {"seats": [HUMAN, BOT], "rounds": "6"},
        {"seats": [HUMAN, BOT], "seed": -1},
        {"seats": [HUMAN, BOT], "seed": True},
        {"seats": [HUMAN, BOT], "seed": "7"},
    ],
)
def test_a_bad_start_request_is_refused_with_a_reason_and_starts_nothing(request_body: Any) -> None:
    host = new_host()
    with pytest.raises(MoveRejected) as excinfo:
        host.start(request_body)
    assert str(excinfo.value)
    assert host.session is None


def test_an_ai_seat_is_refused_when_no_key_is_configured() -> None:
    host = new_host(llm_available=False)
    with pytest.raises(MoveRejected, match="OPENROUTER_API_KEY"):
        host.start({"seats": [HUMAN, LLM]})
    host.start({"seats": [HUMAN, BOT]})  # but a bot match needs no key
    host.close()


def test_a_human_and_a_bot_get_plain_ids_and_names() -> None:
    host = new_host()
    session = host.start({"seats": [HUMAN, BOT], "rounds": 3, "seed": 4})
    assert session.players == ["you", "bot"] and session.human == "you"
    assert session.names == {"you": "You", "bot": "Bot"}
    assert session.kinds == {"you": "human", "bot": "bot"}
    host.close()


def test_two_ais_of_one_model_are_told_apart() -> None:
    host = new_host()
    session = host.start({"seats": [LLM, LLM]})
    assert session.players == ["ai-1", "ai-2"] and session.human is None
    assert list(session.names.values()) == ["deepseek-v4.1-flash 1", "deepseek-v4.1-flash 2"]
    host.close()


def test_a_second_start_while_a_match_runs_is_refused_until_it_is_stopped() -> None:
    host = new_host()
    host.start({"seats": [HUMAN, BOT]})
    with pytest.raises(MoveRejected, match="already running"):
        host.start({"seats": [HUMAN, BOT]})
    host.stop()
    host.start({"seats": [LLM, BOT]})
    host.close()


def test_stopping_returns_everyone_to_the_start_screen() -> None:
    host = new_host()
    host.start({"seats": [HUMAN, BOT]})
    sub = host.broadcaster.subscribe()
    assert any(event == "state" for event, _ in drain(sub))
    first = host.session
    host.stop()

    assert host.session is None and first is not None and not first.is_active()
    late = host.broadcaster.subscribe()
    replay = drain(late)
    assert [event for event, _ in replay] == ["lobby"]  # no stale state or talk is replayed


def drain(sub: Any) -> list[tuple[str, str]]:
    out = []
    while True:
        try:
            out.append(sub.get(0.3))
        except Exception:
            return out


def test_the_start_screen_says_whether_ai_is_available_and_never_carries_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-SECRET-VALUE")
    host = Host()
    config = host.config()
    assert config["llm_available"] is True
    assert "SECRET" not in json.dumps(config) and "SECRET" not in json.dumps(
        drain(host.broadcaster.subscribe())
    )
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert Host().config()["llm_available"] is False


def test_parse_seat_checks_the_model_name() -> None:
    assert parse_seat({"kind": "llm"}, "a/b") == SeatSpec("llm", "a/b")
    assert parse_seat({"kind": "llm", "model": "openai/gpt-4o-mini"}, "a/b").model == (
        "openai/gpt-4o-mini"
    )
    assert parse_seat({"kind": "human", "model": "ignored/x"}, "a/b") == SeatSpec("human")
    with pytest.raises(MoveRejected):
        parse_seat({"kind": "llm", "model": "../etc/passwd"}, "a/b")


def test_seat_flags_are_parsed_like_the_play_command() -> None:
    assert parse_seat_flag("human", "a/b") == SeatSpec("human")
    assert parse_seat_flag("bot:wl-random", "a/b") == SeatSpec("bot")
    assert parse_seat_flag("llm:openrouter/openai/gpt-4o-mini", "a/b") == SeatSpec(
        "llm", "openai/gpt-4o-mini"
    )
    with pytest.raises(MoveRejected):
        parse_seat_flag("llm:other/x", "a/b")


def test_ids_and_names_are_unique() -> None:
    assert seat_ids([SeatSpec("human"), SeatSpec("bot")]) == ["you", "bot"]
    assert seat_ids([SeatSpec("llm", "a/b"), SeatSpec("llm", "c/d")]) == ["ai-1", "ai-2"]
    assert display_names([SeatSpec("llm", "a/b"), SeatSpec("llm", "c/d")]) == ["b", "d"]
    assert display_names([SeatSpec("llm", "a/b"), SeatSpec("llm", "x/b")]) == ["b 1", "b 2"]
