"""Named AI players from a TOML file: a name, a model and a personality (V9).

```toml
[[player]]
name = "Dry Sceptic"
model = "deepseek/deepseek-v4.1-flash"
personality = "You are dry and sceptical. ..."
voice = "ada"   # optional: the vikaki persona (avatar and voice) used with --voice
```

The personality is operator config, not game data: it goes to the model as extra system text
(``OpenRouterBackend(system_prompt=...)``) and to nobody else. A page and the chat context see
only the name. It adds to the built-in prompts and cannot lift a rule: the guard still bounds
retries and drops clue-turn banter, and a psychic still does not chat.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODEL_SLUG = re.compile(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.:\-]+")  # an OpenRouter "<provider>/<model>"
FIELDS = ("name", "model", "personality", "voice")
VOICE_NAME = re.compile(r"[A-Za-z0-9_\-]{1,32}")  # a vikaki persona name
MAX_NAME = 24
MAX_PERSONALITY = 1200


class PlayersError(ValueError):
    """The players file is unusable; the message says where and why."""


@dataclass(frozen=True)
class Player:
    name: str
    model: str
    personality: str
    voice: str | None = None  # the vikaki persona (face and voice) this player speaks with


def _text(item: dict[str, Any], key: str, where: str, limit: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlayersError(f"{where}: '{key}' must be a non-empty string")
    value = value.strip()
    if len(value) > limit:
        raise PlayersError(f"{where}: '{key}' is longer than {limit} characters")
    return value


def parse_players(data: Any) -> list[Player]:
    items = data.get("player") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise PlayersError("the file needs at least one [[player]] table")
    players: list[Player] = []
    for index, item in enumerate(items):
        where = f"player {index + 1}"
        if not isinstance(item, dict):
            raise PlayersError(f"{where} must be a table")
        unknown = sorted(set(item) - set(FIELDS))
        if unknown:
            raise PlayersError(f"{where}: unknown field(s) {', '.join(unknown)}")
        name = _text(item, "name", where, MAX_NAME)
        model = _text(item, "model", where, 100)
        if not MODEL_SLUG.fullmatch(model):
            raise PlayersError(f"{where}: model must look like provider/model, not {model!r}")
        personality = _text(item, "personality", where, MAX_PERSONALITY)
        if any(p.name.lower() == name.lower() for p in players):
            raise PlayersError(f"{where}: the name {name!r} is used twice")
        voice = item.get("voice")
        if voice is not None and (not isinstance(voice, str) or not VOICE_NAME.fullmatch(voice)):
            raise PlayersError(f"{where}: 'voice' must be a persona name such as ada")
        players.append(Player(name, model, personality, voice))
    return players


def load_players(path: Path) -> list[Player]:
    try:
        return parse_players(tomllib.loads(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise PlayersError(f"cannot read {path}: {exc.strerror}") from None
    except tomllib.TOMLDecodeError as exc:
        raise PlayersError(f"{path} is not valid TOML: {exc}") from None


def find_player(players: list[Player], name: str) -> Player | None:
    return next((p for p in players if p.name.lower() == name.strip().lower()), None)
