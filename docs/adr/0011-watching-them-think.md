# ADR-0011: Watching them think: public needle drafts, the guesser's thoughts, a silent psychic

- Status: Accepted (Jian, 2026-10-19: the derived walk and a collapsed notes panel, with V15 as the direction; built as written) Builds on [ADR-0009](0009-voice-through-a-vikaki-stage.md) and [ADR-0010](0010-players-think-before-they-move.md); plan in `docs/SLICES.md` V13.
- Date: 2026-10-19
- Deciders: Jian

## Context

V12 made the AI players write notes before each move, but nobody sees them, and the guesser's needle jumps from the middle to its final place at the reveal. V13 shows the thinking. The risk is one thing: a psychic's notes name the target (ADR-0010 §3), and the guesser may be a human or a model in the same match. Whatever shows the thinking must not become a path for the target to the guesser.

## Decision

1. **A needle draft is a public number and is not an action.** New SSE event `draft` (`{type, seat, value, final}`), kept (`remember`) so a page that loads late sees the needle. It never reaches the engine, the move queue or a seat's observation. Only the final guess is an action, as now. It is refused outside a guess turn and for a value outside the dial range.
2. **Human guesser:** `POST /api/draft {value}` from the dial, throttled in the page (about 5 per second, last value wins) and rate-limited in the server (drop anything faster than 100 ms apart; no error). Accepted only from the human seat, only while `awaiting == "guess"`. The AI partner never reads it: a draft is shown, not given to a model.
3. **AI guesser:** the walk is *derived from the notes, not asked of the model.* `ThinkingSeat` already holds the guesser's notes in `last`. The session replays a short walk (the needle moves from the middle through up to three intermediate points to the final guess, about a second apart), where the intermediate points are fixed by a pure function of the final guess and the seed (`walk(final, round, seed)`): no extra model call and no model-chosen number, so the walk is a presentation of a number the guesser already chose, not new information. (The alternative, asking the model for `walk: [..]`, costs a tool-schema change the framework does not allow, see ADR-0010.) The lock is the real move; the reveal waits for it.
4. **The guesser's thoughts are public once the guesser has them.** A guesser's notes are built only from the clue, the spectrum and the history, so they hold nothing the page may not see. They are sent as a `thinking` event (`{seat, text}`) and spoken as subtitles in the guesser's voice, from one place in `WebSession`, only when the seat is the guesser by role. Notes are capped (first 280 characters, cut at a sentence) for the subtitle; the full text is not sent.
5. **The psychic's notes never leave the server until after the reveal.** `ThinkingSeat.last` for a psychic is read in one function, `WebSession._release_psychic_notes`, which runs only after the reveal has been published for that round. Before it, a leak test scans every SSE frame and every hub message for the notes' text.
6. **A silent psychic.** In the guess phase the tap sends nothing for the psychic seat: no `thinking`, no `say`, no `react`, no idle change. The psychic is the one the clue came from; its avatar is neutral until the reveal. (Today `_voice_clue_turn` marks the next psychic as thinking after the reveal; that is the next round's clue turn, which stays.)
7. **A reaction after the reveal.** The psychic seat gets a spoken line and a face. An AI psychic makes **one more model call** after the reveal (target and result are public by then), through the same `GuardedSeat` / `Meter` path, so `--max-calls` bounds it; its reply is a line of at most 25 words, plus the already-held notes may be shown on the page after the reveal. A failed or capped call degrades to the existing silent reaction (the face from the points). A human psychic gets the face only until V14.
8. **The dial animates the needle** between drafts in `Dial.svelte` (CSS transition) and jumps under `prefers-reduced-motion`.

## Where this is going (Jian, 2026-10-19)

The derived walk is a stopgap. The goal is an AI guesser that works the pointer the way a person does: think aloud, move the needle, ask itself whether to nudge it from there, say why, and lock it when satisfied. That is a loop of small model steps (`say`, `move_needle(value)`, `lock(value)`), each public, instead of one notes call. It is not built here, but V13 keeps it open: `draft` already carries `{seat, value, final}` and is a public number from any source, so a model-driven needle emits the same event; the thoughts line shows text in turn rather than once; and the loop would sit inside `GuardedSeat` and the `Meter` with a step cap. It needs the framework to allow a tool-using turn (ADR-0010's reason against a framework change no longer holds once the value is a loop), so it gets its own ADR and slice (V15), with the same leak rule: a guesser's steps contain nothing a page may not see, and a psychic never steps during a guess.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Send drafts through the engine as actions | Breaks "only the final guess is an action"; adds randomness-free but replayable state for no gain |
| Ask the AI guesser for a `walk` list | Needs a framework tool-schema change (ADR-0010 chose not to) and lets a model fake a path; a derived walk costs nothing |
| Stream the guesser's notes live as they are written | The framework's `respond` returns the whole text; there is no stream to tap |
| Show the psychic's notes the moment the clue is given | They name the target and the guesser (human or AI) is watching the same page |
| Let a human guesser's draft go to the AI psychic | A tell that carries nothing the psychic needs, and one more path from a page into a prompt |

## Consequences

- Three new events (`draft`, `thinking`, and the post-reveal `reaction` with the notes) join `docs/web-protocol.md`; each gets a leak case in `tests/integration/test_web_session.py` and `web/e2e/`.
- The hub allow-list in `test_voice.py` gains `react` and the reaction line; a case asserts that no message for the psychic seat leaves between the clue and the reveal.
- An AI psychic costs one more call per round (about 5 per round with notes).
- The AI guesser's walk is theatre, not a record of its thinking. The page and docs say "needle", not "its thoughts".
