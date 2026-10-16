"""``wavelength web``: serve the browser UI. With no ``--seat`` it opens on a start screen
where you choose who plays; with two ``--seat`` flags it starts that match straight away."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from wavelength.web.app import STATIC, create_app
from wavelength.web.host import DEFAULT_MODEL, Host
from wavelength.web.moves import MoveRejected
from wavelength.web.seatspec import parse_seat_flag


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="wavelength web", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--seat",
        action="append",
        default=[],
        metavar="SPEC",
        help="human, bot:wl-random or llm:openrouter/<model>; two of them skip the start screen",
    )
    parser.add_argument("--rounds", type=int, default=6, help="rounds, with --seat")
    parser.add_argument("--seed", type=int, help="seed, with --seat (default: random)")
    parser.add_argument(
        "--max-calls", type=int, default=200, help="hard cap on model calls per match"
    )
    parser.add_argument("--bot-delay", type=float, default=0.8, help="seconds the bot waits")
    parser.add_argument("--static", type=Path, default=STATIC, help="folder of page files (tests)")
    args = parser.parse_args(argv)

    if args.max_calls < 1 or args.rounds < 1:
        print("--max-calls and --rounds must be at least 1", file=sys.stderr)
        return 2
    if len(args.seat) not in (0, 2):
        print("give --seat twice, or not at all", file=sys.stderr)
        return 2
    if not (args.static / "app.js").exists():
        print("The page is not built. Run: make web-build", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    import uvicorn

    host = Host(max_calls=args.max_calls, bot_delay=args.bot_delay)
    try:
        if args.seat:
            seats = [parse_seat_flag(s, DEFAULT_MODEL) for s in args.seat]
            host.start(
                {
                    "seats": [{"kind": s.kind, "model": s.model} for s in seats],
                    "rounds": args.rounds,
                    "seed": args.seed,
                }
            )
    except MoveRejected as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    state = "a match is running" if args.seat else "start screen"
    print(f"Wavelength: http://{args.host}:{args.port}/  ({state})")
    try:
        uvicorn.run(
            create_app(host),
            host=args.host,
            port=args.port,
            log_level="warning",
            timeout_graceful_shutdown=2,
        )
    finally:
        host.close()
    return 0
