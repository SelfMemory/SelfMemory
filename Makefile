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
	cd selfmemory-mcp && uv run uvicorn main:mcp --host 0.0.0.0 --port 8080 --reload

all:
	uv run uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload
	cd selfmemory-mcp && uv run uvicorn main:mcp --host 0.0.0.0 --port 8080 --reload
	npm run start

clean:
	rm -rf .venv
	rm -rf .ruff_cache
	rm -rf selfmemory.egg-info
	rm -rf selfmemory-mcp/selfmemory_mcp.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist/
