# ADR-0005: Chat uses a redacted projection, and psychic chat is closed until the reveal

- Status: Accepted
- Date: 2026-10-14
- Deciders: Jian (assumed default; the leak risk is load-bearing)

## Context

fw-ADR-0008/0009 let a human chat with an LLM seat at any time, decoupled from moves, including while that seat's `decide()` is in flight. In Wavelength the LLM *psychic* knows the target. If a human guesser chats with it ("is it closer to hot?"), a polite model will answer. Chat is not a game action, so no engine rule sees it.

Checked in the framework source: `OpenRouterBackend.respond()` builds its prompt from the conversation history only and never receives the observation. So the framework cannot leak the target through chat, and equally knows nothing about the game, which makes chat useless for discussing a clue. This repo has to add context, and that context is the leak risk.

## Decision

- The seat wrapper that provides `Conversable` for an LLM seat injects game context as a leading conversation turn built from a **chat-safe projection**, never the raw observation: the spectrum, round number, score and history of revealed rounds, plus, for a guesser, the clue.
- During a round in which the seat is the psychic, the wrapper's `respond()` does not call the model at all and returns a fixed in-character refusal ("I'm the psychic this round, ask me after the reveal"). It reopens after the reveal.
- Chat history is never fed back into `decide()` prompts for either role, so a chat cannot smuggle information into a move.
- The leak suite includes the chat context for every phase and role (R2, R5).

## Alternatives considered

| Option | Why not |
|--------|---------|
| Instruct the model not to reveal the target | Not enforcement. The structural guard works with a model that ignores instructions. |
| Disable chat entirely | Loses a headline feature of the framework and of this game (discussion is part of Wavelength). |
| Filter model output for the target number | Misses paraphrase ("pretty far toward cold"). |

## Consequences

Safe by construction for the target, at the cost of a dead psychic during the clue phase (a human psychic and LLM guesser is unaffected). The guesser's chat sees the clue, which is intended. A chat partner could still *infer* position from the psychic's tone, which no guard can stop.
