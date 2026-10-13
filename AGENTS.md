# wavelength

Cooperative two-player Wavelength for a human and an LLM, or two LLMs, on [`agent-game-framework`](https://github.com/leejianrong/agent-game-framework). If this file, `docs/`, and the code disagree, trust the code and fix the doc in the same PR.

## What and why

Python 3.12, uv. `src/wavelength/engine.py` is the game; `cli.py` registers it into the framework's CLI. The plan and its reasoning are in `docs/PLAN.md`, the build order in `docs/SLICES.md`, decisions in `docs/adr/`. Read the ADR before changing what it covers.

Done: V0 (framework changes, merged upstream), V1 (engine, clue rules, deck, dial, bot), V2 (full matches, recap). Next: V3-V5 in `docs/SLICES.md`.

## Commands

`make` lists them. The ones you will use: `make all` (everything CI runs), `make play-bot` (no key), `make play` (LLM, needs `.env`). Tests are `tests/unit` (no I/O), `tests/integration` (in-process `Match`), `tests/e2e` (the installed script, LLM mocked).

## Rules that are easy to break

- **The target must never reach the guesser.** Only `WavelengthEngine.observation_for` decides visibility. Anything new that prints or sends game data (an output, a prompt, an error message) needs a leak case in `tests/integration/test_match.py` or `tests/e2e/`. Use `observation_for(viewer)`, never `serialize`, for anything a player or LLM sees.
- **Do not add randomness to `apply_action`.** The whole round plan is drawn in `initial_state` from the seed. Bots must be deterministic given the observation.
- **The framework is pinned to a commit** in `pyproject.toml`, not a path. We rely on its registry dicts and on replacing `framework_cli.build_controller` (`cli.py`), neither of which is a public API: bump the pin deliberately and run `make all`.
- **LLM seats go through `GuardedSeat`** (`seats.py`). The framework retries an illegal move forever; the guard bounds it at 3 attempts and tells the model why. Do not bypass it for a new LLM path.
- **CI never calls OpenRouter.** Mock it (`tests/e2e/_mock_openrouter.py`). `.env` is gitignored; never log the key.

## Workflow

Branch per slice off fresh `main`; PR only, after CI is green. A costly-to-reverse decision gets an ADR (Context / Decision / Alternatives / Consequences). Install the hooks once with `make install`. See `CONTRIBUTING.md`.
