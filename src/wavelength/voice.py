"""Voice and faces through a vikaki hub (ADR-0006 §4, ADR-0009).

``VoiceTap`` is the only thing in this repo that talks to the hub. It is a speaker, not a
reader of the game: its methods take a seat, a line of text that is already public (a clue,
an AI guesser's banter, a chat reply) or a number of points, and nothing else. It never sees
an observation, the plan or the target, so there is nothing to filter. The one place that
decides which text is public is ``WebSession`` (the same rules as the talk log).

The hub is optional. If it cannot be reached, or fails later, the tap switches itself off,
tells ``on_status`` once, and every method becomes a no-op: the match is never held up
and never fails because of the voice. A line that does not finish within ``timeout`` is
cancelled and the match goes on.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from functools import partial
from typing import Any

log = logging.getLogger("wavelength.voice")

MAX_LINE_CHARS = 400
DEFAULT_TIMEOUT = 20.0

Line = dict[str, str]
LineListener = Callable[[Line | None], None]
StatusListener = Callable[[str], None]


def hub_seat_ids(players: Iterable[str]) -> dict[str, str]:
    """Our seat ids to the hub's table seats, in order (``/avatar?seats=2``: seat-1, seat-2)."""
    return {p: f"seat-{i + 1}" for i, p in enumerate(players)}


def reaction_for(points: int, best: int) -> dict[str, Any]:
    """A silent reaction to a round's public points: a nod and a smile for the top band, a shake
    for a miss, a plain nod in between."""
    if best > 0 and points >= best:
        return {"emotion": "happy", "gesture": "nod"}
    if points <= 0:
        return {"emotion": "sad", "gesture": "shake"}
    return {"emotion": "neutral", "gesture": "nod"}


class VoiceTap:
    def __init__(
        self,
        clients: dict[str, Any],
        hub_seats: dict[str, str],
        *,
        timeout: float = DEFAULT_TIMEOUT,
        on_line: LineListener | None = None,
        on_status: StatusListener | None = None,
    ) -> None:
        self._clients = dict(clients)
        self._hub = hub_seats
        self._timeout = timeout
        self._on_line = on_line or (lambda _line: None)
        self._on_status = on_status or (lambda _status: None)
        self._lock = threading.Lock()
        self._pending: dict[str, tuple[Any, str]] = {}  # utterance id -> (client, seat)
        self._lines: dict[str, Line] = {}
        self._active = bool(self._clients)
        for client in self._clients.values():
            client.on_event(self._heard)

    @classmethod
    def connect(
        cls,
        url: str,
        players: list[str],
        *,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        on_line: LineListener | None = None,
        on_status: StatusListener | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> VoiceTap:
        """One driver per seat (vikaki ADR-0017). Any failure gives a tap that is already off."""
        hub = hub_seat_ids(players)
        clients: dict[str, Any] = {}
        try:
            factory = client_factory or _default_client
            for player in players:
                clients[player] = factory(url, token=token, seats=[{"seat_id": hub[player]}])
        except Exception as exc:  # noqa: BLE001 - no hub, no extra installed, a busy seat: all the same
            log.warning("voice is off: %s", _reason(exc))
            for client in clients.values():
                _quietly(client.close)
            tap = cls({}, hub, timeout=timeout, on_line=on_line, on_status=on_status)
            tap._on_status("off")
            return tap
        tap = cls(clients, hub, timeout=timeout, on_line=on_line, on_status=on_status)
        tap._on_status("on")
        return tap

    @property
    def active(self) -> bool:
        return self._active

    # -- what is spoken ------------------------------------------------------

    def thinking(self, seat: str) -> None:
        """The seat's avatar looks thoughtful until it speaks or its turn ends."""

        def act(client: Any, hub: str) -> None:
            client.turn_started(hub)

        self._call(seat, act)

    def idle(self, seat: str) -> None:
        def act(client: Any, hub: str) -> None:
            client.turn_ended(hub)

        self._call(seat, act)

    def clue(self, seat: str, text: str) -> None:
        """The psychic's clue, neutral: a feeling could hint at how close the target is."""
        self._say(seat, text, kind="clue", emotion="neutral")

    def reply(self, seat: str, text: str, kind: str = "banter") -> None:
        """An AI guesser's remark with its guess, or a chat reply."""
        self._say(seat, text, kind=kind)

    def reveal(self, guesser: str, psychic: str, points: int, best: int) -> None:
        """Silent faces after the reveal, from the public points only."""
        reaction = reaction_for(points, best)

        def act(client: Any, hub: str) -> None:
            client.react(hub, seconds=2.0, **reaction)

        for seat in (guesser, psychic):
            self._call(seat, act)

    def wait(self, timeout: float | None = None) -> None:
        """Block until every line sent so far is over, or ``timeout`` (default: the tap's) runs
        out, in which case what is left is cancelled."""
        deadline = time.monotonic() + (self._timeout if timeout is None else timeout)
        with self._lock:
            waiting = list(self._pending.items())
        for uid, (client, _seat) in waiting:
            left = max(0.0, deadline - time.monotonic())
            try:
                client.wait_finished(uid, timeout=left)
            except Exception as exc:  # noqa: BLE001
                if getattr(exc, "code", None) == "timeout":
                    log.warning("a spoken line did not finish in time; cancelling it")
                    _quietly(partial(client.cancel, uid))
                else:
                    self._fail(exc)
            finally:
                with self._lock:
                    self._pending.pop(uid, None)
                    self._lines.pop(uid, None)

    def close(self) -> None:
        with self._lock:
            clients, self._clients, self._active = list(self._clients.values()), {}, False
            self._pending.clear()
        for client in clients:
            _quietly(client.close)

    # -- internals -----------------------------------------------------------

    def _say(self, seat: str, text: str, **kw: Any) -> None:
        text = text.strip()[:MAX_LINE_CHARS]
        if not text:
            return

        def send(client: Any, hub: str) -> None:
            uid = f"wl-{uuid.uuid4().hex[:12]}"
            with self._lock:  # registered first: a fast hub can answer before say() returns
                self._pending[uid] = (client, seat)
                self._lines[uid] = {"seat": seat, "text": text, "kind": kw["kind"]}
            try:
                client.say(text, seat_id=hub, utterance_id=uid, **kw)
            except BaseException:
                with self._lock:
                    self._pending.pop(uid, None)
                    self._lines.pop(uid, None)
                raise

        self._call(seat, send)

    def _call(self, seat: str, action: Callable[[Any, str], None]) -> None:
        with self._lock:
            client = self._clients.get(seat)
        if client is None:
            return
        try:
            action(client, self._hub[seat])
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def _heard(self, event: dict[str, Any]) -> None:
        kind, uid = event.get("type"), event.get("utterance_id")
        with self._lock:
            line = self._lines.get(uid) if isinstance(uid, str) else None
        if line is None:
            return
        if kind == "speech_started":
            self._on_line(line)
        elif kind in ("speech_finished", "speech_interrupted"):
            self._on_line(None)

    def _fail(self, exc: BaseException) -> None:
        with self._lock:
            was = self._active
        if not was:
            return
        log.warning("voice is off: %s", _reason(exc))
        self.close()
        self._on_line(None)
        self._on_status("off")


def _default_client(url: str, **kw: Any) -> Any:
    from vikaki_client import Vikaki  # the optional `voice` extra

    return Vikaki(url, **kw)


def _reason(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {getattr(exc, 'code', '') or exc}"


def _quietly(action: Callable[[], Any]) -> None:
    try:
        action()
    except Exception:  # noqa: BLE001 - closing a dead connection
        pass
