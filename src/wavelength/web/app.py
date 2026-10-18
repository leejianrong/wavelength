"""HTTP surface of the web UI: a page, an event stream and a few JSON endpoints.

``GET /events`` is a Server-Sent Events stream. The server pushes ``lobby`` (the start
screen), ``state`` (what the viewer may see), ``draft``, ``thinking``, ``reaction`` and ``problem``.
Commands are POSTs; their verdicts arrive on the stream. The server listens on
localhost, answers only local ``Host`` names (DNS rebinding) and refuses a command whose
``Origin`` is another site: a page elsewhere must not play, or start AI matches that
spend the API key, on your behalf. Wire format: ``docs/web-protocol.md``.
"""

from __future__ import annotations

import asyncio
import queue
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from wavelength.web.host import Host
from wavelength.web.moves import MoveRejected

STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]", "testserver"]


def _refuse(status: int, message: str) -> Response:
    return JSONResponse({"error": message}, status_code=status)


async def _command(request: Request) -> tuple[Any, Response | None]:
    """The JSON body of a command, or the response that refuses it."""
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host"):
        return None, _refuse(403, "cross-site request refused")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        return None, _refuse(415, "send application/json")
    try:
        return await request.json(), None
    except ValueError:
        return None, _refuse(400, "that is not JSON")


def create_app(
    host: Host, allowed_hosts: list[str] | None = None, static: Path = STATIC
) -> Starlette:
    async def index(request: Request) -> Response:
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})

    async def events(request: Request) -> Response:
        sub = host.broadcaster.subscribe()

        async def stream() -> AsyncIterator[str]:
            idle = 0
            try:
                while not await request.is_disconnected():
                    try:
                        event, data = await asyncio.to_thread(sub.get, 1.0)
                    except queue.Empty:
                        idle += 1
                        if idle % 15 == 0:
                            yield ": keepalive\n\n"
                        continue
                    idle = 0
                    yield f"event: {event}\ndata: {data}\n\n"
            finally:
                host.broadcaster.unsubscribe(sub)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
        )

    async def move(request: Request) -> Response:
        payload, refusal = await _command(request)
        if refusal:
            return refusal
        session = host.session
        if session is None:
            return _refuse(409, "no match is running")
        try:
            session.submit(payload)
        except MoveRejected as exc:
            return _refuse(409, str(exc))
        return JSONResponse({"accepted": True}, status_code=202)

    async def start(request: Request) -> Response:
        payload, refusal = await _command(request)
        if refusal:
            return refusal
        try:
            host.start(payload)
        except MoveRejected as exc:
            return _refuse(409, str(exc))
        return JSONResponse({"accepted": True}, status_code=202)

    async def stop(request: Request) -> Response:
        _, refusal = await _command(request)
        if refusal:
            return refusal
        host.stop()
        return JSONResponse({"accepted": True}, status_code=202)

    async def peek(request: Request) -> Response:
        payload, refusal = await _command(request)
        if refusal:
            return refusal
        session = host.session
        if session is None:
            return _refuse(409, "no match is running")
        on = payload.get("on") if isinstance(payload, dict) else None
        if not isinstance(on, bool):
            return _refuse(409, 'say whether to peek: {"on": true or false}')
        try:
            session.set_peek(on)
        except MoveRejected as exc:
            return _refuse(409, str(exc))
        return JSONResponse({"accepted": True}, status_code=202)

    async def draft(request: Request) -> Response:
        payload, refusal = await _command(request)
        if refusal:
            return refusal
        session = host.session
        if session is None:
            return _refuse(409, "no match is running")
        value = payload.get("value") if isinstance(payload, dict) else None
        try:
            session.draft(value)
        except MoveRejected as exc:
            return _refuse(409, str(exc))
        return JSONResponse({"accepted": True}, status_code=202)

    async def chat(request: Request) -> Response:
        payload, refusal = await _command(request)
        if refusal:
            return refusal
        session = host.session
        text = payload.get("text") if isinstance(payload, dict) else None
        if session is None or not isinstance(text, str):
            return _refuse(409, "no match is running" if session is None else "say some text")
        try:
            await asyncio.to_thread(session.chat, text)  # waits on a model call
        except MoveRejected as exc:
            return _refuse(409, str(exc))
        return JSONResponse({"accepted": True}, status_code=202)

    async def config(request: Request) -> Response:
        return JSONResponse(host.config())

    async def health(request: Request) -> Response:
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/", index),
            Route("/events", events),
            Route("/api/move", move, methods=["POST"]),
            Route("/api/start", start, methods=["POST"]),
            Route("/api/stop", stop, methods=["POST"]),
            Route("/api/peek", peek, methods=["POST"]),
            Route("/api/draft", draft, methods=["POST"]),
            Route("/api/chat", chat, methods=["POST"]),
            Route("/api/config", config),
            Route("/api/health", health),
            Mount("/static", StaticFiles(directory=static), name="static"),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or LOCAL_HOSTS),
        ],
    )
