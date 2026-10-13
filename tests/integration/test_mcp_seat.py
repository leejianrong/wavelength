"""The MCP seat, in-process: what a client is allowed to see and do."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from mcp import Client

from wavelength.mcp_server import build


def run(server: Any, calls: list[tuple[str, dict[str, Any]]]) -> list[Any]:
    async def go() -> list[Any]:
        async with Client(server) as client:
            return [await client.call_tool(name, args) for name, args in calls]

    return asyncio.run(go())


def play_whole_match(server: Any) -> list[dict[str, Any]]:
    """Play the client seat to the end with a fixed clue / guess. Returns every
    structured tool result, in order."""

    async def go() -> list[dict[str, Any]]:
        seen: list[dict[str, Any]] = []
        async with Client(server) as client:
            obs = (await client.call_tool("get_observation", {})).structured_content
            seen.append(obs)
            while obs["phase"] is not None:
                legal = (await client.call_tool("list_legal_actions", {})).structured_content
                action: Any = "a lazy afternoon" if obs["phase"] == "clue" else 50
                assert legal is not None
                result = await client.call_tool("submit_action", {"action": action})
                assert not result.is_error, result.content
                obs = result.structured_content
                seen.append(obs)
        return seen

    return asyncio.run(go())


def test_a_guesser_client_plays_six_rounds_and_never_receives_a_target() -> None:
    server = build(opponent_first=True, config={"seed": 5})  # the bot is psychic in round 1

    seen = play_whole_match(server)

    assert seen[-1]["phase"] is None  # the match ended
    assert len(seen[-1]["history"]) == 6
    guesser_views = [s for s in seen if s.get("role") == "guesser"]
    assert len(guesser_views) >= 3  # not vacuous: the client really guessed in some rounds
    assert all("target" not in s for s in guesser_views)
    assert all("plan" not in s for s in seen)


def test_a_psychic_client_gets_the_target_and_its_clues_are_validated() -> None:
    server = build(config={"seed": 5, "rounds": 2})

    obs, bad, good = run(
        server,
        [
            ("get_observation", {}),
            ("submit_action", {"action": "about 70"}),
            ("submit_action", {"action": "a lazy afternoon"}),
        ],
    )

    assert obs.structured_content["role"] == "psychic" and "target" in obs.structured_content
    assert bad.is_error and "digits" in json.dumps([c.text for c in bad.content])
    assert not good.is_error
    assert good.structured_content["round"] == 2  # the bot guessed and the round turned over


def test_a_rejected_clue_changes_nothing() -> None:
    server = build(config={"seed": 5})
    before, _, after = run(
        server,
        [
            ("get_observation", {}),
            ("submit_action", {"action": "left of centre"}),
            ("get_observation", {}),
        ],
    )
    assert before.structured_content == after.structured_content


def test_the_clue_request_is_json_safe_and_the_guess_request_is_the_dial() -> None:
    server = build(config={"seed": 5})
    free_text, _, guess = run(
        server,
        [
            ("list_legal_actions", {}),
            ("submit_action", {"action": "a lazy afternoon"}),
            ("list_legal_actions", {}),
        ],
    )
    assert "free_text" in json.dumps(free_text.structured_content)
    # the bot guessed round 1 and, as round 2's psychic, already gave its clue, so
    # the client is now the guesser and is offered the whole dial
    assert guess.structured_content == {"result": list(range(101))}


def test_a_dump_is_the_viewers_observation_and_another_seat_is_refused() -> None:
    server = build(config={"seed": 5})
    obs, dump, other, other_dump = run(
        server,
        [
            ("get_observation", {}),
            ("get_state_dump", {}),
            ("get_observation", {"player": "opponent"}),
            ("get_state_dump", {"player": "opponent"}),
        ],
    )
    assert dump.structured_content == obs.structured_content
    assert other.is_error and other_dump.is_error


@pytest.mark.parametrize("bad", [[1, 2], {"clue": "x"}, None, 1.5])
def test_a_payload_that_is_neither_text_nor_a_whole_number_never_reaches_the_engine(
    bad: Any,
) -> None:
    server = build(config={"seed": 5})
    before, rejected, after = run(
        server,
        [
            ("get_observation", {}),
            ("submit_action", {"action": bad}),
            ("get_observation", {}),
        ],
    )
    assert rejected.is_error
    assert before.structured_content == after.structured_content


def test_the_two_seats_must_have_different_names() -> None:
    with pytest.raises(ValueError, match="different names"):
        build(client="x", opponent="x")
