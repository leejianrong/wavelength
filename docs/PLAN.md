# Wavelength: Plan

Status: built, V0-V15 (the terminal milestone V0-V5, then the web UI, voice, thinking players and speech; see `docs/SLICES.md`) · Milestone: MVP

Built on [`agent-game-framework`](https://github.com/leejianrong/agent-game-framework) (the "framework"). Conventions follow its `AGENTS.md`; framework ADRs are cited as `fw-ADR-NNNN`, this repo's as `ADR-NNNN`.

## Problem

Wavelength is a party game of shared intuition: one player (the *psychic*) sees a hidden target on a spectrum between two opposites ("Hot ↔ Cold", "Overrated ↔ Underrated") and gives a short clue; the other player (the *guesser*) turns a dial to where they think the target is. It tests whether a model can read *a particular person's* sense of "a bit past halfway to Cold", and whether a person can read the model's.

No reusable foundation plays it between one human and one LLM, or between two LLMs, with the hidden target actually enforced rather than trusted. The framework's contract was designed with Wavelength in mind (fw-ADR-0003) but has never been exercised against hidden information or a free-text move.

## Solution

`wavelength play` runs a short cooperative match in the terminal. Each round a spectrum is drawn; the psychic types (or an LLM generates) a one-line clue; the guesser sets the dial (0-100); the target is revealed on an ASCII dial and points are awarded by closeness. Roles swap each round. Either seat can be a human or an LLM, so human+LLM and LLM+LLM (zero humans) are the same code path (fw-ADR-0005). While guessing, a human can chat with an LLM guesser about the clue (fw-ADR-0008/0009) without that chat being a game move.

## Users and actors

- **Primary: Jian**, as the human seat against an LLM. Secondary: two LLM seats playing unattended, and an external agent (e.g. Claude Code) driving a seat over MCP.
- **LLM psychic / LLM guesser:** `SeatController`s via the framework's OpenRouter backend.
- When a human's CLI turn and an LLM's decision overlap, the human's turn wins; the framework never auto-advances a human seat (fw PLAN §Users).

## Scope

**In this milestone.**
- A `WavelengthEngine` implementing the framework `GameEngine` (fw-ADR-0003): 2 players, cooperative, alternating psychic, fixed round count, seeded and reproducible (ADR-0002, ADR-0003).
- Hidden target enforced in `observation_for`, and absent from everything a seat, chat partner or MCP client can read before the reveal (ADR-0003, ADR-0005).
- Free-text clue as a first-class action with a deterministic validator (ADR-0004).
- Original spectrum deck (232 pairs since V8.1) shipped in the repo, replaceable via `--deck <file>`.
- ASCII dial rendering for the CLI.
- `wavelength` console script that registers the game into the framework registries and delegates to the framework CLI (ADR-0001).
- LLM seats for both roles, all-LLM matches, and guesser-side chat with a leak-proof projection (ADR-0005).
- Stdio MCP seat binding that exposes only viewer-scoped state.
- Same Python / uv / ruff / mypy / pytest / Makefile / CI layout as the framework.

**Out.**
- Competitive team play and the opposing team's left/right counter-guess. It is the variant that would use simultaneous `current_players`, so the contract's simultaneous path stays unproven (see Open risks).
- 3+ players and team rosters. Config accepts only 2 players.
- ~~A graphical or web dial; voice.~~ No longer out: built in SLICES V6-V15 (ADR-0006 to ADR-0013) once the terminal milestone was met. Persistence and replay beyond JSON serialization. Networked play.
- A `GameAlgorithm` for Wavelength. A clue's meaning is the whole game, so there is no honest non-LLM baseline beyond a uniform-random guesser bot, which ships only as a test/e2e seat.
- Semantic clue judging (is "Sunday morning" a fair clue for Hot ↔ Cold?). Only deterministic checks are enforced (ADR-0004).
- Official Wavelength card text. The deck is original; the name is used descriptively (see Open risks).

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | One `WavelengthEngine` plays through the framework's `Match`, CLI and MCP with no Wavelength-specific connector code beyond registration | Core goal |
| R1 | Any mix of human/LLM seats works, including zero humans | Must-have |
| R2 | The target is never observable by the guesser, a chat partner, or any connector output before the reveal | Must-have |
| R3 | The clue is free text, validated deterministically; an invalid clue is rejected with a reason and the turn does not advance (fw R5) | Must-have |
| R4 | Matches are reproducible from `seed` + `rounds` + `deck`, and state round-trips through `serialize`/`deserialize` with `schema_version` | Must-have |
| R5 | A human can chat with an LLM guesser during the guess phase; an LLM psychic cannot leak the target through chat | Must-have |
| R6 | LLM seats work in both roles and produce a clue/guess plus banter | Must-have |
| R7 | The package installs from a clean venv and registers itself with the framework | Must-have |
| R8 | An agent can drive one seat over MCP | Nice-to-have |

## Shape

| Part | Mechanism | ADR |
|------|-----------|-----|
| S1 | `WavelengthEngine`: state holds a pre-drawn, seeded round plan (spectrum + target per round), scores, history and phase. Phases per round: `CLUE` (`current_players = [psychic]`) then `GUESS` (`[guesser]`); the reveal is a state transition, not a phase | ADR-0002, ADR-0003 |
| S2 | Action types: clue is `str`, guess is `int` in `0..100`; the phase disambiguates. `legal_actions` in `CLUE` returns the framework's free-text marker; in `GUESS` it returns the 101 ints | ADR-0004 |
| S3 | `observation_for`: psychic sees spectrum + target + history; guesser sees spectrum + clue (once given) + history of already-revealed rounds. Both get an `instructions` field with role rules, so no framework prompt hook is needed | ADR-0003 |
| S4 | Clue validator inside `apply_action`: single line, 1-6 words, no digits, no position words, no spectrum-endpoint words | ADR-0004 |
| S5 | Scoring: distance bands from `config` (default ±2 → 4, ±6 → 3, ±10 → 2, else 0); co-op win when total ≥ threshold after the last round | ADR-0002 |
| S6 | Registration shim: the `wavelength` entry point adds to `GAME_REGISTRY`/`RENDERER_REGISTRY`/`BOT_REGISTRY` (the last from fw-ADR-0010), then calls the framework's `main(argv)` | ADR-0001 |
| S7 | Chat-safe projection: wrapper around a seat's `Conversable` that supplies game context from a redacted view only; psychic chat is refused until the round's reveal | ADR-0005 |
| S8 | Viewer-scoped dump: framework (fw-ADR-0011, done) makes CLI `--json` and MCP tools emit `observation_for(viewer)`, not `serialize(state)`, unless `--omniscient` / `omniscient=True` | ADR-0003 |
| S9 | Free-text action support: framework `FreeText` marker handled by `OpenRouterBackend`, `HumanCLIController`, CLI chat and MCP (fw-ADR-0010, done) | ADR-0004 |

## Affordances

**CLI.**

| Affordance | Place | Wires to |
|------------|-------|----------|
| `wavelength play --seat A=human --seat B=llm:openrouter/<model>` | terminal | framework `cmd_play`, game `wavelength` registered by S6 |
| `wavelength play --seat A=llm:... --seat B=llm:...` | terminal | zero-human match, same path |
| `--config rounds=N --config seed=S --config target_score=T --config deck=file.json` | framework flag | `config` passed to `initial_state` |
| ASCII dial after each reveal | terminal | registered renderer: both spectrum labels, guess marker, target marker, points |
| `chat: <text>` while an LLM guesser is deciding | terminal | framework live chat via S7 |
| `--json` | flag | per-turn viewer-scoped output (S8) |

**Non-UI.**

| Affordance | Kind | Wires to |
|------------|------|----------|
| `python -m wavelength.mcp_server --seat A` | MCP stdio | framework MCP server bound to one seat, viewer-scoped (S8) |
| `WavelengthEngine` | library | S1-S5 |

## Implementation decisions

- Repo: sibling of the framework, Python 3.12, `src/wavelength/` (engine, deck, clue rules, render, chat guard, cli) plus a bundled `spectra.json`. Depends on the framework as a pinned git dependency (ADR-0001). Test layout and `make` targets copy the framework's (`unit`/`integration`/`e2e`).
- State is a dataclass; the full round plan is drawn once in `initial_state` from `random.Random(seed)`, so the engine is a pure function of its inputs and `apply_action` never needs an RNG (ADR-0003).
- `winners()` returns both players if the match is terminal and total ≥ threshold, else `[]`. A cooperative loss is an empty list, consistent with the contract's "empty for a draw".
- All rejects use the framework's `IllegalActionError` with a message an LLM can act on (e.g. "clue contains a digit"); the framework's one-retry policy covers the rest (fw-ADR-0005).
- `initial_state` raises `ValueError` for a non-2-player roster, `rounds < 1`, or a deck with duplicate spectra.
- Secrets: only `OPENROUTER_API_KEY` via `.env`, gitignored, never logged. The target is secret *state*, not a credential; it is kept out of logs by the same rule as ADR-0003.

## Testing approach

The highest-leverage seam is `WavelengthEngine` driven through the framework's `Match`; most tests go there. A **leak test suite** is first-class: for every phase and every viewer, scan `observation_for`, connector output, chat context and error messages for the target value and the reveal-only fields. Every LLM path mocks HTTP (fw AGENTS.md rule: CI never calls OpenRouter). Live-chat tests synchronize with `threading.Event`, not sleeps. A real-key eval is a manual local target (`make eval-llm`), never in CI. Per-slice plans are in `SLICES.md`.

## Assumed defaults

| ID | Assumed | Cost if wrong |
|----|---------|---------------|
| Q4 | Dial is integer 0-100 | Changes the guess enum size and bands; config-level, low |
| Q5 | 6 rounds, win at total ≥ 12, bands ±2/±6/±10 | Pure tuning, low |
| Q6 | First seat is psychic in round 1, then alternate | Trivial |
| Q8 | CLI + ASCII only | A web UI is additive over the same engine, low-medium |
| Q9 | Original deck, bundled, ~60 pairs | Avoids a licensing problem; pair quality is a content task |
| Q10 | Deterministic clue rules only | If LLMs routinely smuggle position hints the rules must grow; contained in S4 |
| Q11 | Chat only with the guesser; psychic chat after reveal | If wrong, either a leak (bad) or a feature gap (cheap) |

## Open risks

- **Contract validation is partial.** Cooperative alternating play exercises hidden information and a non-enumerable action, but never `len(current_players()) > 1`. The simultaneous path stays unproven until a competitive variant; nothing in this milestone reveals a problem there.
- **Framework coupling.** The upstream changes (S8, S9) are merged (framework PR #36). Wavelength relies on registry dicts that are a convention, not a published API; V1's spike and the pin on commit `3d3c5dc` contain that.
- **LLM clue quality.** Models may give flat or position-leaking clues; the deterministic validator catches only mechanical ones. Revealed by V3's manual eval.
- **Chat leak surface.** An LLM psychic's chat context is the likeliest leak; ADR-0005's structural guard is untested against a real model until V4's manual check.
- **Name.** "Wavelength" is a commercial game by Palm Court / CMYK. This repo is an independent, original-content implementation under Apache-2.0 and the README should say so.
