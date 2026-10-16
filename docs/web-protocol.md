# Web protocol

What the browser and `wavelength web` say to each other (ADR-0006). The server is `src/wavelength/web/`; the page is `web/src/` compiled to `src/wavelength/web/static/app.js`.

The server pushes with **Server-Sent Events** and takes moves with **one POST**. It was chosen over WebSockets because play is strictly turn-based, it needs no extra library (Starlette and uvicorn are already in the lock file), and every frame is plain text a test can scan.

## The one rule

A browser is only ever sent `observation_for(<its seat>)` plus public configuration. Never `serialize`, never another seat's observation. The view is built in one place, `WebSession._view`, on the match thread. Anything new that goes to a browser needs a leak case in `tests/integration/test_web_session.py` (wire) or `web/e2e/` (page).

## `GET /events[?seat=you]`

An event stream. Only the human seat can be watched; any other seat is `404`. A page that connects (or reconnects) is sent the current state at once. A `: keepalive` comment is sent every 15 s.

`event: state`, `data:` one JSON object, sent whenever what the seat can see changes:

| field | meaning |
| --- | --- |
| `type` | `"state"` |
| `seat` | the seat this view is for (`you`) |
| `players` | `[you, opponent]` |
| `observation` | exactly the engine's `observation_for(seat)` ([ADR-0003](adr/0003-hidden-target-in-state-viewer-scoped-output.md)). The `target` key is present only when this seat is the psychic. |
| `awaiting` | `"clue"`, `"guess"` or `null`: what this seat must do now |
| `clue_limits` | `{max_words, max_chars}` once the seat has been asked for a clue, else `null` |
| `scoring` | `[{within, points}, ...]`, the public scoring bands, widest last |

`event: problem`, `data: {"type": "problem", "reason": "..."}`: the engine refused the last move (`reason` is its message, for example that a clue contains digits) or the match stopped. After a refused move the seat is asked again; nothing has changed.

## `POST /api/move`

`Content-Type: application/json`, body one of:

```json
{"type": "clue", "text": "a lazy afternoon"}
{"type": "guess", "value": 40}
```

`202 {"accepted": true}` means the move was queued, not that it was legal: the verdict arrives on the stream (a new `state`, or a `problem`). Refusals are immediate and change nothing:

| status | when |
| --- | --- |
| `400` | the body is not JSON |
| `403` | an `Origin` header names another site |
| `409` | wrong shape (a guess must be a whole number, a clue must be text), wrong turn ("it is not time to make a guess"), or not your seat. `{"error": "..."}` is safe to show a player. |
| `415` | not `application/json` |

The engine, not the server, judges clue rules and the 0 to 100 range.

## Other routes

`GET /` the page, `GET /static/*` its files, `GET /api/health` `{"ok": true}`.

## Safety

It listens on `127.0.0.1` and answers only local `Host` names (a web page elsewhere cannot reach it through DNS rebinding); a move with a foreign `Origin` is refused, so another site cannot play for you. There is no login: whoever can reach the port plays the seat.

## Not here yet

Chat with an LLM seat, spectator and peek, and voice come in V8 to V10 and will extend this page, not change the rules above.
