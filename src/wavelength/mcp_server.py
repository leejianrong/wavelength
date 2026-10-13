"""Stdio MCP server that lets an external agent (e.g. Claude Code) play one
seat of Wavelength against a bot or an LLM opponent.

It is the framework's MCP server (fw-ADR-0006) bound to one seat, with its
viewer-scoped default left on (fw-ADR-0011): every tool result is that seat's
own observation, naming another seat is refused, and no tool returns the full
state, so the client cannot see an unrevealed target.

Tool flow for the client::

    get_observation()            -> role, phase, spectrum, clue, history, instructions
    list_legal_actions()         -> [{"free_text": ...}] for a clue, or the ints 0..100
    submit_action(action=...)    -> your next observation, after the opponent has played

``action`` is a string for a clue and an int for a guess. A rejected clue comes
back as a tool error that says why; nothing changes and you may try again. The
match is over when an observation has ``"phase": null``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from agent_game_framework import cli as framework_cli
from agent_game_framework.connectors.mcp import build_server
from mcp.server.mcpserver import MCPServer

from wavelength.cli import BoundMatch, register
from wavelength.engine import WavelengthEngine


def build(
    *,
    client: str = "agent",
    opponent: str = "opponent",
    opponent_spec: str = "bot:wl-random",
    opponent_first: bool = False,
    config: dict[str, Any] | None = None,
) -> MCPServer[None]:
    """A server whose one MCP client plays seat ``client``. ``opponent_spec`` is
    any seat spec the CLI accepts (``bot:wl-random``, ``llm:openrouter/<model>``).
    The client is the first seat, so the psychic in round 1, unless
    ``opponent_first``."""
    register()
    if client == opponent:
        raise ValueError("the client and opponent seats need different names")
    opponent_seat = framework_cli.build_controller(opponent_spec)
    players = [opponent, client] if opponent_first else [client, opponent]
    match = BoundMatch(
        WavelengthEngine(),
        players=players,
        config=config or {},
        seats={opponent: opponent_seat},
    )
    return build_server(
        match,
        bot_seats={opponent: opponent_seat},
        name="wavelength",
        bound_seat=client,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wavelength-mcp", description=__doc__.split("\n\n")[0])
    parser.add_argument("--client", default="agent", help="name of the seat the MCP client plays")
    parser.add_argument("--opponent", default="opponent", help="name of the other seat")
    parser.add_argument(
        "--opponent-spec",
        default="bot:wl-random",
        help="how the other seat plays: bot:wl-random or llm:openrouter/<model>",
    )
    parser.add_argument(
        "--opponent-first", action="store_true", help="the opponent is psychic in round 1"
    )
    parser.add_argument(
        "--config", action="append", default=[], metavar="KEY=VALUE", help="rounds, seed, ..."
    )
    args = parser.parse_args(argv)
    try:
        config = framework_cli.parse_config_args(args.config)
        server = build(
            client=args.client,
            opponent=args.opponent,
            opponent_spec=args.opponent_spec,
            opponent_first=args.opponent_first,
            config=config,
        )
    except (ValueError, framework_cli.SeatSpecError) as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
