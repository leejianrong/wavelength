"""Fan-out of server events to every connected page, across matches.

A page that connects (or reconnects) is replayed the events marked ``remember``
(the lobby, the current state, the talk log), so a reload shows the present at
once. Bodies are encoded here, once; whoever calls ``emit`` has already decided
what a browser may see.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any


class Subscriber:
    """One page's mailbox of ``(event, json)`` pairs."""

    def __init__(self) -> None:
        self.mailbox: queue.Queue[tuple[str, str]] = queue.Queue()

    def get(self, timeout: float) -> tuple[str, str]:
        return self.mailbox.get(timeout=timeout)


class Broadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[Subscriber] = []
        self._remembered: dict[str, str] = {}

    def subscribe(self) -> Subscriber:
        sub = Subscriber()
        with self._lock:
            self._subscribers.append(sub)
            for event, data in self._remembered.items():
                sub.mailbox.put((event, data))
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    def emit(self, event: str, body: dict[str, Any], *, remember: bool = False) -> bool:
        """Send to every page. Returns False (and sends nothing) when ``remember``
        is set and the body is identical to the last one remembered for the event."""
        data = json.dumps(body, sort_keys=True)
        with self._lock:
            if remember:
                if self._remembered.get(event) == data:
                    return False
                self._remembered.pop(event, None)  # re-insert last, so replay order is recency
                self._remembered[event] = data
            targets = list(self._subscribers)
        for sub in targets:
            sub.mailbox.put((event, data))
        return True

    def forget(self, *events: str) -> None:
        with self._lock:
            for event in events:
                self._remembered.pop(event, None)
