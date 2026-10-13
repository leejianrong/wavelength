# ADR-0001: Wavelength is a sibling repo on a pinned framework, registered without editing it

- Status: Accepted
- Date: 2026-10-14
- Deciders: Jian (inherited from fw-ADR-0001; registration mechanism assumed)

## Context

fw-ADR-0001 says each real game is its own repo depending on `agent-game-framework`. The framework's CLI finds games through module-level dicts (`GAME_REGISTRY`, `RENDERER_REGISTRY`, `ALGORITHM_REGISTRY`) and `main(argv)` takes an argument list, so a game can be added without a plugin system. The framework is Apache-2.0, and this repo is too.

## Decision

- This repo is a Python 3.12 package `wavelength`, with the framework's toolchain and `make` targets, and a `wavelength` console script.
- It depends on the framework through a git dependency pinned to a commit (`[tool.uv.sources]`, currently `3d3c5dc`, package 0.2.0, the first with fw-ADR-0010/0011), never a local path, so a fresh clone installs. Bumping the pin is a deliberate commit. A release tag can replace the SHA if the framework starts tagging.
- `wavelength` adds its engine, renderer and test bot to the framework's registries (the bot registry is fw-ADR-0010), then calls `agent_game_framework.cli.main(argv)`. All seat parsing, LLM/chat wiring and match loops stay in the framework.
- Nothing in the framework imports `wavelength`; the dependency points one way.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Wait for a framework entry-point plugin system | Blocks on work that this one game does not justify; the registry mutation is three lines and can be replaced by a plugin system later without touching the engine. |
| Put Wavelength under the framework's `examples/` | fw-ADR-0001 reserves `examples/` for throwaway reference games. |
| Fork the framework CLI | Duplicates seat/chat wiring that already works. |

## Consequences

Cheap to start and the framework stays game-agnostic. The cost is coupling to registry internals that are not a published API: a framework refactor can break registration, which the pin and one e2e test (V1) turn into a visible failure. A later plugin mechanism would supersede S6 only.
