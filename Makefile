#!make
# Self-contained socle for a host-run Python library (repos.yml runtime: exempt:lib).
# Tools are invoked through `python -m` and degrade gracefully when absent locally;
# CI runs the authoritative gate via pre-commit / GitHub Actions.
PROJECT_NAME ?= herdr-rtk-savings
SRC          ?= .
PY           ?= python
.DEFAULT_GOAL := help
.PHONY: help install install-dev lint format format-check typecheck test test-cov pre-commit clean ci quality-gate-baseline quality-gate-verify

help: ## Display this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n",$$1,$$2}'

install: ## Install the package
	@$(PY) -m pip install -e .

install-dev: ## Install the package with dev extras
	@$(PY) -m pip install -e ".[dev]" || $(PY) -m pip install -e .

lint: ## Run ruff lint
	@$(PY) -m ruff check $(SRC) tests 2>/dev/null || ruff check $(SRC) tests

format: ## Auto-format with ruff
	@$(PY) -m ruff format $(SRC) tests

format-check: ## Check formatting (no write)
	@$(PY) -m ruff format --check $(SRC) tests

typecheck: ## Run mypy
	@$(PY) -m mypy $(SRC)

test: ## Run the test suite
	@$(PY) -m pytest

test-cov: ## Run tests with coverage
	@$(PY) -m pytest --cov=$(SRC) --cov-report=term-missing

pre-commit: ## Run pre-commit hooks on all files
	@command -v pre-commit >/dev/null 2>&1 && pre-commit run --all-files \
		|| echo "pre-commit not installed — skipping (runs in CI)"

clean: ## Remove regenerable caches and build artefacts
	@find . -type d \( -name __pycache__ -o -name .ruff_cache -o -name .mypy_cache \
		-o -name .pytest_cache -o -name '*.egg-info' -o -name build -o -name dist \) \
		-prune -exec rm -rf {} + 2>/dev/null || true

quality-gate-baseline: ## Record the quality-gate baseline (no-op until wired)
	@echo "quality-gate: no baseline configured for this repo yet"

quality-gate-verify: ## Verify against the quality-gate baseline (skips until wired)
	@echo "quality-gate: SKIP (no baseline recorded)"

ci: lint typecheck test ## Aggregate CI gate: lint + typecheck + test
