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
| Q9 | Spectrum content and licensing | ASSUMED (232 pairs with six written zone names each since ADR-0007) | Original deck in a bundled JSON file (format 2); `--deck` overrides; no official card text | PLAN §Scope |
| Q10 | What counts as a legal clue | ASSUMED | Deterministic checks only: single line, 1-6 words, no digits, no position words (left, right, middle, center, halfway, percent), no spectrum endpoint words | ADR-0004 |
| Q11 | May a human chat with the LLM seats | ASSUMED | Yes with the guesser during the guess phase; psychic chat refused until reveal; chat is never a game action | ADR-0005 |
| Q12 | Free-text action across LLM/human/MCP adapters | DECIDED (Jian, F2) | Shipped upstream: `FreeText` marker, fw-ADR-0010 | ADR-0004 |
| Q13 | Viewer-scoped connector output | DECIDED (Jian, F2) | Shipped upstream: viewer-scoped `--json` and MCP, fw-ADR-0011 | ADR-0003 |
| Q14 | Game registration without editing the framework | ASSUMED (`BOT_REGISTRY` shipped in V0) | Console script adds to `GAME_REGISTRY`/`RENDERER_REGISTRY`, then calls `agent_game_framework.cli.main(argv)`. Checked in framework source: both are module-level dicts and `main` takes `argv` | ADR-0001 |
| Q15 | Role instructions to the LLM without a framework prompt hook | ASSUMED | Carried in an `instructions` field of the observation | PLAN §Shape S3 |
| Q16 | Failure behaviour | ASSUMED | Invalid clue/guess → `IllegalActionError` with an actionable reason, state unchanged; LLM failure → framework one-retry then `AgentTimeoutError`; never a silent fallback move | PLAN §Implementation |
| Q17 | Algorithm seat | DEFERRED | No honest baseline; a random-guess bot exists for tests only | PLAN §Scope |
| Q18 | Persistence, replay, network | DEFERRED | JSON serialize only (fw Q9, Q10) | n/a |
| Q19 | Measurable success | ASSUMED (measured 1.80 on one model, 60 rounds; 2.47 on 30 rounds after zones and a bigger deck; see SLICES V3, V8.1) | Leak suite clean; an all-mock match completes; manual eval of two LLM seats averages ≥ 2.0 points/round over 30 rounds, against 0.568 for a uniform-random guesser (computed exactly, pinned by a unit test) | SLICES V3 |
| Q20 | Versioning | ASSUMED | `schema_version: 1` on serialized state from day one; the deck file carries its own `format: 1` | ADR-0003 |
| Q21 | Web UI | ASSUMED (Jian, 2026-10-16) | Python server plus a TypeScript UI (esbuild) and an SVG dial; the browser gets only `observation_for` of its seat | ADR-0006 |
| Q22 | Voice and faces | ASSUMED (Jian, 2026-10-16) | vikaki's avatar page embedded in an iframe, driven by a `VoiceTap` over `vikaki-client`; optional, the game works without it | ADR-0006 |
| Q23 | Watching agent + agent | ASSUMED (Jian, 2026-10-16) | Target hidden until the reveal by default; opt-in peek only when no human seat exists | ADR-0006 |
| Q24 | LLM personalities | ASSUMED (Jian, 2026-10-16) | Per-seat players file; prompt reaches the model via a small framework hook, fallback a `persona` observation field | ADR-0006 |
| Q25 | Human input | ASSUMED (Jian, 2026-10-16) | Typed for now; speech waits for vikaki VIK-69 | ADR-0006 |
| Q26 | Voice engine for play | ASSUMED (Jian, 2026-10-16) | Real Kokoro voice for play, test tone in development and CI | ADR-0006 |
| Q27 | Naming the dial | ASSUMED (Jian, 2026-10-16) | Six equal zones per spectrum with hand-written names; numbers shown second; a clue may not contain a zone name | ADR-0007 |

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
