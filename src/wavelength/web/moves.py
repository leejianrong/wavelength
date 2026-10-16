"""What a browser may send, checked before the engine sees it. The engine still
judges a clue's rules and a guess's range; this only rejects what is not even
the right shape, so garbage never reaches ``apply_action``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MAX_CLUE_CHARS = 500  # a sanity bound on the request; the engine's own limit is stricter


class MoveRejected(Exception):
    """A browser message that cannot be a move; the text is safe to show the player."""


@dataclass(frozen=True)
class Move:
    kind: Literal["clue", "guess"]
    value: str | int


def parse_move(payload: Any) -> Move:
    if not isinstance(payload, dict):
        raise MoveRejected("a move must be a JSON object")
    kind = payload.get("type")
    if kind == "clue":
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise MoveRejected("a clue must be some text")
        if len(text) > MAX_CLUE_CHARS:
            raise MoveRejected("that clue is far too long")
        return Move("clue", text)
    if kind == "guess":
        value = payload.get("value")
        if isinstance(value, bool) or not isinstance(value, int):
            raise MoveRejected("a guess must be a whole number")
        return Move("guess", value)
    raise MoveRejected("a move is a clue or a guess")
