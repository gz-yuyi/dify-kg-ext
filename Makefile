.PHONY: help setup check-setup install lint format check fix test clean run dev
.DEFAULT_GOAL := help

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## Setup development environment (run this after cloning)
	@echo "🚀 Setting up development environment..."
	uv sync --group dev --group test
	uv run pre-commit install
	@echo "✅ Development environment setup complete!"
	@echo "💡 You can now run 'make pre-commit-run' to test the hooks"

check-setup:  ## Check if development environment is properly configured
	@./scripts/check-dev-setup.sh

install:  ## Install dependencies
	uv sync

install-dev:  ## Install with dev dependencies
	uv sync --group dev --group test

lint:  ## Run linting with ruff
	uv run ruff check .

format:  ## Format code with ruff
	uv run ruff format .

check:  ## Check code without making changes (lint + format check)
	uv run ruff check . --diff
	uv run ruff format . --check

fix:  ## Auto-fix linting issues and format code
	uv run ruff check . --fix
	uv run ruff format .

test:  ## Run tests
	uv run pytest

test-v:  ## Run tests with verbose output
	uv run pytest -v

test-cov:  ## Run tests with coverage report in terminal
	uv run pytest --cov=match_lock --cov-report=term-missing

test-cov-html:  ## Run tests with HTML coverage report
	uv run pytest --cov=match_lock --cov-report=html --cov-report=term-missing
	@echo "📊 Coverage report generated at htmlcov/index.html"

test-cov-xml:  ## Run tests with XML coverage report (for CI)
	uv run pytest --cov=match_lock --cov-report=xml --cov-report=term-missing

test-cov-all:  ## Run tests with all coverage report formats
	uv run pytest --cov=match_lock --cov-report=term-missing --cov-report=html --cov-report=xml
	@echo "📊 Coverage reports generated:"
	@echo "  - Terminal: above"
	@echo "  - HTML: htmlcov/index.html"
	@echo "  - XML: coverage.xml"

test-cov-fail:  ## Run tests with coverage and fail if coverage below threshold
	uv run pytest --cov=match_lock --cov-report=term-missing --cov-fail-under=80

clean:  ## Clean cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ coverage.xml .coverage 2>/dev/null || true

run:  ## Run the application
	uv run python main.py serve

dev:  ## Run in development mode
	uv run python main.py serve --reload

ci:  ## Run all CI checks (lint, format check, test)
	uv run ruff check .
	uv run ruff format . --check
	uv run pytest

pre-commit:  ## Run pre-commit checks (fix + test)
	uv run ruff check . --fix
	uv run ruff format .
	uv run pytest

pre-commit-install:  ## Install pre-commit hooks
	uv run pre-commit install

pre-commit-run:  ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

pre-commit-update:  ## Update pre-commit hooks to latest versions
	uv run pre-commit autoupdate
