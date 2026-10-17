"""A stand-in vikaki hub for the browser tests: one port that serves a tiny ``/avatar`` page and
the driver WebSocket at ``/ws``. The page does what vikaki's embed does (docs/embed.md): it posts
``audio_locked`` to the ``?parent=`` origin and obeys ``unlock`` from that origin only.

Prints its origin on stdout, then runs until killed. ``--speak S`` is how long each line takes.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

PAGE = b"""<!doctype html><meta charset=utf-8><title>stub avatars</title>
<body style="margin:0;background:transparent"><p id=s>locked</p><script>
const parent = new URLSearchParams(location.search).get('parent');
let locked = true;
const tell = () => parent && window.parent.postMessage(
  {type: locked ? 'audio_locked' : 'audio_unlocked'}, parent);
addEventListener('message', (e) => {
  if (e.origin !== parent || e.source !== window.parent) return;
  if (e.data.type === 'unlock') {
    locked = false;
    document.getElementById('s').textContent = 'unlocked';
  }
  if (e.data.type === 'unlock' || e.data.type === 'audio_status') tell();
});
tell();
</script>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speak", type=float, default=0.3)
    args = parser.parse_args()

    async def handler(ws: ServerConnection) -> None:
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "hello":
                await ws.send(
                    json.dumps({"protocol_version": 1, "type": "welcome", "role": "driver"})
                )
            elif msg["type"] == "utterance":
                uid = msg["utterance_id"]
                await ws.send(json.dumps({"type": "speech_started", "utterance_id": uid}))
                await asyncio.sleep(args.speak)
                await ws.send(json.dumps({"type": "speech_finished", "utterance_id": uid}))

    def page(connection: ServerConnection, request: Request) -> Response | None:
        if request.path.startswith("/avatar"):
            headers = Headers([("Content-Type", "text/html; charset=utf-8")])
            return Response(200, "OK", headers, PAGE)
        return None  # /ws: carry on with the WebSocket handshake

    async def run() -> None:
        async with serve(handler, "127.0.0.1", 0, process_request=page) as server:
            port = server.sockets[0].getsockname()[1]
            print(f"http://127.0.0.1:{port}", flush=True)
            await asyncio.Event().wait()

    asyncio.run(run())


if __name__ == "__main__":
    main()
