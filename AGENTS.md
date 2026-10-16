# wavelength

Cooperative two-player Wavelength for a human and an LLM, or two LLMs, on [`agent-game-framework`](https://github.com/leejianrong/agent-game-framework). If this file, `docs/`, and the code disagree, trust the code and fix the doc in the same PR.

## What and why

Python 3.12, uv. `src/wavelength/engine.py` is the game; `cli.py` registers it into the framework's CLI. The plan and its reasoning are in `docs/PLAN.md`, the build order in `docs/SLICES.md`, decisions in `docs/adr/`. Read the ADR before changing what it covers.

Done: all slices V0-V5 (framework changes, engine, full matches, LLM seats + eval, chat, MCP seat). Live-model quality (2026-10-16, deepseek-v4.1-flash self-play, against 0.57 for random): 1.80 points/round over 60 rounds before named zones, 2.47 over 30 rounds after (a different deck too). Q19's 2.0 looks reachable but one model and a small sample do not settle it; see `docs/SLICES.md` V3 and V8.1.

## Commands

`make` lists them. The ones you will use: `make all` (everything CI runs, Node 24 needed for the web UI), `make play-bot` (no key), `make web` (play in the browser against a bot), `make play` (LLM, needs `.env`). Tests are `tests/unit` (no I/O), `tests/integration` (in-process `Match`), `tests/e2e` (the installed script, LLM mocked), plus the web UI's own `web/test` (dial maths) and `web/e2e` (Playwright, `make test-web`).

## Rules that are easy to break

- **The target must never reach the guesser.** Only `WavelengthEngine.observation_for` decides visibility. Anything new that prints or sends game data (an output, a prompt, an error message) needs a leak case in `tests/integration/test_match.py` or `tests/e2e/`. Use `observation_for(viewer)`, never `serialize`, for anything a player or LLM sees.
- **Do not add randomness to `apply_action`.** The whole round plan is drawn in `initial_state` from the seed. Bots must be deterministic given the observation.
- **The framework is pinned to a commit** in `pyproject.toml`, not a path. We rely on its registry dicts and on replacing `framework_cli.build_controller` and `framework_cli.Match` (`cli.py`), none of which is a public API: bump the pin deliberately and run `make all`.
- **LLM seats go through `GuardedSeat`** (`seats.py`). The framework retries an illegal move forever; the guard bounds it at 3 attempts and tells the model why. It also drops banter on clue turns, because the framework prints banter to the other player and the psychic knows the target. Do not bypass it for a new LLM path.
- **Chat context comes only from `chat_guard.chat_context`**, an allow-list. Never build it by copying an observation and removing fields. A seat that is the psychic must not reach the model in chat.
- **A browser gets only what one seat may see**, built in `WebSession._render` (`src/wavelength/web/`) from `observation_for`; the wire format and its five rules are in `docs/web-protocol.md`. In short: a spectator sees the guesser's view unless they peek, peek is refused when a human is seated, banter comes only from guess turns, and raw exception text never goes to a page (a framework error can hold a model's output). Anything new that goes to a browser needs a leak case in `tests/integration/test_web_session.py`, `tests/e2e/test_web.py` or `web/e2e/`. The page holds no game logic.
- **AI matches in the browser are capped**: every AI seat is `guard(metered(...))` with one shared `Meter` per match. A new path that calls a model must go through it.
- **CI never calls OpenRouter.** Mock it (`tests/e2e/_mock_openrouter.py`). `.env` is gitignored; never log the key.

## Workflow

Branch per slice off fresh `main`; PR only, after CI is green. A costly-to-reverse decision gets an ADR (Context / Decision / Alternatives / Consequences). Install the hooks once with `make install`. See `CONTRIBUTING.md`.
