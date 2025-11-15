# Makefile

.PHONY: setup run clean

setup:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv venv .venv --python=3.12
	chmod +x run.sh
	uv pip install -r requirements.txt

run:
	uv run uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload

runmcp:
	cd selfmemory-mcp && uv run python3 main.py

clean:
	rm -rf .ruff_cache
	rm -rf selfmemory.egg-info
	rm -rf selfmemory-mcp/selfmemory_mcp.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist/

allclean:
	rm -rf .venv
	rm -rf .ruff_cache
	rm -rf selfmemory.egg-info
	rm -rf selfmemory-mcp/selfmemory_mcp.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist/

build:
	uv build

cleanauth:
	cd ory-infrastructure && docker-compose down
	rm -rf ory-infrastructure/volumes/postgres
	docker compose up

restartauth:
	cd ory-infrastructure && docker-compose down
	docker compose up

# Code quality targets
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

format:
	uv run ruff format .

quality: lint-fix format
	@echo "✅ Code quality checks complete"
