"""Players that think before they move (V12, ADR-0010).

``ThinkingSeat`` makes one extra, plain model call before each move, asking for short working
notes written from a checklist (``prompts.py``), and then asks for the move with those notes
added to the observation's instructions. It costs two calls per move, both counted by the shared
``Meter`` (it wraps a *metered* seat).

The notes are the seat's own working. A psychic's notes name the target, so they stay inside
this object: they go back to the same model for its move and nowhere else. ``last`` is kept for
V13, which may show them after a reveal; nothing reads it yet. If the notes call fails the move
is made without them; a call-cap error is never swallowed.
"""

from __future__ import annotations

import logging
from typing import Any

from agent_game_framework.core import (
    ConversationInput,
    ConversationOutput,
    ConversationTurn,
    SeatController,
    SeatDecision,
    TextTurn,
    is_free_text,
)

from wavelength.eval import CallCapExceeded
from wavelength.prompts import MAX_NOTES_CHARS, thinking_prompt

log = logging.getLogger("wavelength.thinking")


class ThinkingSeat:
    def __init__(self, inner: SeatController[Any, Any]) -> None:
        self._inner = inner
        self._key: tuple[Any, ...] | None = None
        self._notes = ""
        self.last: dict[str, Any] | None = None

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        notes = self._think(observation, legal_actions)
        if notes:
            observation = {
                **observation,
                "instructions": f"{observation.get('instructions', '')}\n\n"
                f"Your own notes from thinking this through:\n{notes}\n\n"
                "Now make your move.",
            }
        return self._inner.decide(observation, legal_actions)

    def respond(
        self, history: list[ConversationTurn], incoming: ConversationInput
    ) -> ConversationOutput:
        return self._inner.respond(history, incoming)  # type: ignore[attr-defined, no-any-return]

    def _think(self, observation: dict[str, Any], legal_actions: list[Any]) -> str:
        role = "psychic" if is_free_text(legal_actions) is not None else "guesser"
        # The guard re-asks a rejected move with a changed observation: think once per turn.
        key = (role, observation.get("round"), observation.get("clue"))
        if key == self._key:
            return self._notes
        try:
            reply = self._inner.respond([], TextTurn(text=thinking_prompt(role, observation)))  # type: ignore[attr-defined]
        except CallCapExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - the move can still be made without notes
            log.warning("thinking failed, moving without notes: %r", exc)
            return ""
        text = reply.text.strip()[:MAX_NOTES_CHARS] if isinstance(reply, TextTurn) else ""
        self._key, self._notes = key, text
        self.last = {"round": observation.get("round"), "role": role, "text": text}
        return text
