# wavelength

Cooperative two-player Wavelength for a human and an LLM, or two LLMs, built on [`agent-game-framework`](https://github.com/leejianrong/agent-game-framework). `docs/PLAN.md`, `docs/SLICES.md` and `docs/adr/*` say what is being built and why; this file is how to work in the repo. If they disagree with the code, trust the code and fix the doc.

## Current state

V0 (framework prerequisites, merged upstream) and V1 (one hidden-target round, human psychic vs bot guesser, plus the multi-round engine) are done. V2-V5 are planned in `docs/SLICES.md`.

## Layout

- `src/wavelength/engine.py`: `WavelengthEngine`, the only place that decides who sees a target (`observation_for`).
- `clue_rules.py`: deterministic clue checks (ADR-0004). `deck.py` + `data/spectra.json`: the original spectrum deck.
- `bots.py`, `render.py`, `cli.py`: test/demo bot, ASCII dial, and the `wavelength` script that registers into the framework registries (ADR-0001).

## Commands

```
make install   # uv sync --all-extras --dev
make play      # one round: you give the clue, a bot dials
make lint      # ruff check .
make typecheck # mypy src
make test      # unit + integration + e2e
make all       # everything CI runs
```

## Rules that are easy to break

- **The target must never reach the guesser.** Visibility is decided only in `observation_for`; connectors print the viewer's observation, never `serialize` (fw-ADR-0011). Any new output path, prompt or error message needs a case in the leak tests (`tests/integration/test_match.py`, `tests/e2e/test_cli.py`).
- **The framework is pinned to a commit** in `pyproject.toml` (`[tool.uv.sources]`), never a local path. Registration relies on its registry dicts, so bump the pin deliberately and run `make test`.
- **CI never calls OpenRouter.** Mock the HTTP call in any LLM test. `OPENROUTER_API_KEY` goes in `.env` (copy `.env.example`), gitignored, never logged.
- **Same seed, same match.** The engine draws the whole round plan from `random.Random(seed)` in `initial_state`; do not add randomness to `apply_action`. Bots must be deterministic given the observation unless given an rng.
- New architectural decision that is costly to reverse: add an ADR in `docs/adr/` (Context / Decision / Alternatives / Consequences).

## Workflow

Branch per slice off fresh `main`; PR-only. Install the pre-push hook once: `git config core.hooksPath .githooks`. Tests are layered like the framework: `tests/unit` (no I/O), `tests/integration` (in-process `Match`), `tests/e2e` (the installed `wavelength` script).
