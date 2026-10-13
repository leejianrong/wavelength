"""``wavelength`` console script: registers the game with the framework's
registries, then delegates to the framework CLI (ADR-0001).

The registries are module-level dicts in ``agent_game_framework.cli``; adding
to them is a convention, not a published API, which is why the framework is
pinned to a commit and ``tests/e2e`` drives the installed script.
"""

from __future__ import annotations

from agent_game_framework import cli as framework_cli

from wavelength.bots import RandomWavelengthBot
from wavelength.engine import WavelengthEngine
from wavelength.render import render_observation

GAME_NAME = "wavelength"
BOT_NAME = "wl-random"


def register() -> None:
    """Idempotently add Wavelength's engine, renderer and test bot."""
    framework_cli.GAME_REGISTRY[GAME_NAME] = WavelengthEngine
    framework_cli.RENDERER_REGISTRY[GAME_NAME] = lambda: render_observation
    framework_cli.BOT_REGISTRY[BOT_NAME] = RandomWavelengthBot


def main(argv: list[str] | None = None) -> int:
    register()
    return framework_cli.main(argv)
