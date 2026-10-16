"""Which seats a web match has, and how each is built."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from agent_game_framework.agents import OpenRouterBackend
from agent_game_framework.core import SeatController

from wavelength.bots import RandomWavelengthBot
from wavelength.eval import Meter, metered
from wavelength.seats import guard
from wavelength.web.moves import MoveRejected

Kind = Literal["human", "bot", "llm"]
KINDS: tuple[str, ...] = ("human", "bot", "llm")
MODEL_SLUG = re.compile(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.:\-]+")  # an OpenRouter "<provider>/<model>"


@dataclass(frozen=True)
class SeatSpec:
    kind: Kind
    model: str | None = None


def parse_seat(raw: Any, default_model: str) -> SeatSpec:
    """A seat as the page sends it: ``{"kind": "human" | "bot" | "llm", "model": "<slug>"}``."""
    if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
        raise MoveRejected("each seat must be a human, a bot or an AI")
    kind: Kind = raw["kind"]
    if kind != "llm":
        return SeatSpec(kind)
    model = raw.get("model") or default_model
    if not isinstance(model, str) or not MODEL_SLUG.fullmatch(model):
        raise MoveRejected("an AI seat needs a model name like provider/model")
    return SeatSpec("llm", model)


def parse_seat_flag(spec: str, default_model: str) -> SeatSpec:
    """A seat as the command line writes it: human, bot:wl-random or llm:openrouter/<model>."""
    if spec == "human":
        return SeatSpec("human")
    if spec.startswith("bot:"):
        return SeatSpec("bot")
    if spec.startswith("llm:openrouter/"):
        return parse_seat(
            {"kind": "llm", "model": spec.removeprefix("llm:openrouter/")}, default_model
        )
    raise MoveRejected(f"unknown seat {spec!r}: use human, bot:wl-random or llm:openrouter/<model>")


def seat_ids(specs: list[SeatSpec]) -> list[str]:
    """Stable, readable ids: ``you``, ``bot``, ``ai``; numbered when two seats would clash."""
    base = {"human": "you", "bot": "bot", "llm": "ai"}
    names = [base[s.kind] for s in specs]
    if len(set(names)) < len(names):
        names = [f"{n}-{i + 1}" for i, n in enumerate(names)]
    return names


def build_controller(spec: SeatSpec, meter: Meter) -> SeatController[Any, Any]:
    """A non-human seat. An AI seat is the framework's OpenRouter backend, counted by the
    shared ``meter`` and wrapped in the guard that bounds retries (``seats.py``)."""
    if spec.kind == "bot":
        return RandomWavelengthBot()
    assert spec.kind == "llm" and spec.model
    return guard(metered(OpenRouterBackend(model=spec.model), meter))
