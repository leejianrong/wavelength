"""A guesser that works the needle in public steps (V15, ADR-0012).

``NeedleSeat`` is a ``ThinkingSeat`` for the psychic and a loop for the guesser: up to
``MAX_NEEDLE_STEPS`` plain model calls, each replying ``{"say", "needle", "lock"}`` with its own
earlier steps as history, the last one forced to lock. Each step is handed to ``on_step`` as it
happens, so a viewer sees the needle move while the model decides; the locked number is the
move. Every call is counted by the meter it wraps. A step's prompt is built from the guesser's
own allow-list (``thinking_context``), so what it says holds nothing a page may not show; a
psychic never steps.

A step that fails or cannot be parsed ends the loop: lock at the last needle, or, with none,
make the ordinary move call. A call-cap error is never swallowed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
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
from wavelength.needle import public_thoughts
from wavelength.prompts import (
    MAX_NEEDLE_STEPS,
    needle_first_prompt,
    needle_next_prompt,
)
from wavelength.thinking import ThinkingSeat

log = logging.getLogger("wavelength.needle_seat")


@dataclass(frozen=True)
class Step:
    index: int  # 1-based
    say: str
    needle: int
    final: bool


StepSink = Callable[[Step], None]


def parse_step(text: str, low: int, high: int) -> tuple[str, int | None, bool] | None:
    """``(say, needle, lock)`` from a reply, or None when it holds no JSON object. The needle is
    clamped to the dial; a missing or non-numeric one is None."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        body, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    raw = body.get("needle")
    needle: int | None = None
    if isinstance(raw, bool):
        needle = None
    elif isinstance(raw, int):
        needle = raw
    elif isinstance(raw, float) and raw.is_integer():
        needle = int(raw)
    elif isinstance(raw, str) and raw.strip().lstrip("+-").isdigit():
        needle = int(raw.strip())
    if needle is not None:
        needle = max(low, min(high, needle))
    say = body.get("say")
    return (public_thoughts(say) if isinstance(say, str) else "", needle, body.get("lock") is True)


class NeedleSeat:
    def __init__(self, inner: SeatController[Any, Any], think: bool = True) -> None:
        self._inner = inner
        self._psychic: SeatController[Any, Any] = ThinkingSeat(inner) if think else inner
        self._on_step: StepSink | None = None
        self._guessed: dict[str, Any] | None = None
        self._role = "psychic"

    # -- wiring --------------------------------------------------------------

    def bind_steps(self, sink: StepSink) -> None:
        """Where each step goes as it happens (the session). Without one, steps are silent."""
        self._on_step = sink

    @property
    def last(self) -> dict[str, Any] | None:
        """The working of this seat's latest move: the psychic's notes (``ThinkingSeat.last``) or
        the guesser's last step. Who may see which is the caller's call (ADR-0011, ADR-0012)."""
        if self._role == "guesser":
            return self._guessed
        last = getattr(self._psychic, "last", None)
        return last if isinstance(last, dict) else None

    # -- moves ---------------------------------------------------------------

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        if is_free_text(legal_actions) is not None:
            self._role = "psychic"
            return self._psychic.decide(observation, legal_actions)
        ints = [a for a in legal_actions if isinstance(a, int) and not isinstance(a, bool)]
        if not ints or "previous_guess_rejected" in observation:
            return self._inner.decide(observation, legal_actions)  # the guard's re-ask
        self._role = "guesser"
        self._guessed = None
        return self._guess(observation, legal_actions, min(ints), max(ints))

    def respond(
        self, history: list[ConversationTurn], incoming: ConversationInput
    ) -> ConversationOutput:
        return self._inner.respond(history, incoming)  # type: ignore[attr-defined, no-any-return]

    def _guess(
        self, observation: dict[str, Any], legal_actions: list[Any], low: int, high: int
    ) -> SeatDecision[Any]:
        history: list[ConversationTurn] = []
        needle: int | None = None
        said = ""
        for index in range(1, MAX_NEEDLE_STEPS + 1):
            forced = index == MAX_NEEDLE_STEPS
            prompt = (
                needle_first_prompt(observation)
                if needle is None
                else needle_next_prompt(needle, forced)
            )
            try:
                reply = self._inner.respond(history, TextTurn(text=prompt))  # type: ignore[attr-defined]
            except CallCapExceeded:
                raise
            except Exception as exc:  # noqa: BLE001 - lock what we have, or move plainly
                log.warning("needle step %d failed: %r", index, exc)
                break
            parsed = parse_step(reply.text, low, high) if isinstance(reply, TextTurn) else None
            if parsed is None:
                log.warning("needle step %d was not a step", index)
                break
            say, moved, lock = parsed
            history += [
                ConversationTurn(role="human", content=TextTurn(text=prompt)),
                ConversationTurn(role="agent", content=reply),
            ]
            if moved is None and needle is None:
                break  # no needle yet and none given: nothing to show
            needle = needle if moved is None else moved
            said = say or said
            final = lock or forced
            assert needle is not None
            self._remember(observation, said or "")
            if self._on_step is not None:
                self._on_step(Step(index=index, say=say, needle=needle, final=final))
            if final:
                return SeatDecision(action=needle, banter=None)
        if needle is not None:
            if self._on_step is not None:  # the loop ended early: lock where the needle is
                self._on_step(Step(index=index, say="", needle=needle, final=True))
            return SeatDecision(action=needle, banter=None)
        return self._inner.decide(observation, legal_actions)

    def _remember(self, observation: dict[str, Any], text: str) -> None:
        self._guessed = {"round": observation.get("round"), "role": "guesser", "text": text}
