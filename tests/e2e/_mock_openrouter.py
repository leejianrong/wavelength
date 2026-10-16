"""Test-only local HTTP server standing in for OpenRouter's chat-completions
endpoint, so e2e tests can drive the real ``wavelength`` subprocess with an
``llm:openrouter/...`` seat and no network or key (point the subprocess at it
with ``OPENROUTER_BASE_URL``). CI never calls the real API.

It answers every POST. A move request (it carries the forced ``submit_move``
tool) gets a legal answer: a fixed clue when the ``action`` schema is a string
(free-text), else the middle entry of the ``enum``. Anything else is chat and
gets a fixed reply. Every request body is recorded so tests can assert on
exactly what the model was shown.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

CLUE = "a lazy afternoon"
BANTER = "mocked banter"
CHAT_REPLY = "mocked chat reply"


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(body)  # type: ignore[attr-defined]
        tools = body.get("tools")
        if tools:
            time.sleep(self.server.delay)  # type: ignore[attr-defined]
            gate = self.server.gate  # type: ignore[attr-defined]
            if gate is not None:
                gate.arrived.set()  # a move request is now in flight
                gate.release.wait(timeout=20)
            action_schema = tools[0]["function"]["parameters"]["properties"]["action"]
            enum = action_schema.get("enum")
            guess = self.server.guess  # type: ignore[attr-defined]
            action: Any = (
                self.server.clue  # type: ignore[attr-defined]
                if not enum
                else guess
                if guess is not None
                else enum[len(enum) // 2]
            )
            message: dict[str, Any] = {
                "tool_calls": [
                    {
                        "function": {
                            "name": "submit_move",
                            "arguments": json.dumps({"action": action, "banter": BANTER}),
                        }
                    }
                ]
            }
        else:
            message = {"content": CHAT_REPLY}
        payload = json.dumps({"choices": [{"message": message}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class Gate:
    """Holds every move request until ``release`` is set, and sets ``arrived``
    when one is waiting. Lets a test act *while a seat's decide() is in flight*
    without sleeping (chat is concurrent with a move, ADR-0009)."""

    def __init__(self) -> None:
        self.arrived = threading.Event()
        self.release = threading.Event()


@contextmanager
def mock_openrouter(
    clue: str = CLUE, gate: Gate | None = None, guess: Any = None, delay: float = 0.0
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Yield ``(base_url, recorded_request_bodies)`` for a server on a free port.
    ``clue`` is what the mocked model answers whenever it is asked for free text;
    ``delay`` seconds pass before each move is answered (to keep a watched match open);
    ``guess``, if given, is sent verbatim for every enum (guess) request instead of
    the middle entry, so a test can send ``"50"`` or garbage; ``gate``, if given,
    holds move requests (chat requests are never held)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.gate = gate  # type: ignore[attr-defined]
    server.daemon_threads = True
    requests: list[dict[str, Any]] = []
    server.requests = requests  # type: ignore[attr-defined]
    server.clue = clue  # type: ignore[attr-defined]
    server.delay = delay  # type: ignore[attr-defined]
    server.guess = guess  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    # Stand-alone, for the browser tests: print the base URL, then serve until killed.
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.0)
    args = parser.parse_args()
    with mock_openrouter(delay=args.delay) as (base_url, _):
        print(base_url, flush=True)
        threading.Event().wait()
