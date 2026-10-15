# ADR-0006: A web UI, with vikaki's avatar page embedded for voice and faces

- Status: Proposed (plan agreed with Jian 2026-10-16; accept when the V6 spike confirms the embed works)
- Date: 2026-10-16
- Deciders: Jian

## Context

Wavelength is terminal-only (PLAN §Scope listed a graphical dial and voice as non-goals, Q8). The goal now is to play it for real: a dial you can see, an LLM partner with a voice and a face, a human + agent match or an agent + agent match you can watch, and LLMs with distinct personalities.

[vikaki](https://github.com/leejianrong/vikaki) (sibling project, Apache-2.0, in active development) already does voice and faces: a hub plus a browser avatar page with local text-to-speech (Kokoro), lip sync, seven emotions, a thinking pose and per-seat personas. A game is a *driver* over a WebSocket (`vikaki-client` for Python, one driver per seat, ADR-0016/0017). Its poker table is a worked example. Its hub plays audio to the avatar *page*, so the voice only exists inside that page. Its MJPEG `stream` is video only and has no audio.

Four things are not yet decided: how the browser gets game data, how vikaki's output reaches the same page, how agent-vs-agent is shown without leaking, and where personalities come from.

## Decision

1. **A web UI served by a small Python server in this repo.** The server runs the match (framework `LiveMatch` thread, as for chat) and gives each browser connection **one viewer-scoped feed**: `observation_for(<seat>)` and nothing else (never `serialize`, ADR-0003). The browser sends only moves (clue, guess) and chat lines. The page holds no game logic. The wire format is a small JSON message set (observation, reveal, chat, error) defined in the V7 slice.
2. **TypeScript (strict) compiled to ES modules with esbuild, and an SVG dial.** No framework and no bundler beyond esbuild's transform; `make web-build` writes the output (gitignored) and `tsc --noEmit` is part of `make all`. Needs Node for the build only; the Python server serves the output as static files. Playwright drives the e2e tests (CI installs Chromium for that layer only). Server framework and licence are confirmed in V7 before the dependency is added. (Jian prefers TypeScript to JavaScript, 2026-10-16; the first draft said no build step.)
3. **vikaki's avatar page is embedded in an iframe**, next to the dial: `/avatar?seats=2&embed=1` (duet layout). The game page never draws a face or plays a sound itself. Needed from vikaki, filed on their board as epic VIK-E6 (VIK-64 to VIK-68): embed mode, framing from another origin, an audio unlock handshake, speech events posted to the parent, and a two-seat duet layout. The V6 spike uses what exists today to find out what actually breaks.
4. **A `VoiceTap` in this repo is the only thing that talks to the hub.** It reads public events and speaks them through `vikaki-client`, one driver per seat: the clue (psychic's avatar), the guesser's reply, chat replies, and reactions after the reveal derived from the public points. It uses an **allow-list of fields** like `chat_guard.chat_context`: never an observation, never the plan or target. Clue turns use a neutral emotion. A leak test scans everything sent to the hub.
5. **vikaki is optional.** With no hub the game is fully playable as text. The page shows "voice off" and nothing else changes.
6. **Pacing:** the guesser LLM may start thinking as soon as the clue text exists, while it is still being spoken. A guess is spoken and revealed only after the clue's speech finishes (`speech_finished`, or a timeout so a dead hub never stalls the match).
7. **Watching agent + agent:** the default view is the guesser's `observation_for`, so the target stays hidden until the reveal. An opt-in **peek** shows the psychic's `observation_for`. Peek exists only in a match with **no human seat**, so a human guesser can never be handed the target. No new visibility logic: both views come from `observation_for`.
8. **Personalities** come from a per-seat players file: `{seat, model, personality prompt, vikaki persona}`. The prompt must reach the model as system-level instruction. The framework's backend has no such hook, so the preferred route is a small framework change (an optional system-prompt addition on the OpenRouter backend), proposed there as its own PR and pinned here. Fallback if that is declined: a `persona` field in the observation (Q15 style), which is weaker. The chat-safe projection gains the persona text as an allow-listed field. Persona text is never game data, so it cannot leak the target, but the leak suite still runs with personalities on.
9. **Human input is typed** for now (clue, guess by dial or number, chat). Spoken input waits for VIK-69 (a vikaki message for human speech).

## Alternatives considered

| Option | Why not |
|--------|---------|
| Stream vikaki's MJPEG into the page | Video only, no audio, a headless Chromium to run, and more latency than the live page |
| Rebuild faces and speech in Wavelength | Duplicates vikaki and drifts; vikaki is built for this and open to requests |
| Wait for an embeddable vikaki component | Blocks the whole feature on someone else's work. An iframe works now and the embed requests make it better |
| Plain JavaScript with no build step | Possible, but the choice is TypeScript, which needs a compile step anyway |
| Vite and a full Node toolchain for the UI | More than a small page needs; esbuild alone does the transform |
| Send the full observation to the hub and let it filter | Puts the leak boundary outside this repo. The allow-list is enforced here |
| Spectator always sees the target | Spoils the guess for the person watching; kept as an opt-in peek |
| Persona only as a field in the observation | Models treat it as data, not character. Fine as a fallback |
| Put the web connector in the framework now | Premature; start here, extract the game-agnostic parts when a second game needs them |

## Consequences

- A new runtime dependency (a Python web server), a small Node build step (esbuild, TypeScript) and a browser test layer. CI cost goes up (Chromium for e2e).
- Two processes for the full experience (this server and a vikaki hub). `make web` starts both for development; they stay separate processes and ports.
- The leak surface grows: the browser feed, the hub traffic and persona text. Each gets its own leak test. AGENTS.md gains a rule when V7 and V10 land.
- Real voice is Kokoro on CPU (about 410 MB install, roughly 1.6 s to the first sentence). Dead air between turns is covered by the thinking pose and by overlapping the guesser's call with the clue's speech.
- vikaki is in active development and its protocol only grows additively, so the risk is its timelines, not breakage. Until VIK-64 to 68 land, the embed may need workarounds.
- Only one voice speaks at a time (vikaki ADR-0017). That suits strict turn alternation here.
