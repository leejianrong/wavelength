# Web protocol

What the browser and `wavelength web` say to each other (ADR-0006). The server is `src/wavelength/web/`; the page is `web/src/` compiled to `src/wavelength/web/static/app.js`.

The server pushes with **Server-Sent Events** and takes commands as **JSON POSTs**. It was chosen over WebSockets because play is strictly turn-based, it needs no extra library (Starlette and uvicorn are already in the lock file), and every frame is plain text a test can scan.

## The rules

1. **A browser is only ever sent what one seat may see.** The view is built in one place, `WebSession._render`, from `Match.observation_for` snapshots: a human gets their own seat's; a spectator gets the *guesser's* (so the target stays hidden until the reveal) or, with peek on, the psychic's. Never `serialize`, never both.
2. **Peek is refused whenever a human is seated**, so a human guesser can never be handed the target.
3. **Banter reaches the page only from a guess turn**, decided by the type of the move, not by what a seat claims.
4. **Raw exception text never reaches the page.** A framework error can carry a model's own output, which for a psychic could include the target. The page gets a general sentence; the details go to the server log.
5. **AI seats spend the server's OpenRouter key.** The key is never sent anywhere. Every match has a hard cap on model calls (`--max-calls`, default 200, chat included), and a start is accepted only from this server's own page.

Anything new that goes to a browser needs a leak case in `tests/integration/test_web_session.py` (the feed), `tests/e2e/test_web.py` (raw frames over HTTP) or `web/e2e/` (the page).

## `GET /events`

An event stream shared by every page. A page that connects (or reconnects) is replayed the current `lobby` or `state`, and the `talk` log, at once. A `: keepalive` comment is sent every 15 s.

`event: lobby`: no match is running (the start screen). It lists `players`, the named AI players from `--players` as `{name, model}`; the personality text is never sent. A start request may name one with `{"kind": "llm", "player": "<name>"}`.

| field | meaning |
| --- | --- |
| `llm_available` | whether an OpenRouter key was set when the server started (never the key) |
| `default_model`, `models` | the model slug to offer, and suggestions |
| `max_calls` | the cap on model calls per match |
| `rounds`, `round_options` | the default and the choices |

`event: state`: what the viewer may see, sent whenever it changes.

| field | meaning |
| --- | --- |
| `seat` | the seat whose view this is |
| `players`, `names`, `kinds` | the two seat ids, their display names, and `human` / `bot` / `llm` |
| `viewer` | `{mode: "player" \| "spectator", peek, peek_allowed}`. Only a spectator can peek. |
| `observation` | exactly the engine's `observation_for(seat)` ([ADR-0003](adr/0003-hidden-target-in-state-viewer-scoped-output.md)). `target` is present only when the shown seat is the psychic. |
| `awaiting` | `"clue"`, `"guess"` or `null`: what the human must do now (always `null` for a spectator) |
| `clue_limits` | `{max_words, max_chars}` once the human has been asked for a clue |
| `scoring` | `[{within, points}, ...]`, the public scoring bands |
| `chat_with` | the AI seat a human may chat with, or `null` |
| `voice_hub` | the origin of the vikaki hub whose avatar page the page frames, or `null` without `--voice`. Never a token. |

`event: talk`: `{messages: [{seat, text, kind: "banter" | "chat", round}]}`, the whole conversation so far (the last 60). Banter is an AI guesser's line with its guess; chat is between a human and an AI partner.

`event: voice`: `{status, line}`, sent only when the server runs with `--voice` and replayed to a new page. `status` is `on` (the hub is connected), or `off` (it could not be reached or failed: the page drops the avatars and the game is text). `line` is `null` or `{seat, text, kind}` for the line being spoken now (`kind`: `clue`, `banter`, `table_talk`), used for subtitles. The text is only what the page may already show: a clue, an AI guesser's banter, or a chat reply; never a clue turn's banter or the psychic's chat refusal.

`event: problem`: `{reason}`. After a refused human move it is the engine's own message (for example that a clue contains digits) and the seat is asked again. Otherwise it is a general sentence ("A player did not respond, so the match stopped.", "The call limit for this match was reached, so it stopped.").

## Commands

All are `POST`, `Content-Type: application/json`. `202 {"accepted": true}` means the command was taken; its outcome arrives on the stream. Refusals are immediate and change nothing: `400` not JSON, `403` an `Origin` naming another site, `415` not JSON content type, `409` anything the game will not do (`{"error": "..."}` is safe to show a player).

| route | body | effect |
| --- | --- | --- |
| `/api/start` | `{seats: [{kind, model?}, {kind, model?}], rounds, seed?}` | start a match. `kind` is `human`, `bot` or `llm` (`model` is an OpenRouter slug). At most one human; `llm` needs a key; one match at a time. |
| `/api/stop` | `{}` | end the running match and return to the start screen |
| `/api/move` | `{"type": "clue", "text"}` or `{"type": "guess", "value"}` | a human's move |
| `/api/chat` | `{"text"}` | say something to the AI partner; returns after its reply. An AI that is the psychic of this round answers with a fixed refusal and no model call ([ADR-0005](adr/0005-chat-safe-projection-for-llm-seats.md)). |
| `/api/peek` | `{"on": true \| false}` | a spectator's peek; refused (`409`) when a human is seated |

The engine, not the server, judges clue rules and the 0 to 100 range.

## Other routes

`GET /` the page, `GET /static/*` its files, `GET /api/config` the lobby message as JSON, `GET /api/health` `{"ok": true}`.

## Voice (the framed avatar page)

The page frames `<voice_hub>/avatar?seats=2&embed=1&layout=duet&hud=0&parent=<this page's origin>` with `allow="autoplay"`, and the dial is drawn over the clear band in the middle. It exchanges messages with the frame, as vikaki's `docs/embed.md` describes: it accepts `audio_locked` and `audio_unlocked` only from the frame's own window and the hub's origin, and posts `unlock` and `audio_status` only to the hub's origin. The browser never opens the hub's socket; this server does, as one driver per seat. See [voice.md](voice.md).

## Safety

It listens on `127.0.0.1` and answers only local `Host` names (a web page elsewhere cannot reach it through DNS rebinding). A command with a foreign `Origin` is refused, so another site cannot play for you or start AI matches that spend your key. There is no login: whoever can reach the port controls the game.

## Not here yet

Spoken input (VIK-69).
