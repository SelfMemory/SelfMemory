# Makefile for SelfMemory - UV-based workflow

.PHONY: help install install-dev sync test test-unit test-integration coverage run run-prod run-mcp clean lint format quality build

# Default target - show help
help:
	@echo "SelfMemory Development Commands (UV-based)"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install core package only"
	@echo "  make install-dev   - Install with all dev dependencies (recommended for contributors)"
	@echo "  make sync          - Sync dependencies from uv.lock"
	@echo ""
	@echo "Development:"
	@echo "  make run           - Run FastAPI server in dev mode (with reload)"
	@echo "  make run-prod      - Run FastAPI server in production mode"
	@echo "  make run-mcp       - Run MCP server"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make coverage      - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Check code with ruff"
	@echo "  make format        - Format code with ruff"
	@echo "  make quality       - Run lint and format together"
	@echo ""
	@echo "Build & Clean:"
	@echo "  make build         - Build package distribution"
	@echo "  make clean         - Clean build artifacts and cache"
	@echo "  make clean-all     - Clean everything including venv"

# Install core package only (minimal dependencies)
install:
	uv pip install -e .

# Install with development dependencies (for contributors)
install-dev:
	uv pip install -e ".[dev]"

# Sync all dependencies from lock file
sync:
	uv sync --all-extras

# Run all tests
test:
	uv run pytest

# Run unit tests only
test-unit:
	uv run pytest tests/ -m unit -v

# Run integration tests only
test-integration:
	uv run pytest tests/ -m integration -v

# Run tests with coverage report
coverage:
	uv run pytest --cov=selfmemory --cov-report=html --cov-report=term-missing

# Run FastAPI server in development mode with reload
run:
	uv run uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload

# Run FastAPI server in production mode
run-prod:
	uv run uvicorn server.main:app --host 0.0.0.0 --port 8081

# Run MCP server
run-mcp:
	cd selfmemory-mcp && uv run python main.py

# Clean build artifacts and caches
clean:
	rm -rf .ruff_cache
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf selfmemory.egg-info
	rm -rf selfmemory-mcp/selfmemory_mcp.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/
	rm -rf build/

# Clean everything including virtual environment
clean-all: clean
	rm -rf .venv
	rm -rf uv.lock

# Build package distribution
build:
	uv build

# Lint code with ruff
lint:
	uv run ruff check .

# Fix linting issues automatically
lint-fix:
	uv run ruff check --fix .

# Format code with ruff
format:
	uv run ruff format .

# Run all code quality checks
quality: lint-fix format
	@echo "✅ Code quality checks complete"

# Auth infrastructure management (if using Ory)
clean-auth:
	cd ory-infrastructure && docker-compose down
	rm -rf ory-infrastructure/volumes/postgres
	cd ory-infrastructure && docker-compose up

restart-auth:
	cd ory-infrastructure && docker-compose restart
