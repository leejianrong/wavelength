# Contributing

## Setup

```
make install     # locked dependencies + the pre-push hook
make all         # lint, typecheck, and all three test layers: what CI runs
```

Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) are required. The web UI also needs Node 24 (`make web-build`, `make web-check`); its browser tests need Chromium once: `cd web && npx playwright install chromium`. `make` with no target lists every command.

## Workflow

- One branch per slice off fresh `main`, one PR per branch. `main` takes changes by PR only, after CI is green.
- The slice plan is `docs/SLICES.md`. Cite the ADR a change rests on in the PR description. A new decision that is costly to reverse gets an ADR in `docs/adr/` (Context, Decision, Alternatives considered, Consequences).
- The pre-push hook runs ruff, mypy and the unit tests. Skip it with `git push --no-verify` only when you have checked the failure is unrelated.

## Tests

Layered by cost, mirroring CI's jobs:

| Layer | Directory | May use |
|-------|-----------|---------|
| unit | `tests/unit` | no I/O |
| integration | `tests/integration` | in-process `Match` and scripted seats |
| e2e | `tests/e2e` | the installed `wavelength` script as a subprocess, and a local mock of OpenRouter |

CI and the test suite never call the real OpenRouter API. A change that adds a way for the target to reach the guesser (a new output, prompt or error message) needs a case in the leak tests.

A bug fix starts with a failing test. If a guard matters (a leak check, a rule), break the thing it protects once and confirm the test goes red for the right reason.

## Dependencies and secrets

`uv.lock` is committed and CI installs with `--locked`; commit the lock file with any dependency change. The framework is pinned to a commit in `pyproject.toml`: bump it deliberately and run `make test`. `make audit` scans the lock file for known vulnerabilities, and Dependabot proposes updates weekly.

`OPENROUTER_API_KEY` lives in `.env` (gitignored), never in code, logs or commits. If a key leaks, rotate it.
