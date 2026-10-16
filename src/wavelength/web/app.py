"""HTTP surface of the web UI: a page, an event stream and one move endpoint.

``GET /events`` is a Server-Sent Events stream of what one seat may see.
``POST /api/move`` submits a clue or a guess; the engine's verdict comes back on
the stream (``state`` or ``problem``), never in the response. The server listens
on localhost, answers only local ``Host`` names (DNS rebinding) and refuses a
move whose ``Origin`` is another site (a page elsewhere must not play for you).
"""

from __future__ import annotations

import asyncio
import queue
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from wavelength.web.moves import MoveRejected
from wavelength.web.session import WebSession

STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]", "testserver"]


def create_app(
    session: WebSession, allowed_hosts: list[str] | None = None, static: Path = STATIC
) -> Starlette:
    async def index(request: Request) -> Response:
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})

    async def events(request: Request) -> Response:
        seat = request.query_params.get("seat", session.human)
        try:
            sub = session.subscribe(seat)
        except KeyError:
            return JSONResponse({"error": "unknown seat"}, status_code=404)

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
                session.unsubscribe(sub)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
        )

    async def move(request: Request) -> Response:
        origin = request.headers.get("origin")
        if origin is not None and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"error": "cross-site request refused"}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"error": "send application/json"}, status_code=415)
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "that is not JSON"}, status_code=400)
        seat = payload.get("seat", session.human) if isinstance(payload, dict) else session.human
        if not isinstance(seat, str):
            return JSONResponse({"error": "that is not your seat"}, status_code=409)
        try:
            session.submit(seat, payload)
        except MoveRejected as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        return JSONResponse({"accepted": True}, status_code=202)

    async def health(request: Request) -> Response:
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/", index),
            Route("/events", events),
            Route("/api/move", move, methods=["POST"]),
            Route("/api/health", health),
            Mount("/static", StaticFiles(directory=static), name="static"),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or LOCAL_HOSTS),
        ],
    )
