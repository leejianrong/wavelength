# Questions

Statuses: `DECIDED` (user answered) · `ASSUMED` (default taken, correct it if wrong) · `FORK` (waiting on the user) · `DEFERRED` (not needed this milestone).

## Open forks

This run was non-interactive, so both forks have their **recommendation applied provisionally**. Reply on the draft PR to confirm or overturn; either is cheap to apply now and expensive after V1.

| ID | Question | Recommendation | What changes |
|----|----------|----------------|--------------|
| F1 | Cooperative 2-player (alternating psychic, shared score) or competitive teams (opposing left/right counter-guess)? | Cooperative. It is the only mode that fits 1 human + 1 LLM, or 2 LLMs. | Competitive needs teams, 3+ seats, an extra or simultaneous phase and a winner rule. It would be the first real use of `current_players() > 1` (good for the framework) but roughly doubles V1-V2. |
| F2 | May this project change the framework repo (free-text actions, viewer-scoped dumps, a bot registry), or must it work around it here? | Change the framework: one small additive PR (V0), consumed by tag. | The workaround is a private copy of the OpenRouter, human-CLI and MCP adapters here, each drifting from the framework, and hidden-info safety would rest on every copy being re-implemented correctly. |

## Register

| ID | Question | Status | Answer or default | Landed |
|----|----------|--------|-------------------|--------|
| Q1 | Language and toolchain | DECIDED (inherited) | Python 3.12, uv, ruff, mypy strict, pytest, Makefile, CI, pre-push hook, copied from the framework | ADR-0001 |
| Q2 | Repo relationship to the framework | DECIDED (inherited, fw-ADR-0001) | Sibling repo, pinned git dependency | ADR-0001 |
| Q3 | Game mode | FORK F1 | Cooperative, alternating psychic | ADR-0002 |
| Q4 | Dial resolution | ASSUMED | Integer 0-100 | PLAN §Shape S2 |
| Q5 | Rounds, bands, win threshold | ASSUMED | 6 rounds; ±2/±6/±10 → 4/3/2; win at ≥ 12; all in `config` | ADR-0002 |
| Q6 | Who starts as psychic | ASSUMED | First seat in `--seat` order, alternate after | ADR-0002 |
| Q7 | Where the hidden target lives and how it is protected | DECIDED (follows from fw-ADR-0003) | In state; seeded pre-drawn plan; only `observation_for` exposes it; connector output must be viewer-scoped | ADR-0003 |
| Q8 | UI | ASSUMED | CLI + ASCII dial; web deferred | PLAN §Scope |
| Q9 | Spectrum content and licensing | ASSUMED | Original ~60-pair deck in a bundled JSON file; `--deck` overrides; no official card text | PLAN §Scope |
| Q10 | What counts as a legal clue | ASSUMED | Deterministic checks only: single line, 1-6 words, no digits, no position words (left, right, middle, center, halfway, percent), no spectrum endpoint words | ADR-0004 |
| Q11 | May a human chat with the LLM seats | ASSUMED | Yes with the guesser during the guess phase; psychic chat refused until reveal; chat is never a game action | ADR-0005 |
| Q12 | Free-text action across LLM/human/MCP adapters | FORK F2 | Upstream additive framework change | ADR-0004 |
| Q13 | Viewer-scoped connector output | FORK F2 | Upstream additive framework change | ADR-0003 |
| Q14 | Game registration without editing the framework | ASSUMED (needs a small `BOT_REGISTRY` from V0; bot specs are hardcoded today) | Console script adds to `GAME_REGISTRY`/`RENDERER_REGISTRY`, then calls `agent_game_framework.cli.main(argv)`. Checked in framework source: both are module-level dicts and `main` takes `argv` | ADR-0001 |
| Q15 | Role instructions to the LLM without a framework prompt hook | ASSUMED | Carried in an `instructions` field of the observation | PLAN §Shape S3 |
| Q16 | Failure behaviour | ASSUMED | Invalid clue/guess → `IllegalActionError` with an actionable reason, state unchanged; LLM failure → framework one-retry then `AgentTimeoutError`; never a silent fallback move | PLAN §Implementation |
| Q17 | Algorithm seat | DEFERRED | No honest baseline; a random-guess bot exists for tests only | PLAN §Scope |
| Q18 | Persistence, replay, network | DEFERRED | JSON serialize only (fw Q9, Q10) | n/a |
| Q19 | Measurable success | ASSUMED | Leak suite clean; an all-mock match completes; manual eval of two LLM seats averages ≥ 2.0 points/round over 30 rounds, against ≈ 0.6 for a uniform-random guesser | SLICES V3 |
| Q20 | Versioning | ASSUMED | `schema_version: 1` on serialized state from day one; the deck file carries its own `format: 1` | ADR-0003 |

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
