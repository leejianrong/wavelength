# ADR-0012: An AI guesser works the needle in public steps

- Status: Proposed (decisions for Jian, 2026-10-19). Fulfils the direction in [ADR-0011](0011-watching-them-think.md) "Where this is going"; plan in `docs/SLICES.md` V15.
- Date: 2026-10-19
- Deciders: Jian

## Context

V13 shows an AI guesser's notes once and then walks the needle along a path derived from its final guess. It is theatre: the model never touches the pointer. Jian's goal is a guesser that behaves like a person at the dial: say what it makes of the clue, move the needle, ask itself whether to nudge it from there and why, and lock when satisfied.

ADR-0011 said this "needs a framework tool-use turn". Reading `agent_game_framework/agents/openrouter.py` again, it does not: `respond(history, incoming)` is a plain chat call that takes a conversation history, and it is already what `ThinkingSeat` uses. A step can be one such call whose reply is a small JSON object we parse ourselves.

## Decision

1. **A step is one plain model call.** The model is told the protocol once and replies with `{"say": "<what I think, one or two sentences>", "needle": <0-100>, "lock": <true|false>}`. We keep the conversation as `history` (our prompt as `human`, its reply as `agent`), so each call sees its own earlier steps. No framework change and no new pin.
2. **`NeedleSeat` replaces `ThinkingSeat` for a guesser** (`needle_seat.py`), inside `GuardedSeat` and over the metered backend. Its `decide` runs the loop and returns the locked number as the move, with the last `say` as the banter. A psychic keeps `ThinkingSeat` (its notes and its silence in the guess phase are unchanged). Role is decided by the legal actions, as in `ThinkingSeat`.
3. **Steps reach the page as they happen.** The session binds a callback to the seat before the match starts (`on_step(seat, step)`). Each step emits the existing `draft` event (`value`, `final` on the locking step) and a `thinking` event with that step's `say`, and the line is spoken in the guesser's voice, which is awaited before the next call so the needle and the voice keep pace with the model. The page keeps this round's steps as a short running list. The derived walk of ADR-0011 stays for any guesser that does not step (`--no-needle-steps`, or a seat with no notes).
4. **Bounded.** At most 4 steps per guess; the 4th is told it must lock. Every call is counted by the shared `Meter`, so `--max-calls` still bounds a match, and a call-cap error is never swallowed. A step that fails or cannot be parsed ends the loop: lock at the last needle position, or, with none yet, fall back to the ordinary move call (`inner.decide`) with whatever it said as notes. A value outside the dial is clamped by the guard's legality check, as for any guess.
5. **Public by construction.** A step's prompt is built from the same allow-list as a guesser's notes (`thinking_context`: the clue, the spectrum, past rounds with their revealed targets), so a step holds nothing the page may not show. The psychic never steps, and nothing about a step reaches a psychic seat or the chat context.
6. **On by default in the web UI** (`--no-needle-steps` turns it off), off in `wavelength.eval` until measured (`--needle-steps` turns it on), so the eval's baseline stays one flag away. Whether stepping plays better is not assumed: it gets measured in the final eval, which Jian wants last.

## Alternatives considered

| Option | Why not |
| --- | --- |
| A native tool call (`move_needle`, `lock`) through a framework change | A cross-repo PR and a pin bump for what a JSON reply in `respond` does; the backend forces `submit_move` on `decide`, so tool-use would need a new method there too |
| One call that returns the whole list of steps | That is V13's walk with extra text: the model still never reacts to where the needle is |
| Run the loop on the session, not in a seat | The seat is where the guard, the meter and the retry bound already are; a second place that calls a model is exactly what AGENTS.md forbids |
| Let the human psychic's page nudge the AI | The guesser must be moved by its own thinking only; V14 is the human's voice, not control |

## Consequences

- A guesser with stepping makes 2 to 4 calls per guess (about 3), where notes plus move made 2. An AI-vs-AI round costs about 6 to 7 calls (was 5).
- A guess is slower: each step is a model call plus its speech. The derived walk's fixed 3.2 s goes away for stepping seats.
- `thinking` now carries several lines a round, and `draft` values come from the model. The leak tests grow to scan each step; `docs/web-protocol.md` says a `thinking` event is one step.
- ADR-0011's "needs a framework tool-use turn" is superseded by this record.
