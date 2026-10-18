"""``wavelength web``: serve the browser UI. With no ``--seat`` it opens on a start screen
where you choose who plays; with two ``--seat`` flags it starts that match straight away."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from wavelength.players import PlayersError, load_players
from wavelength.web.app import STATIC, create_app
from wavelength.web.host import DEFAULT_MODEL, Host
from wavelength.web.hub import DEFAULT_HUB, HubError, start_hub, stop_hub, voice_config
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
        help="human, bot:wl-random, llm:openrouter/<model> or llm:player/<name>; two start a match",
    )
    parser.add_argument(
        "--players", type=Path, metavar="FILE", help="TOML file of named AI players (personalities)"
    )
    parser.add_argument("--rounds", type=int, default=6, help="rounds, with --seat")
    parser.add_argument("--seed", type=int, help="seed, with --seat (default: random)")
    parser.add_argument(
        "--max-calls", type=int, default=200, help="hard cap on model calls per match"
    )
    parser.add_argument(
        "--think",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="AI players write working notes before each move (two model calls per move; "
        "--no-think for one call, cheaper and a little weaker: ADR-0010)",
    )
    parser.add_argument(
        "--needle-steps",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="an AI guesser works the needle in up to 4 steps, thinking aloud (about 3 model "
        "calls a guess); --no-needle-steps for one move and a derived walk: ADR-0012",
    )
    parser.add_argument("--bot-delay", type=float, default=0.8, help="seconds the bot waits")
    parser.add_argument(
        "--walk-pause",
        type=float,
        default=0.8,
        help="seconds between the needle's tentative positions when an AI guesser locks in",
    )
    parser.add_argument(
        "--voice",
        choices=["off", "fake", "real"],
        default="off",
        help="voice and faces through a vikaki hub: fake (silent test voice) or real (Kokoro)",
    )
    parser.add_argument("--hub", default=DEFAULT_HUB, help="the hub's address, with --voice")
    parser.add_argument(
        "--vikaki-dir",
        type=Path,
        default=Path(os.environ["VIKAKI_DIR"]) if os.environ.get("VIKAKI_DIR") else None,
        help="a built vikaki checkout: start the hub from it (default: expect one at --hub)",
    )
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

    try:
        players = load_players(args.players) if args.players else []
    except PlayersError as exc:
        print(f"cannot read the players file: {exc}", file=sys.stderr)
        return 2
    voice = None
    hub_process = None
    if args.voice != "off":
        try:
            voice = voice_config(args.hub, os.environ.get("VIKAKI_TOKEN") or None)
            if args.vikaki_dir:
                origins = [f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"]
                hub_process = start_hub(
                    args.vikaki_dir,
                    voice,
                    tts="kokoro" if args.voice == "real" else "fake",
                    frame_origins=origins,
                )
                if hub_process is None:
                    print(
                        f"voice: a hub is already running at {args.hub}; using it as it is "
                        "(its own --tts and --frame-ancestors apply)",
                        file=sys.stderr,
                    )
        except HubError as exc:
            print(f"voice: {exc}", file=sys.stderr)
            return 2
    host = Host(
        max_calls=args.max_calls,
        bot_delay=args.bot_delay,
        walk_pause=args.walk_pause,
        players=players,
        voice=voice,
        think=args.think,
        needle_steps=args.needle_steps,
    )
    try:
        if args.seat:
            seats = [parse_seat_flag(s, DEFAULT_MODEL, players) for s in args.seat]
            host.start(
                {
                    "seats": [{"kind": s.kind, "model": s.model, "player": s.name} for s in seats],
                    "rounds": args.rounds,
                    "seed": args.seed,
                }
            )
    except MoveRejected as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        host.close()
        if hub_process is not None:
            stop_hub(hub_process)
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
    except KeyboardInterrupt:
        pass  # Ctrl+C: uvicorn has shut down and re-raises the signal; that is a normal exit
    finally:
        # A second Ctrl+C (or uvicorn's re-raised one) must not cut the clean-up short.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        host.close()
        if hub_process is not None:
            stop_hub(hub_process)
    return 0
