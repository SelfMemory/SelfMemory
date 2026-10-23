# Makefile for SelfMemory - UV-based workflow

.PHONY: lint-imports openapi ts-client help install install-dev sync test test-unit test-wiki coverage run run-dev run-api status check stop stop-clean worker isolation run-prod run-mcp run-mcp-prod clean clean-all lint lint-fix format quality build ship

DEVSTACK := uv run python -m scripts.devstack

# Default target - show help
help:
	@echo "SelfMemory Development Commands (UV-based)"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install core package only"
	@echo "  make install-dev   - Install with all dev dependencies (recommended for contributors)"
	@echo "  make sync          - Sync dependencies from uv.lock"
	@echo ""
	@echo "Run the application:"
	@echo "  make run           - Start the stack: Mongo, then the API"
	@echo "  make run-dev       - Same as run, without uvicorn auto-reload"
	@echo "  make run-api       - Start ONLY the API (assumes services already up)"
	@echo "  make status        - Show what is currently running"
	@echo "  make check         - Preflight checks only, changes nothing"
	@echo "  make worker        - Run the wiki job worker as its own process"
	@echo "  make isolation     - Print the agent isolation report as JSON"
	@echo "  make stop          - Stop Mongo (keeps data)"
	@echo "  make stop-clean    - Stop Mongo and DELETE its volume (wiki data kept)"
	@echo ""
	@echo "Development:"
	@echo "  make run-prod      - Run FastAPI server in production mode"
	@echo "  make run-mcp       - Run MCP server in dev mode (with reload)"
	@echo "  make run-mcp-prod  - Run MCP server in production mode"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make test-wiki     - Run wiki engine, routes and run tests"
	@echo "  make coverage      - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Check code with ruff and the layer contracts"
	@echo "  make format        - Format code with ruff"
	@echo "  make quality       - Run lint and format together"
	@echo ""
	@echo "Build & Clean:"
	@echo "  make build         - Build package distribution"
	@echo "  make clean         - Clean build artifacts and cache"
	@echo "  make clean-all     - Clean everything including venv"

# Install core package only (minimal dependencies)
install:
	uv sync --no-dev

# Install with development dependencies (for contributors)
install-dev:
	uv sync

# Sync all dependencies from lock file
sync:
	uv sync --locked

# Run all tests
test:
	uv run pytest

# Run unit tests only (tests/unit)
test-unit:
	uv run pytest tests/unit -v

# Run the wiki backend tests (engine, routes, access, runs)
test-wiki:
	uv run pytest tests/unit/wiki tests/unit/runs tests/unit/tenancy tests/integration -v

# Run tests with coverage report
coverage:
	uv run pytest --cov=selfmemory --cov-report=html --cov-report=term-missing

# Start the application: Mongo (tenancy + wiki run queue), then the API.
#
# Each dependency is started and proven ready before the next begins. The wiki
# data root is a directory on disk and the opencode agent runs per job, so
# neither needs starting; preflight warns when the agent binary or its
# credentials are missing.
#
# Blocks until Ctrl-C. Containers stay up afterwards; use `make stop`.
run:
	$(DEVSTACK) up

# Same as run, without uvicorn auto-reload. Faster, and the only mode that
# behaves predictably under a debugger.
run-dev:
	$(DEVSTACK) up --no-reload

# Start only the API. Use when the services are already up -- e.g. after
# `make stop` followed by `docker compose up -d` by hand -- or when you want
# uvicorn's output in the foreground where you can see it directly.
run-api:
	uv run uvicorn selfmemory.apps.api:app --host 0.0.0.0 --port 8081 --reload --reload-dir packages/selfmemory/src

# Report which services are up. Changes nothing, always exits 0.
status:
	$(DEVSTACK) status

# Verify prerequisites without starting anything.
check:
	$(DEVSTACK) check

# Stop Mongo. Local data is kept.
stop:
	$(DEVSTACK) down

# Stop Mongo and delete its volume: users, organizations, projects, API keys
# and the run queue. The wiki data root (uploads and compiled wikis) is on
# disk and is never deleted here; its location is printed so you can remove
# it by hand if that is really what you want.
stop-clean:
	$(DEVSTACK) down --volumes
	@echo "Wiki data root left untouched:"
	@uv run python -c "from scripts.devstack.settings import load_settings; print('  ' + str(load_settings().wiki.data_root))"

# Run the wiki job worker on its own (the API also runs one unless
# SELFMEMORY_WORKER=off).
worker:
	uv run python -m selfmemory.apps.worker

# Print the agent isolation report (may run a docker probe for a few seconds).
isolation:
	@uv run python -c "import json; from dotenv import load_dotenv; load_dotenv(); from selfmemory.wiki_settings import load_settings; from selfmemory.platform.sandbox.isolation import isolation_report; print(json.dumps(isolation_report(load_settings()), indent=2, default=str))"

# Run FastAPI server in production mode
run-prod:
	uv run uvicorn selfmemory.apps.api:app --host 0.0.0.0 --port 8081

# Run MCP server in development mode with auto-reload
run-mcp:
	MCP_DEV_MODE=true uv run python -m selfmemory.apps.mcp

# Run MCP server in production mode
run-mcp-prod:
	uv run python -m selfmemory.apps.mcp

# Clean build artifacts and caches
clean:
	rm -rf .ruff_cache
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/
	rm -rf build/

# Clean everything including virtual environment
clean-all: clean
	rm -rf .venv
	rm -rf uv.lock

# Build package distribution
build:
	uv build --package selfmemory

# Dump the /api/v1 OpenAPI contract to docs/api/openapi.json
openapi:
	uv run python scripts/export_openapi.py

# Regenerate the typed TS client in selfmemory-ts from the committed contract
ts-client: openapi
	cd selfmemory-ts && npm ci && npm run generate

# Lint code with ruff
lint:
	uv run ruff check .
	uv run lint-imports

# Check the layer rules (import-linter contracts in pyproject.toml)
lint-imports:
	uv run lint-imports

# Fix linting issues automatically
lint-fix:
	uv run ruff check --fix .

# Format code with ruff
format:
	uv run ruff format .

# Run all code quality checks
quality: lint-fix format
	@echo "✅ Code quality checks complete"

# Note: the previous clean-auth / restart-auth targets were removed. They
# referenced an `ory-infrastructure/` directory that has never been tracked in
# this repository, so `make clean-auth` failed with "No such file or directory".
# Nothing referenced them in CI or docs.
#
# Ory Kratos and Hydra are not required to run the stack. They back the
# browser login flow; API-key clients bypass them entirely. To use the seeded
# key without standing up auth:
#
#   uv run python scripts/dev_seed_api_key.py

ship:
	uv lock
	uv sync --all-extras
