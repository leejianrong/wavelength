# ADR-0004: The clue is a free-text action, validated deterministically

- Status: Accepted (upstream part shipped in framework PR #36, fw-ADR-0010/0011)
- Date: 2026-10-14
- Deciders: Jian

## Context

Every move in Tic-Tac-Toe is one of a small enumerated list. The framework assumes that: `OpenRouterBackend` forces the model's `action` to a JSON-schema `enum` of `legal_actions`, and `HumanCLIController` matches typed input against `str(action)` for each legal action. A clue is arbitrary text, so neither works as built. The guess (101 ints) is fine.

Separately, the rules forbid clues that give away position ("it's near 70", "to the left"). If the engine does not enforce at least the mechanical part, an LLM will take the shortcut.

## Decision

- Action types are `str` (clue) and `int` (guess); the phase says which is legal. In `CLUE`, `legal_actions` returns a single framework-defined free-text marker carrying constraints (`max_words`, `max_chars`). In `GUESS` it returns the ints.
- Framework (fw-ADR-0010, done): the marker is `agent_game_framework.core.FreeText`. When `legal_actions` is `[FreeText(...)]`, `OpenRouterBackend` builds `{"type": "string", ...}` instead of an `enum`, `HumanCLIController` and the CLI chat matcher accept any non-empty line, and MCP lists it as `{"free_text": ...}`. `RandomBotController` cannot play it, so this repo registers its own bot via `BOT_REGISTRY`. Games that never return the marker are unchanged.
- The engine validates in `apply_action` and raises `IllegalActionError` with a specific reason. Rules: one line; 1-6 words; at most 80 characters; no digits or spelled-out numbers; none of left, right, middle, center, centre, halfway, percent, dial, target; neither endpoint label of the current spectrum nor its words, case-insensitive.
- Semantic fairness is not judged.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Carry the clue in `SeatDecision.banter` with a dummy enum action | Banter is optional, unstructured and not part of state or history. The clue must be recorded and validated. |
| Pick from a fixed clue list | Defeats the game. |
| LLM-as-judge for clue fairness | Non-deterministic, costs a call per clue, and cannot run in CI. Left as a possible later add-on. |
| Wavelength-private controllers for free text | Duplicates and drifts from the framework adapters. |

## Consequences

Clues are structured, recorded, reproducible and testable without a model. The validator is blunt: it will reject some clever legal clues and pass some unfair ones, and will need tuning from real play (S4 is isolated for that). The framework gains a small concept that a later game (Codenames' clue word) can reuse.
