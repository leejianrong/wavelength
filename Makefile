.DEFAULT_GOAL := help

MODEL ?= deepseek/deepseek-v4-flash
MODEL2 ?= openai/gpt-4o-mini
ROUNDS ?= 6
EVAL_ROUNDS ?= 30
EVAL_SEEDS ?= 1
MAX_CALLS ?= 400

.PHONY: help install check-key play play-bot watch eval-llm web web-build web-check test-web lint typecheck test-unit test-integration test-e2e test audit all

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (from uv.lock) and the pre-push hook
	uv sync --locked --all-extras --dev
	@git config core.hooksPath .githooks 2>/dev/null || true

check-key:
	@test -f .env || { echo "Missing .env: copy .env.example to .env and set OPENROUTER_API_KEY."; exit 1; }
	@grep -Eq '^OPENROUTER_API_KEY=.+' .env || { echo "OPENROUTER_API_KEY is empty in .env."; exit 1; }

play: install check-key ## Play against an LLM agent (needs OPENROUTER_API_KEY in .env; MODEL=, ROUNDS= to change)
	uv run --env-file .env wavelength play wavelength --config rounds=$(ROUNDS) \
		--seat you=human --seat agent=llm:openrouter/$(MODEL)

play-bot: install ## Play against a scripted bot, no API key needed
	uv run wavelength play wavelength --config rounds=$(ROUNDS) \
		--seat you=human --seat bot=bot:wl-random

watch: install check-key ## Watch two LLM agents play each other (MODEL=, MODEL2=)
	uv run --env-file .env wavelength play wavelength --config rounds=$(ROUNDS) \
		--seat one=llm:openrouter/$(MODEL) --seat two=llm:openrouter/$(MODEL2)

eval-llm: install check-key ## Score two LLM seats over EVAL_ROUNDS x EVAL_SEEDS rounds vs a random guesser, capped at MAX_CALLS calls (real API calls, costs money)
	uv run --env-file .env python -m wavelength.eval --model $(MODEL) --model2 $(MODEL2) \
		--rounds $(EVAL_ROUNDS) \
		--seeds $(EVAL_SEEDS) --max-calls $(MAX_CALLS) --table

web/node_modules: web/package-lock.json
	cd web && npm ci
	@touch web/node_modules

web-build: web/node_modules ## Compile the web UI (web/src -> src/wavelength/web/static/app.js; needs Node 24)
	cd web && npm run build

web-check: web/node_modules ## Typecheck and unit-test the web UI
	cd web && npm run typecheck && npm test

test-web: web-build ## Browser tests (Playwright; first time: cd web && npx playwright install chromium)
	cd web && npm run e2e

web: install web-build ## Play in the browser (start screen; AI seats use .env if present; MAX_CALLS= caps model calls)
	uv run $(if $(wildcard .env),--env-file .env) wavelength web --max-calls $(MAX_CALLS)

lint: ## Run ruff
	uv run ruff check .

typecheck: ## Run mypy
	uv run mypy src

test-unit: ## Run the no-infra unit test layer
	uv run pytest tests/unit -q

test-integration: ## Run the integration test layer (in-process only)
	uv run pytest tests/integration -q

test-e2e: ## Run the e2e layer (drives the installed `wavelength` script; LLM calls are mocked)
	uv run pytest tests/e2e -q

test: test-unit test-integration test-e2e ## All three test layers

audit: ## Scan locked dependencies for known vulnerabilities
	uv export --locked --no-hashes --no-emit-project --no-emit-package agent-game-framework \
		| uvx pip-audit --no-deps --disable-pip -r /dev/stdin

all: lint typecheck web-check test test-web ## Everything CI runs
