# Wavelength: Slices

Vertical increments. Each ends in something you can demonstrate. Slice 1 (V1) confronts the riskiest unknown: whether the framework's contract carries a hidden target and a free-text move end to end without leaking or special-casing.

V0 lives in the **framework repo** and gates V1's leak guarantee (fork F2). If F2 is answered "work around it here", V0 becomes the first step of V1 as Wavelength-private adapters and ADR-0003/0004's upstream paragraphs are rewritten.

## V0: Framework prerequisites (in `agent-game-framework`)

**Delivers:** enabler for R2, R3

**Build plan**

1. fw ADR-0010: free-text action marker in `legal_actions`, with `max_words`/`max_chars` constraints (ADR-0004 here).
2. `OpenRouterBackend`: marker → `{"type": "string"}` schema instead of `enum`; the system prompt line "must be one of legal_actions" is adjusted for that case.
3. `HumanCLIController` and the CLI's live-chat move matcher: marker → accept any non-empty line.
4. fw ADR-0011: CLI `--json` and MCP `get_state_dump`/`submit_action` return `observation_for(viewer)` by default; full `serialize` only behind an explicit omniscient flag (ADR-0003 here).
5. Game-specific bots: `build_controller` hardcodes `human`/`bot:random`, and `RandomBotController` cannot write a clue. Add a small `BOT_REGISTRY` so `bot:<name>` resolves to a game-registered factory, mirroring `GAME_REGISTRY` (ADR-0001).
6. Tag a release; Wavelength pins it.

**Demo:** In the framework's Tic-Tac-Toe example nothing changes (existing suite green). A tiny in-test fake game with a hidden field and a free-text move plays a full match through the CLI and MCP, and the hidden field never appears in `--json` or MCP output.

**Rests on assumptions:** F2 (framework may be changed).

### Test plan

#### End-to-end

- Existing framework e2e suite passes unchanged.
- Fake hidden-info game: MCP client bound to seat B never sees seat A's secret in any tool result, including `submit_action`'s return value.

#### Integration

- `OpenRouterBackend` (HTTP mocked) with a free-text marker sends a string-typed `action` schema and returns the model's text as the action; with an int list it still sends the `enum`.
- Omniscient flag off: `--json` equals `observation_for(viewer)`; on: equals `serialize`.

#### Unit

- Marker constraints round-trip through the request builder.
- `HumanCLIController` returns a typed clue with surrounding whitespace stripped and re-prompts on an empty line.

## V1: One hidden-target round, human psychic vs bot guesser

**Delivers:** R0, R2 (CLI), R3, R4 (partial), R7

**Build plan**

1. Repo skeleton copied from the framework's conventions: `pyproject.toml` with the pinned git dependency, `Makefile`, ruff/mypy/pytest config, CI, pre-push hook, `AGENTS.md`, `.env.example`. Installable from the first commit.
2. Spike first: prove the V0 pin installs and a registered stub game runs through `wavelength play`. If it cannot, stop and fix before building more.
3. `deck`: loader and validator for the bundled original spectra (`format: 1`), plus ~60 pairs.
4. `WavelengthEngine`, one round: seeded plan in `initial_state`, `CLUE` then `GUESS`, reveal, scoring, `observation_for` per ADR-0003, `serialize`/`deserialize` with `schema_version`.
5. Clue validator (ADR-0004) with actionable rejection messages.
6. `bot:wl-random` (one scripted seat for both roles: a stock clue from a short list that passes the validator, a uniform random guess; test/demo only, registered via V0's bot registry) and the ASCII dial renderer.
7. Registration shim and console script (ADR-0001).

**Demo:** `wavelength play --rounds 1 --seed 7 --seat A=human --seat B=bot:wl-random`. You see the target and spectrum, type a clue, see the bot's guess, then the dial with both markers and your points. Re-run with the same seed: same spectrum and target.

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

## V2: Full match, role alternation, both seats scripted

**Delivers:** R1 (human/bot mix), R4, co-op win/lose

**Build plan**

1. Multi-round state: roles alternate, cumulative score, `rounds`/`target_score`/bands from `config`, terminal after the last reveal, `winners()` per ADR-0002.
2. Zero-human matches run without an API key via `bot:wl-random`. Simulate 10,000 random-guess rounds to pin the baseline points/round that Q19 compares against (the ≈ 0.6 in QUESTIONS is a hand estimate).
3. CLI flags `--rounds`, `--seed`, `--target-score`, `--deck`; end-of-match summary.
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

## V3: LLM seats in both roles, all-LLM matches

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

## V4: Guess-phase chat with a leak-proof projection

**Delivers:** R5

**Build plan**

1. Chat-safe projection and the psychic refuse-until-reveal wrapper (ADR-0005), wired to the framework's `Conversable`/`LiveMatch`.
2. First check what the framework passes into `respond()`; if it includes the raw observation, filter it in the wrapper, never in the engine.
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

## V5: MCP seat for an external agent

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
