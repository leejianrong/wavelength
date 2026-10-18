# Questions

Statuses: `DECIDED` (user answered) · `ASSUMED` (default taken, correct it if wrong) · `FORK` (waiting on the user) · `DEFERRED` (not needed this milestone).

## Forks (all closed)

None. Round 1 closed 2026-10-14:

| ID | Question | Status | Answer |
|----|----------|--------|--------|
| F1 | Cooperative 2-player or competitive teams? | DECIDED (Jian) | Cooperative 2-player, psychic alternating each round, no competitive teams (ADR-0002) |
| F2 | May this project change the framework repo? | DECIDED (Jian) | Yes. Shipped as framework PR #36 (merge `3d3c5dc`, v0.2.0): fw-ADR-0010, fw-ADR-0011 |

## Register

| ID | Question | Status | Answer or default | Landed |
|----|----------|--------|-------------------|--------|
| Q1 | Language and toolchain | DECIDED (inherited) | Python 3.12, uv, ruff, mypy strict, pytest, Makefile, CI, pre-push hook, copied from the framework | ADR-0001 |
| Q2 | Repo relationship to the framework | DECIDED (inherited, fw-ADR-0001) | Sibling repo, pinned git dependency | ADR-0001 |
| Q3 | Game mode | DECIDED (Jian) | Cooperative, alternating psychic; competitive teams are out | ADR-0002 |
| Q4 | Dial resolution | ASSUMED | Integer 0-100 | PLAN §Shape S2 |
| Q5 | Rounds, bands, win threshold | ASSUMED | 6 rounds; ±2/±6/±10 → 4/3/2; win at ≥ 12; all in `config` | ADR-0002 |
| Q6 | Who starts as psychic | ASSUMED | First seat in `--seat` order, alternate after | ADR-0002 |
| Q7 | Where the hidden target lives and how it is protected | DECIDED (follows from fw-ADR-0003) | In state; seeded pre-drawn plan; only `observation_for` exposes it; connector output must be viewer-scoped | ADR-0003 |
| Q8 | UI | SUPERSEDED by Q21 | CLI + ASCII dial; web was deferred | PLAN §Scope |
| Q9 | Spectrum content and licensing | ASSUMED (232 pairs since V8.1) | Original deck in a bundled JSON file (format 1); `--deck` overrides; no official card text | PLAN §Scope |
| Q10 | What counts as a legal clue | ASSUMED | Deterministic checks only: single line, 1-6 words, no digits, no position words (left, right, middle, center, halfway, percent), no spectrum endpoint words | ADR-0004 |
| Q11 | May a human chat with the LLM seats | ASSUMED | Yes with the guesser during the guess phase; psychic chat refused until reveal; chat is never a game action | ADR-0005 |
| Q12 | Free-text action across LLM/human/MCP adapters | DECIDED (Jian, F2) | Shipped upstream: `FreeText` marker, fw-ADR-0010 | ADR-0004 |
| Q13 | Viewer-scoped connector output | DECIDED (Jian, F2) | Shipped upstream: viewer-scoped `--json` and MCP, fw-ADR-0011 | ADR-0003 |
| Q14 | Game registration without editing the framework | ASSUMED (`BOT_REGISTRY` shipped in V0) | Console script adds to `GAME_REGISTRY`/`RENDERER_REGISTRY`, then calls `agent_game_framework.cli.main(argv)`. Checked in framework source: both are module-level dicts and `main` takes `argv` | ADR-0001 |
| Q15 | Role instructions to the LLM without a framework prompt hook | ASSUMED | Carried in an `instructions` field of the observation | PLAN §Shape S3 |
| Q16 | Failure behaviour | ASSUMED | Invalid clue/guess → `IllegalActionError` with an actionable reason, state unchanged; LLM failure → framework one-retry then `AgentTimeoutError`; never a silent fallback move | PLAN §Implementation |
| Q17 | Algorithm seat | DEFERRED | No honest baseline; a random-guess bot exists for tests only | PLAN §Scope |
| Q18 | Persistence, replay, network | DEFERRED | JSON serialize only (fw Q9, Q10) | n/a |
| Q19 | Measurable success | ASSUMED (measured 1.80 on one model, 60 rounds; 1.70 on 30 rounds with the 232-pair deck after named zones were reverted; 2.08 with notes over 53 rounds, ADR-0010; needle steps unmeasured) | Leak suite clean; an all-mock match completes; manual eval of two LLM seats averages ≥ 2.0 points/round over 30 rounds, against 0.568 for a uniform-random guesser (computed exactly, pinned by a unit test) | SLICES V3 |
| Q20 | Versioning | ASSUMED | `schema_version: 1` on serialized state from day one; the deck file carries its own `format: 1` | ADR-0003 |
| Q21 | Web UI | ASSUMED (Jian, 2026-10-16) | Python server plus a Svelte + Vite TypeScript UI (ADR-0008) and an SVG dial; the browser gets only `observation_for` of its seat | ADR-0006 |
| Q22 | Voice and faces | ASSUMED (Jian, 2026-10-16) | vikaki's avatar page embedded in an iframe, driven by a `VoiceTap` over `vikaki-client`; optional, the game works without it | ADR-0006 |
| Q23 | Watching agent + agent | ASSUMED (Jian, 2026-10-16) | Target hidden until the reveal by default; opt-in peek only when no human seat exists | ADR-0006 |
| Q24 | LLM personalities | ASSUMED (Jian, 2026-10-16) | Per-seat players file; prompt reaches the model via a small framework hook, fallback a `persona` observation field | ADR-0006 |
| Q25 | Human input | DECIDED (Jian, 2026-10-19) | Typed, or spoken with Chrome's Web Speech API in the page (a spoken clue fills the clue box; thinking aloud is shown, never a move). Transcripts go straight to our server, not through vikaki's `human_utterance` (VIK-69). A local Whisper waits for how well Chrome hears us | ADR-0013 |
| Q26 | Voice engine for play | ASSUMED (Jian, 2026-10-16) | Real Kokoro voice for play, test tone in development and CI | ADR-0006 |
| Q27 | Naming the dial | REVERSED (Jian, 2026-10-17) | Tried six hand-written zone names per spectrum (ADR-0007) and rejected them: he dislikes the names and a target shown as a name. The target is a number ("Your target: 27 out of 100"); no zone names anywhere. The 232-pair deck stays | ADR-0007 (superseded) |
| Q28 | Do AI players think first | DECIDED (Jian, 2026-10-18) | A notes call before each move, on in the web UI (1.67 to 2.08 points a round), kept in the seat | ADR-0010 |
| Q29 | May viewers watch the thinking | DECIDED (Jian, 2026-10-19) | Public needle drafts, the guesser's thoughts, a silent psychic; the psychic's notes only after the reveal | ADR-0011 |
| Q30 | May an AI work the needle itself | DECIDED (Jian, 2026-10-19) | Up to 4 public steps of `{say, needle, lock}`, on by default in the web UI, unmeasured | ADR-0012 |

## Coverage

| Category | Covered by |
|----------|-----------|
| Primary user and actors | Q3, PLAN §Users |
| Scope boundary | Q3, Q8, Q9, Q17, Q18, PLAN §Scope |
| Data model and identity | Q7, Q20, ADR-0003 (round plan; rounds addressed by index) |
| State and storage | Q7, Q18, Q20 |
| Concurrency and conflict | ADR-0002 (strict alternation; the framework `Match` is the single writer; no simultaneous phase) |
| Interfaces and contracts | Q12, Q13, Q14, Q15 |
| Failure behaviour | Q16, ADR-0004 |
| External dependencies | Q1, Q2, ADR-0001 (framework: Apache-2.0, git pin; OpenRouter: optional, key-gated, mocked in CI; no other runtime deps planned) |
| Runtime and deployment | Q1, Q14 (local terminal; no service) |
| Measurable success | Q19 |
| Security and secrets | Q7, Q11, PLAN §Implementation (key via `.env`; the real secret is the target) |
| Versioning and migration | Q20 |
