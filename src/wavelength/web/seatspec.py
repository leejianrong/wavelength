"""Which seats a web match has, and how each is built."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from agent_game_framework.agents import OpenRouterBackend
from agent_game_framework.core import SeatController

from wavelength.bots import RandomWavelengthBot
from wavelength.eval import Meter, metered
from wavelength.needle_seat import NeedleSeat
from wavelength.players import MODEL_SLUG, Player, find_player
from wavelength.seats import guard
from wavelength.thinking import ThinkingSeat
from wavelength.web.moves import MoveRejected

SEMULA_KEY = "semula-local"  # semula takes any key; the real one never goes near it


@dataclass(frozen=True)
class Semula:
    """Where the semula server is and which project holds this game's calls. Operator config:
    a page learns that an agent can play, never the address or the project."""

    url: str
    project: str = "play"
    timeout: float = 300.0

    @property
    def base_url(self) -> str:
        return f"{self.url.rstrip('/')}/v1/projects/{self.project}"


Kind = Literal["human", "bot", "llm"]
KINDS: tuple[str, ...] = ("human", "bot", "llm")


@dataclass(frozen=True)
class SeatSpec:
    kind: Kind
    model: str | None = None
    name: str | None = None  # a named player's name, shown instead of the model
    personality: str | None = None
    voice: str | None = None  # the vikaki persona for a named player
    provider: str = "openrouter"  # "semula": an agent answers through semula (ADR-0014)


def parse_seat(raw: Any, default_model: str, players: list[Player] | None = None) -> SeatSpec:
    """A seat as the page sends it: ``{"kind": "human" | "bot" | "llm", "model": "<slug>"}``,
    or for an AI ``{"kind": "llm", "player": "<name from the players file>"}``."""
    if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
        raise MoveRejected("each seat must be a human, a bot or an AI")
    kind: Kind = raw["kind"]
    if kind != "llm":
        return SeatSpec(kind)
    if raw.get("player") is not None:
        player = (
            find_player(players or [], raw["player"]) if isinstance(raw["player"], str) else None
        )
        if player is None:
            raise MoveRejected("that player is not in the players file")
        return SeatSpec(
            "llm", player.model, player.name, player.personality, player.voice, player.provider
        )
    model = raw.get("model") or default_model
    if not isinstance(model, str) or not MODEL_SLUG.fullmatch(model):
        raise MoveRejected("an AI seat needs a model name like provider/model")
    return SeatSpec("llm", model)


def parse_seat_flag(spec: str, default_model: str, players: list[Player] | None = None) -> SeatSpec:
    """A seat as the command line writes it: human, bot:wl-random, llm:openrouter/<model> or
    llm:player/<name>."""
    if spec == "human":
        return SeatSpec("human")
    if spec.startswith("bot:"):
        return SeatSpec("bot")
    if spec.startswith("llm:openrouter/"):
        return parse_seat(
            {"kind": "llm", "model": spec.removeprefix("llm:openrouter/")}, default_model
        )
    if spec.startswith("llm:player/"):
        return parse_seat(
            {"kind": "llm", "player": spec.removeprefix("llm:player/")}, default_model, players
        )
    raise MoveRejected(
        f"unknown seat {spec!r}: use human, bot:wl-random, llm:openrouter/<model> "
        "or llm:player/<name>"
    )


def seat_ids(specs: list[SeatSpec]) -> list[str]:
    """Stable, readable ids: ``you``, ``bot``, ``ai``; numbered when two seats would clash."""
    base = {"human": "you", "bot": "bot", "llm": "ai"}
    names = [base[s.kind] for s in specs]
    if len(set(names)) < len(names):
        names = [f"{n}-{i + 1}" for i, n in enumerate(names)]
    return names


def build_controller(
    spec: SeatSpec,
    meter: Meter,
    think: bool = True,
    needle_steps: bool = True,
    semula: Semula | None = None,
) -> SeatController[Any, Any]:
    """A non-human seat. An AI seat is the framework's OpenRouter backend, counted by the
    shared ``meter`` and wrapped in the guard that bounds retries (``seats.py``). A semula
    seat is the same backend pointed at a semula project, where an agent answers the held
    call; it makes one call a move, because each extra call is one more for the agent."""
    if spec.kind == "bot":
        return RandomWavelengthBot()
    assert spec.kind == "llm" and spec.model
    backend: OpenRouterBackend[Any, Any]
    if spec.provider == "semula":
        if semula is None:
            raise ValueError("an agent seat needs --semula")
        backend = OpenRouterBackend(
            model=spec.model,
            system_prompt=spec.personality or None,
            api_key=SEMULA_KEY,
            base_url=semula.base_url,
            timeout=semula.timeout,
        )
        think = needle_steps = False
    else:
        backend = OpenRouterBackend(model=spec.model, system_prompt=spec.personality)
    counted = metered(backend, meter)
    if needle_steps:
        return guard(NeedleSeat(counted, think=think))
    return guard(ThinkingSeat(counted) if think else counted)
