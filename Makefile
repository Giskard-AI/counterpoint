.PHONY: help install install-tools sync test lint check-compat security format clean all pre-commit-install pre-commit-run licenses licenses-json licenses-md licenses-check

# Default target
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation targets
install: ## Install project dependencies
	uv sync

install-tools: ## Install development tools
	uv tool install ruff
	uv tool install vermin
	uv tool install pre-commit --with pre-commit-uv
	uv tool install pip-licenses

sync: install ## Alias for install

setup: install install-tools ## Complete development setup (install deps + tools)

# Development targets
test: ## Run tests
	uv run pytest

lint: ## Run linting checks
	uv tool run ruff check .

format: ## Format code with ruff
	uv tool run ruff format .

check-format: ## Check if code is formatted correctly
	uv tool run ruff format --check .

check-compat: ## Check Python 3.10 compatibility
	uv tool run vermin --target=3.10- --no-tips --violations .

security: ## Check for security vulnerabilities
	uv run pip-audit .

# Pre-commit targets
pre-commit-install: ## Install pre-commit hooks
	pre-commit install

pre-commit-run: ## Run pre-commit on all files
	pre-commit run --all-files

# Combined targets
check: lint check-format check-compat security ## Run all checks (lint, format, compatibility, security)

all: format check test ## Format, check, and test

# CI simulation
ci: check test ## Run the same checks as CI

# License compliance
licenses: licenses-json licenses-md ## Generate license inventory (JSON) and THIRD_PARTY_NOTICES.md

licenses-json: ## Generate licenses.json inventory
	uvx pip-licenses --format=json --with-license-file --with-authors --with-urls > licenses.json

licenses-md: ## Generate THIRD_PARTY_NOTICES.md with embedded license texts
	uvx pip-licenses --format=markdown --with-license-file --with-authors --with-urls > THIRD_PARTY_NOTICES.md

licenses-check: ## Fail if disallowed licenses are present
	@ALLOW='MIT|BSD|ISC|Apache-2.0|Apache 2.0|Apache2|CC0-1.0|Python-2.0|MPL-2.0|EPL-2.0|Unlicense'; \
	RES=$$(uvx pip-licenses --format=csv | tail -n +2 | awk -F, '{print $$3}' | grep -Ev "$$ALLOW" || true); \
	if [ -n "$$RES" ]; then echo "Found disallowed licenses:" >&2; echo "$$RES" >&2; exit 1; fi

clean: ## Clean up build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/