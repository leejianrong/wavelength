# ADR-0003: The target lives in state, is exposed only by `observation_for`, and connector output is viewer-scoped

- Status: Accepted (provisional on fork F2 for the upstream part)
- Date: 2026-10-14
- Deciders: Jian (follows fw-ADR-0003; upstream part pending F2)

## Context

fw-ADR-0003 puts hidden information in `observation_for`, "enforced once, in the game's own code, not reimplemented per connector". Reading the framework as built shows that is only half true for a game like this:

- `GameEngine.serialize(state)` must round-trip the whole state, so it contains the target.
- The CLI's `--json` and the MCP server's `get_state_dump` and `submit_action` return `match.serialize()` in full. An agent on the guesser's seat would read the target in plain text.

Randomness is the other open point: the engine must stay a pure function and reproducible (R4).

## Decision

- `initial_state(players, config)` draws the whole round plan (spectrum and target for every round) from `random.Random(config["seed"])` and stores it in state. `apply_action` uses no RNG. Same seed, rounds and deck give the same match.
- `observation_for` is the only read path that decides visibility: the psychic sees the current target; the guesser sees the spectrum and clue, and targets only for rounds already revealed. Future rounds' plan is never in any observation.
- Connector output must be viewer-scoped. We change the framework (one additive PR, V0) so that CLI `--json` and MCP tools emit `observation_for(viewer)`, and the full `serialize` dump is available only behind an explicit omniscient flag. Games with no hidden information are unaffected.
- `serialize` keeps the full state with `schema_version: 1`; it is a save format, never a viewer format.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Add a `redact`/`public_state` method to `GameEngine` | A bigger contract change than the viewer-scoped default, and every future game must remember to implement it. Defaulting connectors to `observation_for` is safe without per-game work. |
| Keep the target out of state; derive it from the seed at reveal | Move the secret into a derivation nobody can see; the state could not be saved mid-game, and `serialize` could not round-trip. |
| Trust agents not to call `get_state_dump` | The point of the framework is enforced rules. |
| Work around it in this repo (F2 alternative) | Needs private copies of three adapters; see QUESTIONS F2. |

## Consequences

The leak surface collapses to `observation_for` plus whatever the connectors emit, which a single parametrized leak test can scan. It costs a framework change and a version bump before V1 can claim R2. The state file is not safe to share with a player mid-match; the omniscient flag and save format must be labelled as such.
