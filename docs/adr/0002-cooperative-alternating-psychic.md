# ADR-0002: Cooperative two-player match with an alternating psychic

- Status: Accepted (F1 confirmed by Jian, 2026-10-14)
- Date: 2026-10-14
- Deciders: Jian

## Context

Official Wavelength is team-vs-team: one team's psychic gives a clue, the team dials, then the opposing team guesses left or right of the dial. The stated use is one human and one LLM, or two LLMs. With two players there is no opposing team to make that second guess.

## Decision

- Exactly two players. Each round one is the *psychic* (first seat in round 1, alternating) and the other the *guesser*.
- A round is two phases, `CLUE` then `GUESS`, each with a single entry in `current_players()`. Reveal and scoring happen when the guess is applied.
- Score is shared. Bands default to ±2 → 4, ±6 → 3, ±10 → 2, otherwise 0 on a 0-100 dial. A match is `rounds` rounds long (default 6). It is a win for both players if total ≥ `target_score` (default 12), otherwise `winners()` is `[]`.
- `rounds`, `target_score`, bands, `seed` and `deck` are `config` keys, validated in `initial_state`.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Competitive teams with the left/right counter-guess | Needs 3+ seats and a second guess per round; doubles the first two slices. Deferred, not rejected: it would be the first user of simultaneous `current_players`. |
| Competitive 2-player (each round's points go to the psychic or to the guesser) | Invents a rule that is neither official nor co-op, and an LLM has no reason to play a clue badly on purpose. |
| Score only, no win condition | `winners()` and the e2e checks need a terminal verdict; a threshold is a config value, not a design commitment. |

## Consequences

Simple to build, test and demo, and symmetric for human/LLM seats. It does not exercise the contract's multi-player path, which is recorded as an open risk. The win threshold is arbitrary and will need playtesting.
