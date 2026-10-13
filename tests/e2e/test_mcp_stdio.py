"""V5 acceptance: an MCP client plays a seat through the installed
``wavelength-mcp`` script over real stdio."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from wavelength.engine import WavelengthEngine


def params(*args: str) -> StdioServerParameters:
    command = shutil.which("wavelength-mcp")
    assert command is not None, "wavelength-mcp is not installed"
    return StdioServerParameters(command=command, args=list(args))


def test_a_client_plays_a_whole_match_as_the_guesser_over_stdio_and_never_sees_a_target() -> None:
    plan = WavelengthEngine().initial_state(["o", "c"], {"seed": 5}).plan

    async def play() -> list[dict[str, Any]]:
        seen: list[dict[str, Any]] = []
        server = params(
            "--client", "c", "--opponent", "o", "--opponent-first", "--config", "seed=5"
        )
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                obs = (await session.call_tool("get_observation", {})).structured_content
                assert obs is not None
                seen.append(obs)
                while obs["phase"] is not None:
                    action: Any = "a lazy afternoon" if obs["phase"] == "clue" else 50
                    result = await session.call_tool("submit_action", {"action": action})
                    assert not result.is_error, result.content
                    assert result.structured_content is not None
                    obs = result.structured_content
                    seen.append(obs)
        return seen

    seen = asyncio.run(asyncio.wait_for(play(), timeout=60))

    assert seen[-1]["phase"] is None and len(seen[-1]["history"]) == 6
    # the guesser sees a round's target only from the observation after its reveal
    for obs in seen:
        assert "target" not in obs or obs["role"] == "psychic"
        assert "plan" not in obs
        revealed = {r["round"] for r in obs["history"]}
        for index, round_plan in enumerate(plan, start=1):
            if index not in revealed and obs.get("role") == "guesser":
                assert f'"target": {round_plan.target}' not in json.dumps(obs)


def test_a_client_psychic_gets_a_clear_error_for_a_bad_clue_over_stdio() -> None:
    async def play() -> tuple[Any, Any]:
        async with stdio_client(params("--config", "seed=5", "--config", "rounds=1")) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                bad = await session.call_tool("submit_action", {"action": "about 70"})
                good = await session.call_tool("submit_action", {"action": "a lazy afternoon"})
                return bad, good

    bad, good = asyncio.run(asyncio.wait_for(play(), timeout=60))

    assert bad.is_error and "digits" in bad.content[0].text
    assert not good.is_error and good.structured_content["phase"] is None  # one round, over


def test_bad_arguments_exit_with_a_usage_message_not_a_traceback() -> None:
    import subprocess

    result = subprocess.run(
        ["wavelength-mcp", "--client", "x", "--opponent", "x"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "different names" in result.stderr and "Traceback" not in result.stderr
