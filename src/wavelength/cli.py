"""``wavelength`` console script: registers the game with the framework's
registries, then delegates to the framework CLI (ADR-0001).

The registries are module-level dicts in ``agent_game_framework.cli``; adding
to them is a convention, not a published API, which is why the framework is
pinned to a commit and ``tests/e2e`` drives the installed script.

``llm:`` seats are additionally wrapped in a ``GuardedSeat`` by replacing the
framework's ``build_controller`` for this process; see ``seats.py`` for why.
"""

from __future__ import annotations

import sys
from typing import Any

from agent_game_framework import cli as framework_cli
from agent_game_framework.agents import HumanCLIController
from agent_game_framework.core import GameEngine, Match, PlayerId, SeatController

from wavelength.bots import RandomWavelengthBot
from wavelength.engine import WavelengthEngine
from wavelength.render import render_observation
from wavelength.seats import GuardedConversableSeat, guard

GAME_NAME = "wavelength"
BOT_NAME = "wl-random"

_framework_build_controller = framework_cli.build_controller


def _quiet_print(*args: Any, **kwargs: Any) -> None:
    """The framework's human prompt dumps the raw observation and legal-action
    list before every move. The renderer already shows what a person needs, and
    the dumps are noise (the guess list is 101 numbers), so drop those two."""
    if args and args[0] in ("Observation:", "Legal actions:"):
        return
    print(*args, **kwargs)


def _build_controller(spec: str) -> SeatController[object, object]:
    if spec == "human":
        return HumanCLIController(print_fn=_quiet_print)
    controller: SeatController[object, object] = _framework_build_controller(spec)
    return guard(controller) if spec.startswith("llm:") or ":advised-by=" in spec else controller


class BoundMatch(Match[Any, Any, Any]):
    """A framework ``Match`` that tells each chat-capable seat which match and
    seat it plays, so its chat replies can be given current, redacted game
    context (``chat_guard``). Seats are built before the match exists, which is
    why this cannot be done in ``_build_controller``."""

    def __init__(
        self,
        engine: GameEngine[Any, Any, Any],
        players: list[PlayerId],
        config: dict[str, Any] | None = None,
        seats: dict[PlayerId, SeatController[Any, Any]] | None = None,
    ) -> None:
        super().__init__(engine, players, config, seats)
        for player, seat in (seats or {}).items():
            if isinstance(seat, GuardedConversableSeat):
                seat.bind(self, player)


def register() -> None:
    """Idempotently add Wavelength's engine, renderer, test bot, seat guard and
    chat binding."""
    framework_cli.GAME_REGISTRY[GAME_NAME] = WavelengthEngine
    framework_cli.RENDERER_REGISTRY[GAME_NAME] = lambda: render_observation
    framework_cli.BOT_REGISTRY[BOT_NAME] = RandomWavelengthBot
    framework_cli.build_controller = _build_controller
    setattr(framework_cli, "Match", BoundMatch)  # noqa: B010  (a private name there)


def main(argv: list[str] | None = None) -> int:
    register()
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "web":
        from wavelength.web.cli import main as web_main

        return web_main(args[1:])
    return framework_cli.main(argv)
