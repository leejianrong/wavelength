.DEFAULT_GOAL := help

.PHONY: help install lint typecheck test-unit test-integration test-e2e test all play

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install the package + dev dependencies
	uv sync --all-extras --dev

play: install ## Play one round: you give the clue, a random-guessing bot dials
	uv run wavelength play --config rounds=1 --seat A=human --seat B=bot:wl-random

lint: ## Run ruff
	uv run ruff check .

typecheck: ## Run mypy
	uv run mypy src

test-unit: ## Run the no-infra unit test layer
	uv run pytest tests/unit -q

test-integration: ## Run the integration test layer (in-process only)
	uv run pytest tests/integration -q

test-e2e: ## Run the e2e layer (drives the installed `wavelength` script)
	uv run pytest tests/e2e -q

test: test-unit test-integration test-e2e ## All three test layers

all: lint typecheck test ## Everything CI runs
