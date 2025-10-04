# Makefile

.PHONY: setup run clean

setup:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv venv .venv --python=3.12
	chmod +x run.sh
	uv pip install -r requirements.txt

activate:
	source .venv/bin/activate

run:
	lsof -ti:8081 | xargs kill -9
	uv run uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload

runmcp:
	lsof -ti:8080 | xargs kill -9
	cd selfmemory-mcp && uv run python3 main.py

runall:
	uv run uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload
	cd selfmemory-mcp && uv run python3 main.py
	npm run start

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
