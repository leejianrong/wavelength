# ADR-0014: An agent through semula is a named player

- Status: Accepted (Jian, 2026-10-26: the named-player route, one agent per match for now, a waiting screen)
- Date: 2026-10-26
- Deciders: Jian

## Context

A Claude Code session played a whole match through semula (a record and replay fake OpenAI server: a call with no recorded answer is held until an agent answers it). That needed environment variables and a hand-started server, and the start screen offered only OpenRouter models. We want the agent in the AI seat's list, with no key.

## Decision

1. **A named player with a provider.** A `[[player]]` may say `provider = "semula"` (default `"openrouter"`). Its `model` is a label (`agent/claude-code`), and its personality is optional, because the agent has its own. `--semula URL` adds a built-in "Claude Code" player when the file has none, so `make web-semula` needs no file.
2. **The same seat, another base URL.** `build_controller` builds `OpenRouterBackend(base_url=<url>/v1/projects/<project>, api_key="semula-local", timeout=<--semula-timeout, 300 s>)`, still through `metered` and `GuardedSeat`. No framework change: the backend already takes a base URL, key and timeout.
3. **Operator config, not page data.** The address, project and timeout live in `Semula`. The lobby gets `agent_available` and a per-player `agent` flag; a state frame gets `agents` (`{seat: seconds}`). A semula player is not listed, and is refused at start, unless the server has `--semula`.
4. **One call a move.** Notes and needle steps are off for an agent seat whatever the server flags say: each extra call is one more thing to answer, and the agent's own deliberation takes the place of the notes. A psychic's reaction after the reveal remains, and is answered like any call.
5. **One agent a match.** Two agent seats would use one semula project, so the agent answering the psychic's call would see the target when it answers the guesser's. A start with two is refused. (A project per seat would allow it; not built.)
6. **No key needed.** `llm_available` still means an OpenRouter key; an agent needs none. Without a key the page offers only the agent, and says so.
7. **A waiting hint.** While an agent seat is the one being waited on, the page says "Waiting for the agent in semula" and when the move gives up. A call not answered in time fails like any model failure: the match stops with the general message ("A player did not respond"), never the raw error.
8. **Replays.** In record mode a repeated prompt is served from the recording, so a replayed seed gets the old answers. This is kept: it is useful for demos and tests. The README says so.

## Alternatives considered

| Option | Why not |
| --- | --- |
| A new seat kind `agent` | Another kind through the page, the engine seats, the protocol and every test, for what is a base URL |
| Only document the env-var command | The page still offers nothing, and the key check refuses the seat |
| The MCP seat (`wavelength-mcp`) | Works, and stays, but has no seat in the lobby |
| Allow two agents with a project per seat | More setup (two projects, two subagents); refused for now |

## Consequences

- A lobby and a state frame each carry one new field; `docs/web-protocol.md` lists them.
- An agent seat is slower than any model and its quality is the agent's: a Claude Code run is not a clean measurement of any model, because one agent sees earlier prompts of the match.
- The semula address is on the server only; the e2e test scans every frame for it.
