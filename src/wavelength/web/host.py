"""The lobby: at most one match at a time, started, stopped and restarted from the page.

``Host`` owns the broadcaster, so the event stream survives from one match to the next.
Nothing here sees game state: it validates a start request, builds the seats and hands
over to a ``WebSession``. An AI seat spends the OpenRouter key the server was started
with, so a start is only accepted from this server's own page (see ``app``), every match
has a hard cap on model calls, and the key itself is never sent anywhere.
"""

from __future__ import annotations

import os
import random
import threading
from typing import Any

from wavelength.eval import Meter
from wavelength.web.broadcast import Broadcaster
from wavelength.web.moves import MoveRejected
from wavelength.web.seatspec import SeatSpec, build_controller, parse_seat, seat_ids
from wavelength.web.session import DelayedSeat, WebSession

DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
SUGGESTED_MODELS = [DEFAULT_MODEL, "openai/gpt-4o-mini"]
ROUND_OPTIONS = [3, 6, 9]
MAX_ROUNDS = 20


def display_names(specs: list[SeatSpec]) -> list[str]:
    base = [
        "You"
        if s.kind == "human"
        else "Bot"
        if s.kind == "bot"
        else (s.model or "AI").split("/")[-1]
        for s in specs
    ]
    return base if len(set(base)) == len(base) else [f"{n} {i + 1}" for i, n in enumerate(base)]


class Host:
    def __init__(
        self,
        *,
        max_calls: int = 200,
        bot_delay: float = 0.8,
        llm_available: bool | None = None,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        self.broadcaster = Broadcaster()
        self.max_calls = max_calls
        self.bot_delay = bot_delay
        self.default_model = default_model
        self.llm_available = (
            bool(os.environ.get("OPENROUTER_API_KEY")) if llm_available is None else llm_available
        )
        self.session: WebSession | None = None
        self._lock = threading.Lock()
        self.show_lobby()

    def config(self) -> dict[str, Any]:
        """What the start screen needs. It says whether an AI can be used, never the key."""
        return {
            "type": "lobby",
            "llm_available": self.llm_available,
            "default_model": self.default_model,
            "models": SUGGESTED_MODELS,
            "max_calls": self.max_calls,
            "rounds": 6,
            "round_options": ROUND_OPTIONS,
        }

    def show_lobby(self) -> None:
        self.broadcaster.forget("state", "talk")
        self.broadcaster.emit("lobby", self.config(), remember=True)

    def start(self, request: Any) -> WebSession:
        """Validate a start request and begin a match. Raises ``MoveRejected`` with a reason
        a player can read; nothing is started in that case."""
        if not isinstance(request, dict):
            raise MoveRejected("a start request must be a JSON object")
        raw_seats = request.get("seats")
        if not isinstance(raw_seats, list) or len(raw_seats) != 2:
            raise MoveRejected("a match needs exactly two seats")
        specs = [parse_seat(s, self.default_model) for s in raw_seats]
        if sum(s.kind == "human" for s in specs) > 1:
            raise MoveRejected("only one human can play at a time")
        if any(s.kind == "llm" for s in specs) and not self.llm_available:
            raise MoveRejected("AI seats need OPENROUTER_API_KEY set before the server starts")
        rounds = request.get("rounds", 6)
        if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= MAX_ROUNDS:
            raise MoveRejected(f"rounds must be a whole number from 1 to {MAX_ROUNDS}")
        seed = request.get("seed")
        if seed is None:
            seed = random.SystemRandom().randrange(1 << 31)
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 1 << 31:
            raise MoveRejected("the seed must be a whole number")

        with self._lock:
            if self.session is not None and self.session.is_active():
                raise MoveRejected("a match is already running; stop it first")
            ids = seat_ids(specs)
            meter = Meter(max_calls=self.max_calls)
            controllers: dict[str, Any] = {}
            try:
                for pid, spec in zip(ids, specs, strict=True):
                    if spec.kind == "human":
                        continue
                    seat = build_controller(spec, meter)
                    controllers[pid] = (
                        DelayedSeat(seat, self.bot_delay)
                        if spec.kind == "bot" and self.bot_delay
                        else seat
                    )
            except ValueError as exc:  # e.g. no key after all
                raise MoveRejected(str(exc)) from None
            human = next(
                (pid for pid, s in zip(ids, specs, strict=True) if s.kind == "human"), None
            )
            session = WebSession(
                ids,
                controllers,
                broadcaster=self.broadcaster,
                human=human,
                names=dict(zip(ids, display_names(specs), strict=True)),
                kinds={pid: s.kind for pid, s in zip(ids, specs, strict=True)},
                rounds=rounds,
                seed=seed,
                meter=meter,
            )
            self.broadcaster.forget("lobby", "state", "talk")
            self.session = session
            session.start()
            return session

    def stop(self) -> None:
        """End the running match, if any, and return everyone to the start screen."""
        with self._lock:
            if self.session is not None:
                self.session.close()
                self.session.join(1.0)  # a human's turn ends at once; an AI call may take longer
                self.session = None
            self.show_lobby()

    def close(self) -> None:
        with self._lock:
            if self.session is not None:
                self.session.close()
