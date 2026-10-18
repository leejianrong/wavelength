# ADR-0010: Players write working notes before each move

- Status: Accepted (Jian, 2026-10-18, after three worked examples; supersedes the "framework change" route in the V12 plan)
- Date: 2026-10-18
- Deciders: Jian

## Context

The AI players score about 1.70 points a round against 0.57 for random, short of the 2.0 target (Q19). The framework's OpenRouter backend forces one `submit_move` tool call with only `action` and `banter`, so a model cannot reason before it commits. Jian walked through three rounds by hand (Smooth/Bumpy at 22, Dizzy/Steady at 81, Sad/Happy song at 50) and described how a good psychic and a good guesser think; `src/wavelength/prompts.py` holds those checklists.

## Decision

1. **One extra plain call before each move** (`ThinkingSeat`, `thinking.py`): the model is given its checklist and its own situation and writes notes in under 200 words; the move call then has the notes appended to its instructions. This uses the backend's existing `respond` method, so no framework change is needed (the plan's "optional `thoughts` field" is not required and is not proposed).
2. **Two calls per move, both counted** by the shared `Meter`, so `--max-calls` still bounds a match. `ThinkingSeat` wraps the *metered* seat, inside `GuardedSeat`, so retries stay bounded; a rejected move is re-asked without thinking again. A failed notes call falls back to moving without notes; a call-cap error is never swallowed.
3. **The notes are the seat's own working and stay in the seat.** A psychic's notes name the target, so they go back to the same model for its move and nowhere else: not to the other seat, the chat context, a page or the hub. `ThinkingSeat.last` keeps them for V13 (which may show them after a reveal); nothing reads it yet. The thinking context is an allow-list over the seat's own observation, like `chat_context`.
4. **Opt in**: `wavelength web --think`, `python -m wavelength.eval --think`. The default changes only after `make eval-llm` shows a gain (see V12 in `docs/SLICES.md`).

## Alternatives considered

| Option | Why not |
| --- | --- |
| A framework change: a `thoughts` field in the move tool | A cross-repo change and pin bump for something `respond` already does; the notes would still be written in the same call as the move |
| Longer system prompt only | The model still commits in one step with nowhere to reason. Cheaper, but the checklists need room to be followed |
| Reasoning models or a provider's reasoning mode | Model- and provider-specific; the checklist is the content, not a mode |
| Show the psychic's notes to everyone | They contain the target. Only after the reveal, and that is V13's decision |

## Consequences

- AI-vs-AI and human-vs-AI matches cost about twice the calls and take longer per move (voice pacing hides some of it).
- The checklists are testable text; they can change without touching the engine, but any change should be re-measured.
- A leak case (`tests/integration/test_thinking.py`, `tests/e2e/test_web_players.py`) checks that a guesser's prompts have no target and no other seat's notes, and that no page receives notes.
