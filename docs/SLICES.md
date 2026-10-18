# Wavelength: Slices

Vertical increments. Each ends in something you can demonstrate. Slice 1 (V1) confronts the riskiest unknown: whether the framework's contract carries a hidden target and a free-text move end to end without leaking or special-casing.

V0 lived in the **framework repo** and is **done**: `leejianrong/agent-game-framework` PR #36, merged as `3d3c5dc` (package 0.2.0), cited here as fw-ADR-0010 and fw-ADR-0011. Wavelength pins that commit.

## V0: Framework prerequisites (in `agent-game-framework`) — DONE

**Delivered:** enabler for R2, R3. As built:

- `FreeText(max_words, max_chars)` marker returned as the only entry of `legal_actions`. `OpenRouterBackend` sends a string schema instead of an enum, `HumanCLIController` and the CLI chat matcher take any line (a `chat:` line stays chat), MCP lists it as `{"free_text": ...}` and `submit_action` takes `int | str`. (fw-ADR-0010)
- `agf play --json` and the renderer use the human seat's `observation_for`; no human seat, or `--omniscient`, gives the full dump as before. MCP `get_state_dump` and `submit_action` return the caller's own observation unless `build_server(omniscient=True)`; `build_server(bound_seat=...)` pins a server to one seat. (fw-ADR-0011)
- `cli.BOT_REGISTRY` for `bot:<name>`, and `agf play --config KEY=VALUE` (JSON-parsed) to reach `initial_state`.
- `examples/secretnumber`, a hidden-info free-text reference game, with unit, integration (CLI json, MCP scoping, seat binding) and e2e tests. Framework CI green (lint, unit, integration, e2e).

**Not covered by V0, and now Wavelength's job:** the chat paths. The framework's `OpenRouterBackend.respond()` builds its prompt from the chat history alone and never sees the observation, so it cannot leak the target but also knows nothing about the game. V4 therefore adds the game context itself, from the chat-safe projection.

## V1: One hidden-target round, human psychic vs bot guesser — DONE

As built: the engine already handles any number of rounds with alternating roles and the co-op verdict, because the state shape is the same; V2 adds the match-level tests and polish rather than new engine code. Play it with `wavelength play wavelength --config rounds=1 --seat A=human --seat B=bot:wl-random` (the framework CLI takes the game name as its first argument).

**Delivers:** R0, R2 (CLI), R3, R4 (partial), R7

**Build plan**

1. Repo skeleton copied from the framework's conventions: `pyproject.toml` with the pinned git dependency, `Makefile`, ruff/mypy/pytest config, CI, pre-push hook, `AGENTS.md`, `.env.example`. Installable from the first commit.
2. Spike first: prove the pinned framework installs from git and a registered stub game runs through `wavelength play`. If it cannot, stop and fix before building more.
3. `deck`: loader and validator for the bundled original spectra (`format: 1`), plus ~60 pairs.
4. `WavelengthEngine`, one round: seeded plan in `initial_state`, `CLUE` then `GUESS`, reveal, scoring, `observation_for` per ADR-0003, `serialize`/`deserialize` with `schema_version`.
5. Clue validator (ADR-0004) with actionable rejection messages.
6. `bot:wl-random` (one scripted seat for both roles: a stock clue from a short list that passes the validator, a uniform random guess; test/demo only, registered via the framework's `BOT_REGISTRY`) and the ASCII dial renderer.
7. Registration shim and console script (ADR-0001).

**Demo:** `wavelength play --config rounds=1 --config seed=7 --seat A=human --seat B=bot:wl-random`. You see the target and spectrum, type a clue, see the bot's guess, then the dial with both markers and your points. Re-run with the same seed: same spectrum and target.

**Rests on assumptions:** Q10 (clue rules are enough), Q14 (registry mutation keeps working on the pinned framework).

### Test plan

#### End-to-end

- Scripted stdin plays one round to completion; the final output contains the dial, both markers and the awarded points.
- Same seed twice yields identical transcripts (R4).
- Submitting `"it is near 70"` or `"left of centre"` is rejected with a reason, and the turn does not advance.
- `pip install` into a scratch venv and `wavelength --help` works (R7).
- Leak scan: the guesser seat's `--json` output, transcript and every error message contain neither the target value nor `target`/`plan` keys before the reveal.

#### Integration

- Drive the engine through `Match` with scripted seats for each phase; `IllegalActionError` leaves serialized state byte-identical.
- `observation_for` per viewer and phase matches the visibility table in ADR-0003, including that future rounds' plan never appears.

#### Unit

- Each clue rule: digit, spelled-out number, position word, endpoint word (case-insensitive), 7 words, empty, multi-line.
- Scoring at each band edge (2/3, 6/7, 10/11) and at dial ends 0 and 100.
- Deck loader rejects duplicate spectra, an unknown `format`, and an empty label.
- `initial_state` rejects 1 or 3 players and `rounds < 1`.
- `serialize`/`deserialize` round-trip mid-round, and reject an unknown `schema_version`.

## V2: Full match, role alternation, both seats scripted — DONE

As built: the engine already carried multi-round state from V1, so V2 added the end-of-match recap table in the renderer, whole-match e2e and integration tests (incl. a mid-match dump resumed to an identical transcript), and the exact random-guess baseline (0.568 points/round, a unit test rather than a 10,000-round simulation). The guard tests were also proven by temporarily leaking the target and watching five tests go red. Left alone: the framework prints "Game over. Draw." after a lost co-op match.

**Delivers:** R1 (human/bot mix), R4, co-op win/lose

**Build plan**

1. Multi-round state: roles alternate, cumulative score, `rounds`/`target_score`/bands from `config`, terminal after the last reveal, `winners()` per ADR-0002.
2. Zero-human matches run without an API key via `bot:wl-random`. Simulate 10,000 random-guess rounds to pin the baseline points/round that Q19 compares against (the ≈ 0.6 in QUESTIONS is a hand estimate).
3. Config via the framework's `--config` (`rounds`, `seed`, `target_score`, `deck`); end-of-match summary.
4. Mid-match save/restore via `serialize`/`deserialize`.

**Demo:** `wavelength play --seat A=bot:wl-random --seat B=bot:wl-random --seed 3` plays 6 rounds to a score and a win/lose line with no input. Then the same with `A=human` and watch roles swap each round.

**Rests on assumptions:** Q5 (rounds, bands, threshold), Q6 (who starts).

### Test plan

#### End-to-end

- All-bot match completes with no stdin and prints a final total and verdict; exit code 0 for a win and a loss alike.
- Human + bot match with scripted input alternates roles for 6 rounds; the human is psychic in rounds 1, 3, 5.
- `--json` for the guesser at every turn of a full match contains no unrevealed target.

#### Integration

- `Match` runs 6 rounds, `is_terminal` becomes true exactly once, `winners()` is both players when total ≥ threshold and `[]` otherwise.
- Serialize after round 3, restore into a fresh `Match`, finish; transcript equals the uninterrupted run.

#### Unit

- Role alternation for odd/even `rounds`.
- Threshold boundary: total = threshold wins, threshold − 1 loses.
- Config validation for `target_score` > max possible (accepted, always loses) and negative values (rejected).

## V3: LLM seats in both roles, all-LLM matches — DONE (live-model quality unmeasured)

As built: the seats work through the framework's `llm:openrouter/<model>` spec, wrapped by `GuardedSeat` (`seats.py`): up to 3 attempts per clue with the rejection reason fed back, quote-wrapped clues tidied, and **no banter on a clue turn** (the framework prints banter to the other seat's terminal and the psychic knows the target; found while reviewing, not in the original plan). Role instructions were rewritten (guesser sees the clue and scoring; psychic told its banter is hidden). `make eval-llm` (`wavelength.eval`) scores two seats against the exact random baseline (0.568). Everything is covered against a mocked endpoint; no real model has been called from here, so Q19 (>= 2.0 points/round) is still untested. Run `make eval-llm` with a key to settle it.

**Delivers:** R1 (complete), R6

**Build plan**

1. Use V0's free-text path: `--seat A=llm:openrouter/<model>` as psychic, producing a clue plus banter; as guesser, an int plus banter.
2. Role instructions in the observation's `instructions` field; confirm the framework's generic system prompt plus these produce a sensible turn (adjust text, not the framework).
3. On a rejected clue the framework's reject-and-reprompt-once policy runs; the rejection reason reaches the model.
4. Mocked-HTTP e2e fixtures for both roles; `make eval-llm` (manual, needs a key) plays 30 rounds between two models and prints mean points/round next to the random-guess baseline.

**Demo:** `make demo` plays human vs an LLM: the LLM gives you a clue and you dial; next round you clue and it dials. `make demo-ai-vs-ai` runs two LLMs with banter, no human.

**Rests on assumptions:** Q19 (the ≥ 2.0 points/round target is reachable by the chosen models; if not, the number is wrong or the clue rules are, and the eval output shows which), Q15 (instructions in the observation are enough).

### Test plan

#### End-to-end

- With HTTP mocked, an LLM psychic vs LLM guesser match completes 6 rounds with zero human input.
- A mocked LLM clue containing a digit is rejected, re-prompted once, and on a second failure raises the framework's `AgentTimeoutError`; state is unchanged.
- Leak scan over the full mocked transcript and every request body sent to the mocked endpoint for the **guesser** seat: no target value, no `target` key.

#### Integration

- The request body for an LLM psychic includes the target and instructions; for an LLM guesser it does not (asserted on the captured request).
- Guess outside `0..100` from a mocked model is rejected like any `IllegalActionError`.

#### Unit

- Instruction text builder renders spectrum labels and constraints for each role.
- Model-output parser handles a clue with quotes, trailing whitespace and a newline (normalized or rejected, per the validator).

**Live check (2026-10-16, `deepseek/deepseek-v4.1-flash` both seats, 6 seeds x 6 rounds, under 1 cent):** clues were legal and good (1.92 points/round on the 24 rounds played, against 0.568 random; Q19's 2.0 not yet settled), `GuardedSeat`'s clue limit was never hit, but the model sent 15 guesses as digit strings (`"35"`), which the engine rejected; three of six matches stalled on it. Fixed by guess normalisation and the same 3-attempt bound on guess turns in `GuardedSeat`. `make eval-llm` now survives refused moves, counts model calls, rejected clues and non-int guesses, takes `EVAL_SEEDS` and a hard `MAX_CALLS` cap, and can print every round. Multi-model comparison is still one pair per run.

**Rerun after both fixes (2026-10-16, `deepseek/deepseek-v4.1-flash` both seats, 10 seeds x 6 rounds, 124 of 300 allowed calls, under 1 cent):** all 60 rounds played, **1.80 points/round** against 0.568 random (12 bullseyes), 0 moves refused by the engine, the guard's 3-attempt limit never hit. 4 of 64 clue attempts were rejected by the rules (each fixed on the next try) and 11 of 60 guesses arrived as text and were coerced. Q19 asks for 2.0: one model, 60 rounds, so the gap is within noise but the target is not shown to be met. One model in self-play only; other models are unmeasured.

## V4: Guess-phase chat with a leak-proof projection — DONE

As built: `chat_guard.chat_context` is an allow-list projection (it never copies the observation), a bound `GuardedConversableSeat` refuses chat while its seat is the psychic without calling the model, and `BoundMatch` (replacing `framework_cli.Match` for this process) tells each chat seat its match and seat id. Chat context is prepended to the incoming message so it is always current. Tests: unit and integration for the projection, plus live e2e against a gated mock (a move held in flight while a chat line is sent, no sleeping). The e2e found a framework bug (the live-chat loop blocked on stdin after the match ended); fixed upstream in agent-game-framework#37 and the pin moved to `8cd66e0`. Not done: the manual real-model check (`make eval-chat`) against a live psychic seat; it needs a key.

**Delivers:** R5

**Build plan**

1. Chat-safe projection and the psychic refuse-until-reveal wrapper (ADR-0005), wired to the framework's `Conversable`/`LiveMatch`.
2. `respond()` receives only the conversation history (checked in the framework source), so the wrapper must inject the game context itself, as a leading turn built from the chat-safe projection and never from the raw observation.
3. CLI: `chat:` works during an LLM guesser's decision; after the reveal chat reopens for both roles.
4. Manual check (`make eval-chat`) against a real model: ask a psychic-seat LLM for the target and confirm the refusal.

**Demo:** Human psychic gives a clue; while the LLM guesser deliberates you type `chat: why that spectrum word?` and get an answer; it then guesses. In a later round, as guesser, `chat: is it near the cold end?` gets the fixed "ask me after the reveal" reply.

**Rests on assumptions:** Q11 (chat policy), and the framework's V5 chat stays stable on the pinned version.

### Test plan

#### End-to-end

- Scripted live match: chat during an LLM guesser's in-flight `decide()` (event-synchronized, no sleeps) gets a reply and does not change game state.
- Chat addressed to an LLM psychic before reveal returns the refusal; after reveal it returns a normal reply.

#### Integration

- The captured chat request for each role and phase contains none of: the target, the unrevealed plan, `target` keys.
- A chat message never changes the next `decide()` request body (history isolation, ADR-0005).

#### Unit

- Projection function output for each phase and role matches the visibility table.
- Wrapper returns the refusal without invoking the backend (backend call count is 0).

## V5: MCP seat for an external agent — DONE

As built: `wavelength-mcp` (`wavelength.mcp_server`) wraps the framework's MCP server with `bound_seat` and the default viewer-scoped output, plus the guarded opponent seat (`--opponent-spec bot:wl-random` or `llm:openrouter/<model>`). Covered in-process (a six-round match as guesser, psychic clue validation, rejected clue changes nothing, another seat refused, malformed payloads rejected) and over real stdio against the installed script. Not done: a run with Claude Code itself; the README has the `claude mcp add` line to try it.

**Delivers:** R8

**Build plan**

1. `wavelength.mcp_server`: framework MCP server bound to one seat with the registered engine, viewer-scoped by V0's default.
2. Document the tool flow for a coding agent, including the clue's free-text `submit_action` payload.
3. README with quick start, the leak guarantee and its limits, the trademark note, and a demo transcript.

**Demo:** A scripted MCP client (or Claude Code pointed at the server) bound to seat B plays 6 rounds against an LLM or bot psychic, calling `get_observation` / `submit_action`, and never receives a target.

**Rests on assumptions:** V0's viewer-scoped dumps and that the pinned MCP server allows per-seat binding with a registered game.

### Test plan

#### End-to-end

- Test MCP client plays a full match as the guesser over stdio and reaches a terminal state; a transcript scan finds no unrevealed target in any tool result.
- Same client as psychic submits a free-text clue and an invalid clue returns a structured tool error with the reason.

#### Integration

- `list_legal_actions` in the clue phase returns the free-text marker in a JSON-safe shape.
- `get_state_dump` without the omniscient flag equals the viewer's observation.

#### Unit

- MCP input schema rejects a non-string clue and a non-int guess before the engine sees them.

# Playable: web UI, voice and faces (ADR-0006)

The terminal milestone is met (V0-V5). These slices make it a game you can sit down and play: a dial you can see, an LLM partner with a voice and a face (vikaki), human + agent or agent + agent, and personalities. The order puts the riskiest unknown first (does vikaki's page embed and speak in another page?) and keeps vikaki optional throughout.

**vikaki dependencies** (their board 35, epic VIK-E6; they are in active development and asked for these): VIK-64 embed mode, VIK-65 framing from another origin, VIK-66 audio unlock, VIK-67 speech events to the parent, VIK-68 duet layout. Later: VIK-69 human speech input, VIK-70 generic overlay decision. V6 runs on what vikaki has today; V10 uses whichever of VIK-64 to 68 have landed and works around the rest.

## V6: Spike: vikaki's avatar page in another page's iframe

**Delivers:** the answer to ADR-0006's one real unknown, plus the list of what to ask vikaki for next.

**Build plan** (throwaway code in `spikes/`, a short write-up in `docs/spikes/`)

1. Run a vikaki hub with the fake voice, then Kokoro. Serve a bare page on another port that embeds `/avatar?seats=2` and a button.
2. Check, in a real browser (also Windows Chrome with the server in WSL): does it frame at all, does audio play after a click on the parent, does the page connect to the hub, how large and responsive is it.
3. Drive it from a small Python script with `vikaki-client`: speak a line from seat 1 then one from seat 2, wait for `speech_finished`, cancel mid-line. Measure time to first audio with Kokoro.
4. List what failed and map each to VIK-64 to 68 or a new card.

**Demo:** a page with two avatars you can hear, driven by a script, with the numbers in the write-up.

**Rests on assumptions:** Q22. If framing or audio cannot work, ADR-0006 is revised (own audio in the page, or vikaki component work) before V7 builds on it.

### Test plan

Manual, but recorded: the write-up names the browser and OS combinations tried and what happened. No CI.

## V7: Web UI, human vs bot — DONE

As built: `wavelength web` (`src/wavelength/web/`): a Starlette app on uvicorn, a `WebSession` that runs the match on a thread, and a TypeScript page (`web/`, strict, esbuild). Transport is Server-Sent Events for state and one POST for moves, not a WebSocket (no extra library, strict turns, plain-text frames; see `docs/web-protocol.md`). Chat is not here: the opponent is a bot, so the chat box moves to V8 with LLM seats. Leak coverage: integration (feed equals the reference `observation_for` stream, guesser frames hold no current or later target), pytest e2e over real HTTP (every raw frame allow-listed and scanned), Playwright (the guesser's DOM has no target marker or text), each proven by mutation. CI gets a `web` job (Node 24, typecheck, unit, Chromium).

**Delivers:** the graphics, with no LLM or voice.

**Build plan**

1. `wavelength.web`: a Python server (Starlette and uvicorn, already locked via `mcp`, now direct dependencies) that runs a match on a thread, serves static files and an event stream. One connection is bound to one seat. It sends `observation_for(seat)`, a reveal after each guess, chat lines and errors. It accepts `clue`, `guess` and `chat` messages and returns the engine's rejection reasons.
2. Static page (strict TypeScript compiled with esbuild; `make web-build`, `tsc --noEmit` in `make all`): spectrum and clue panel, an SVG dial you drag or type into, the reveal with both markers, the points, a score recap. Layout works at phone width. (The chat box is V8.)
3. `wavelength web` command and `make web` (bot opponent, no key).
4. Message set documented in `docs/web-protocol.md`; AGENTS.md gains the rule that the browser feed comes only from `observation_for`.

**Demo:** `make web`, open the page, play 6 rounds against `bot:wl-random` with the mouse.

**Rests on assumptions:** Q21.

### Test plan

#### End-to-end (Playwright, mocked everything)

- A scripted browser plays a whole match; the final recap shows the right total.
- A rejected clue shows the reason and the turn does not advance.
- **Leak:** every WebSocket frame the guesser's browser receives, for a whole match, contains no unrevealed target, `target` key or plan; the same scan on the page's DOM text before the reveal.

#### Integration

- The feed for seat A and seat B at each phase equals `observation_for`. A message for the wrong seat or phase is refused with a reason and changes no state.

#### Unit

- Message validation (a guess must be an int 0-100; a clue a non-empty string). The dial's pixel-to-value maths.

## V8: LLM seats in the web UI, and watch mode — DONE

As built: the server starts on a start screen; a `Host` owns one match at a time (`/api/start`, `/api/stop`) and a `Broadcaster` keeps the event stream across matches. Each seat is a human, the bot, or an AI (an OpenRouter slug) built through `GuardedSeat` and a shared `Meter`, so every match has a hard call cap (`--max-calls`, default 200; chat counts). A spectator's default view is the guesser's `observation_for`; peek swaps in the psychic's and is refused whenever a human is seated. Guess-turn banter and human-AI chat share a `talk` log; chat goes through `LiveMatch.send_chat`, so the psychic refusal and the `chat_guard` allow-list apply unchanged. Review found and fixed a V7 leak path: raw exception text was forwarded to the page and a framework parse error can carry a model's output, so the page now gets general sentences and the detail goes to the server log. Leak coverage, each proven by mutation: integration (spectator default, peek, human peek refused, banter only from guesses, failure text, cap), pytest e2e over real HTTP with a mocked OpenRouter (including the guesser LLM's captured requests), and Playwright (start screen, play and chat, psychic refusal, watch and peek, end match, phone width). Not here: a thinking indicator beyond the text line, and voice (V10).

**Delivers:** play with an LLM partner and watch two LLMs, in the browser.

**Build plan**

1. Seat choices on a start screen (human, bot, LLM with a model), each through `GuardedSeat` as before.
2. Thinking and speaking indicators, banter lines, guesser chat while the LLM decides (the existing `chat_guard`).
3. Watch mode for an agent + agent match: guesser's view by default; an opt-in **peek** that switches to the psychic's `observation_for`, refused by the server whenever any seat is human.
4. A start/stop control and a call cap so a watch session cannot run up cost unbounded.

**Demo:** human vs LLM in the browser; then two LLMs playing while you watch, target hidden until each reveal, peek on request.

**Rests on assumptions:** Q23.

### Test plan

#### End-to-end

- Mocked-LLM human vs LLM and LLM vs LLM matches complete in the browser.
- **Leak:** in a match with a human guesser, a peek request is refused and no frame holds the target; in a match with no human, the default feed holds no target before the reveal.
- The guesser LLM's captured requests still contain no target (the V3 check, now through the web path).

#### Integration

- Peek on/off per seat configuration, including a human seat anywhere refusing it.

## V8.1: A bigger deck; named zones tried and reverted — DONE (ADR-0007 superseded)

V8.1 grew the deck from 61 to 232 spectra (written and pruned by hand: pairs that were categories rather than continua, like "Bark / Meow", were dropped) and gave each a set of six hand-written zone names (ADR-0007). Jian rejected the zones on 2026-10-17: he dislikes the names and a target shown as a name. **Reverted:** the target is a number again ("Your target: 27 out of 100") in the psychic panel, reveal, recap and peek; there are no zone names in the deck, the clue rules, prompts, observations or page; the dial has no six segments and the guess has no zone label (needle, scoring bands and readout stay). **Kept:** the 232 pairs, as deck format 1 (left and right only). Q27 records the reversal. **Live check after the revert (2026-10-17, deepseek-v4.1-flash both seats, 5 seeds x 6 rounds, 65 calls, cents):** 1.70 points per round against 0.57 random (3 bullseyes), 5 clue attempts rejected, 0 moves refused. With zones (2026-10-16, same model and sample size) it was 2.47, and 1.80 on the old 61-pair deck over 60 rounds; 30 rounds on one model is noisy, so none of these settles Q19's 2.0.

## V9: Personalities from seed prompts — DONE

As built: a TOML players file (`players.example.toml`; TOML not YAML so there is no new dependency) lists `[[player]]` tables with `name`, `model` and `personality`; unknown fields, a bad model slug, a duplicate name or a personality over 1200 characters are refused with the reason. `wavelength web --players FILE` adds a player picker to each AI seat on the start screen, and `--seat llm:player/<name>` starts one from the command line. The seam is `system_prompt` on `OpenRouterBackend` (agent-game-framework PR #43; the pin is now `9656286`): the text is appended to the built-in move and chat prompts, never replacing them. `make eval-llm PLAYERS=file PLAYER=name [PLAYER2=name]` compares personalities. The personality is operator config: it goes to the model only. A page receives the player's name and model (never the text); the chat context is unchanged, so `chat_guard.chat_context` needed no allow-list entry; `GuardedSeat` still drops clue-turn banter and the psychic still refuses chat. Not here: a voice persona per player (V10, when vikaki voice lands, the file gains a `voice` field), and personalities for `wavelength play` seats. **Live check (2026-10-17, Dry Sceptic vs Bright Optimist, both deepseek-v4.1-flash, 2 seeds x 6 rounds, 25 calls, under 1 cent):** 1.75 points per round, 0 moves refused; the clues differ in style. Two samples of six rounds say nothing about whether a personality plays better or worse.

**Framework change picked up with the bump:** framework PR #40 makes two AI seats reply to each other's banter in `wavelength play` (extra `chat` events, extra model calls on guess turns). It is safe here (the replier is a guesser or the psychic refusal, because roles swap at the reveal; `tests/e2e/test_llm_seat.py` now checks it) but it costs calls in an AI-vs-AI `play`/`watch`.

## V10a: The page in Svelte + Vite with Material 3 tokens — DONE (ADR-0008)

As built: the hand-rolled TypeScript DOM code is replaced by Svelte 5 components (`web/src/*.svelte`, state in `store.svelte.ts`), built by Vite to the same `static/app.js` plus `app.css` and self-hosted fonts. Look: Material 3 roles generated from a teal seed (`npm run tokens`), Bricolage Grotesque and Figtree, a tuning-dial face with tick marks, filled cards on surface-container tiers, state layers, light and dark. Behaviour is unchanged: the whole Playwright suite (13 tests) and the dial maths tests pass against it, with one fix on the way (a rejected clue must reset the sending state when the problem arrives, not on the next redraw). Not here: the avatar frame, voice and subtitles (V10b), and a floating-label text field (a plain label above an outlined field).

## V10b: Voice and faces through vikaki — DONE (ADR-0009)

As built (vikaki pinned at `1318f80`, its VIK-64 to 71 all landed): `voice.py` (`VoiceTap`, a speaker that takes public text and points only), `WebSession` speaks the clue, an AI guesser's banter and an AI chat partner's reply, holds the reveal until the clue has been said (20 s timeout, then cancel), and sends silent reactions after the reveal. The page frames `/avatar?seats=2&embed=1&layout=duet&hud=0&parent=<origin>` and draws the dial in the clear band (`Stage.svelte`); the speaker marking is vikaki's. Sound uses `audio_locked`/`unlock` with a "Turn on sound" button and any click as a chance; subtitles come from a `voice` SSE event and have a toggle. `make web-voice VIKAKI_DIR=...` starts the hub and the game; `--voice off|fake|real`, `--hub`. No hub or a failed one means a text game. How to run, WSL and the manual sound check: `docs/voice.md`. Tests: `tests/integration/test_voice.py` (fake hub, leak scan, ordering, timeout, dead hub, chat), `tests/unit/test_voice.py`, `web/e2e/voice.spec.ts` (a stand-in hub: URL, handshake, origin check, subtitles, text fallback). Checked by hand against the real hub with `--tts fake` in headless Chromium at desktop and phone width (screenshots in `docs/img/`). Checked by hand in Windows Chrome with the hub in WSL (2026-10-18, Jian): sound works, with both the fake and the real (Kokoro) voice. Not done: Firefox and Safari (untested), sound toggle (vikaki has no mute message), personas per player (the hub assigns its own in order), spoken input (VIK-69), spoken reactions.

Original plan, kept for reference:

**Delivers:** the LLM speaks and has a face, in the same page as the dial.

**Build plan**

1. `wavelength.voice.VoiceTap`: connects to the hub with `vikaki-client`, one driver per seat bound to its persona; speaks the psychic's clue, the guesser's reply, chat replies, and reactions after the reveal chosen from the public points. Built from an allow-list of fields, like `chat_context`. Failure or no hub degrades to text and a "voice off" badge.
2. The page embeds the avatar page (duet layout and the embed options as VIK-64 to 68 land); the dial sits in the middle band. The speaker is marked; subtitles show the same text.
3. Pacing per ADR-0006 §6: the guesser starts thinking once the clue text exists; the reveal waits for `speech_finished`, with a timeout.
4. `make web` starts the vikaki hub (path from an env var or a sibling checkout) and this server; `--voice off|fake|real`.
5. Docs: how to install the real voice, and what to do on WSL.

**Demo:** human vs LLM with a voice, then two LLMs with different personalities talking to each other, you watching.

**Rests on assumptions:** V6's findings, Q22 and Q26, and the vikaki cards above (or workarounds).

### Test plan

#### Integration (a fake hub, a plain WebSocket server, no vikaki needed)

- **Leak:** every message the tap sends over a whole match, in every phase and both roles, contains no target, `target`/`plan` keys or observation fields; the psychic's clue-turn emotion is neutral.
- The tap speaks the clue, never the psychic's banter or its chat refusal; a hub that never answers does not stall the match (timeout).
- Ordering: the reveal is not sent to the page before the clue's `speech_finished` or the timeout.

#### End-to-end

- One test with a real `vikaki serve --tts fake` (as vikaki's own CI does): the page loads, a line is spoken and the speech events arrive.
- Hub down: the match still completes as text and the badge shows.

## V11a: Reveal animation and an accessibility pass — DONE

As built: a reveal that arrives while you watch is staged (the needle sweeps from the middle to the guess, then the scoring bands and target appear, then the points land); a reveal already there on load, or any reveal under `prefers-reduced-motion`, is shown at rest. A polite live region announces each finished round and whose turn it is, built only from revealed rounds and the turn (never the hidden target); a new turn moves focus to its field on a fine pointer (not on phones, to keep the on-screen keyboard down); touch targets are 48 px on coarse pointers. `web/e2e/a11y.spec.ts` runs axe (WCAG 2 A and AA, including contrast) on the start screen, both turns and the recap in light and dark; it was clean before and after, so the M3 tokens pass contrast. Already covered, so left alone: keyboard play (the slider and every control), restart without a reload (New match). Still open in V11: sound and subtitle toggles, reactions and spoken input (all need voice, so they wait for V10b), the README screenshots and video.

## V10c: Per-player avatars and voices — DONE

A named player can set `voice` (a vikaki persona) in the players file; the tap binds each seat's driver to its persona, gives every other seat a persona nobody else has, falls back with a log line for one the hub lacks, and the page frames `seats=seat-1:ada,seat-2:ben` (`voice.seats` on the wire). Tests: integration with a fake hub that has personas, players unit tests, the Playwright URL check; checked against the real hub with the fake voice. Docs: `docs/voice.md`.

## Next: V11b to V14 (planned 2026-10-18, with Jian)

Order: V11b, then V12, V13, V14. Each is one branch and PR. V12 to V14 change how a round feels, so they get an ADR (what is shown, and what may leave the server) before code.

### V11b: README screenshots and a short match video

The README gets screenshots (desktop and phone, with voice) and a 10 to 30 second video of a match, recorded with the `video-demo` skill (Playwright for the web UI). The match is two named AIs with different avatars, driven against the mock OpenRouter and the real hub with the fake voice, so nothing is billed and the video is repeatable. Done when the README shows both and `docs/img/` holds the sources.

### V12: Players that think before they play

**Why:** an AI that guesses 1.70 points a round plays like it reads the clue and pulls a number. A good psychic picks a clue by imagining what a guesser will make of it; a good guesser asks why this clue and what the giver meant. Prompts alone should lift play, and the thinking is what V13 shows.

**Facts found:** the framework backend forces one `submit_move` tool call with only `action` and `banter` (`agent_game_framework/agents/openrouter.py`), so there is nowhere to put reasoning. Wavelength adds text through `system_prompt` only.

**Plan**
1. A framework change, proposed in `agent-game-framework` as its own PR and pinned here: an optional `thoughts` string in the move tool (first field, so the model writes it before it commits) and on `SeatDecision`. Fallback if declined: a first plain call that returns thoughts, then the forced move call that includes them (two calls per move, counted by the `Meter`).
2. Prompts in `src/wavelength/prompts.py` (a pure module, unit tested), added to the personality. Psychic: look at the target on the spectrum, list three or four candidate clues, for each imagine what number a stranger would guess and how far off it is, pick the one with the smallest expected miss, avoid the rules' banned forms. Guesser: say what the clue literally means, what it implies about the giver's idea of the spectrum, why they chose it over other clues, then place the guess, and say how sure they are.
3. Measure with `make eval-llm` before and after on the same seeds. Cost is printed first and Jian confirms (cents only). Done when the mean points per round is higher over at least 30 rounds, or the result is written up as not better.

**Leak rules:** a psychic's thoughts contain the target. They stay on the server, never in a prompt for the guesser, the chat context or any frame to a page, until V13 decides to show them after the reveal. `chat_context` stays an allow-list; the thoughts are not on it. A leak case scans every frame for a psychic's thoughts.

### V13: Watching them think: a live needle, thoughts, and a silent psychic

**What the viewer sees (guess phase):** the guesser's needle moves while they think, then they lock it. The psychic's avatar stays silent and shows no reaction. After the reveal, the psychic reacts: a spoken line and a face, and the page may show what they had been thinking.

**Plan**
1. **A draft needle.** New event `draft` (`{seat, value}`), public by design: the guesser's tentative position. A human guesser sends it from the dial (throttled, `POST /api/draft`); the server fans it out. An AI guesser's thinking yields a short list of tentative positions before the final one (V12's `thoughts` plus `walk: [..]`); the session replays them with pauses of about a second, then locks the final. The reveal waits for the lock as today. Drafts are refused outside a guess turn and never reach the engine: only the final guess is an action.
2. **Thoughts shown.** The guesser's thoughts appear as subtitles and in a "thinking" line under the dial, spoken in the guesser's voice if voice is on. The psychic's pre-clue thoughts are never shown during a round.
3. **A silent psychic.** In the guess phase the tap sends nothing for the psychic seat (no line, no thinking pose, a neutral idle face). A test asserts that no `utterance` or `turn_started` for the psychic seat leaves the server between the clue and the reveal.
4. **A reaction after the reveal.** The psychic seat says a line and shows a face from the public result. An AI psychic gets one more call after the reveal (the target is public by then), counted by the `Meter`, with its own thoughts allowed to be shown. A human psychic reacts by voice (V14) or only with the face.
5. The needle's travel animates smoothly in `Dial.svelte` and respects `prefers-reduced-motion` (jumps).

**Leak rules:** `draft` carries only a number the guesser chose. The psychic's thoughts reach a page only after the round's reveal, from one place in `WebSession`, and a leak case in `tests/integration/test_web_session.py` and `web/e2e/` proves none is sent earlier. Hub traffic still goes through the allow-list scan in `test_voice.py`, now including `react` and the reaction line.

### V14: Thinking aloud, for the human

**What you can do:** speak your thoughts while you move the needle, then confirm. Your words show as live subtitles and can be heard in your avatar's voice only if you choose so. Nothing you say is auto-submitted as a clue or guess.

**Blocked on vikaki:** VIK-69 (human speech to text). We also need partial transcripts while you speak, so we will comment on VIK-69 asking for interim results and a push-to-talk or voice-activity signal, before the ADR is written.

**Plan:** a microphone button (push to talk) in the page that talks to the hub through the avatar page or its own channel, per what VIK-69 provides; transcripts arrive as `heard` events to this server (one place decides what is shown); they feed the thinking line, never the move. A human psychic's silence in the guess phase is not enforced by the game, it is a rule of play shown as "you are the psychic, stay quiet until the reveal"; the mic is off for the psychic seat in the guess phase.

**Leak rules:** a human psychic's microphone is closed during the guess phase and its transcripts are dropped on the server, so the target cannot be spoken to an AI guesser through a transcript. A human guesser's words go to the AI psychic only after the reveal.

## V11: Polish and spoken input

**Delivers:** the parts that make it pleasant.

**Build plan**

1. Dial reveal animation, score recap, sound-off and subtitles toggles, keyboard play, restart without a reload, a match summary.
2. Reactions tuned (nod or shake on a good or bad score, a silent `react`): see V13.
3. Spoken human input: see V14.
4. README screenshots and a short video: see V11b.

**Demo:** a clean end-to-end session recorded for the README.

### Test plan

- Visual: screenshots reviewed at desktop and phone width, with and without voice.
- The existing leak e2e re-run unchanged.

