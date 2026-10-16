"""``wavelength web``: serve the browser UI for one human against a scripted
opponent. (LLM opponents and watch mode arrive in V8.)"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from agent_game_framework import cli as framework_cli

from wavelength.web.app import STATIC, create_app
from wavelength.web.session import WebSession


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="wavelength web", description=__doc__)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--seed", type=int, help="default: a random seed, printed at start")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--opponent", default="bot:wl-random", help="a bot:<name> seat")
    parser.add_argument("--bot-delay", type=float, default=0.8, help="seconds the bot waits")
    parser.add_argument("--static", type=Path, default=STATIC, help="folder of page files (tests)")
    args = parser.parse_args(argv)

    if args.rounds < 1:
        print("--rounds must be at least 1", file=sys.stderr)
        return 2
    if not args.opponent.startswith("bot:"):
        print("only bot: opponents are available so far", file=sys.stderr)
        return 2
    if not (args.static / "app.js").exists():
        print("The page is not built. Run: make web-build", file=sys.stderr)
        return 2
    try:
        opponent = framework_cli.build_controller(args.opponent)
    except Exception as exc:
        print(f"cannot build opponent {args.opponent!r}: {exc}", file=sys.stderr)
        return 2

    import uvicorn

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1 << 31)
    session = WebSession(opponent, rounds=args.rounds, seed=seed, opponent_delay=args.bot_delay)
    session.start()
    print(f"Wavelength: http://{args.host}:{args.port}/  (seed {seed}, {args.rounds} rounds)")
    try:
        uvicorn.run(
            create_app(session, static=args.static),
            host=args.host,
            port=args.port,
            log_level="warning",
            timeout_graceful_shutdown=2,
        )
    finally:
        session.close()
    return 0
