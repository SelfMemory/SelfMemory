# CLAUDE.md — selfmemory-core

Python FastAPI backend. Package manager is `uv` (not pip).

## Commands

```bash
make install-dev          # Install with dev dependencies
make run                  # Dev server with reload (:8081)
make test                 # All tests (pytest)
make test-unit            # Unit tests only
make test-sdk             # SDK memory tests
make test-client          # Client API tests
make coverage             # Tests + coverage report
make quality              # Lint + format (ruff)
make lint-fix             # Auto-fix lint issues
make run-mcp              # MCP server dev mode
```

## Code Style

- Ruff for linting and formatting (config in `pyproject.toml`)
- Line length: 88
- Double quotes, space indent
- Pre-commit hooks enforce ruff check + format + commitizen

## Structure

- `selfmemory/` — core library: `SelfMemory` class, factory pattern for vector stores and embeddings
- `server/` — FastAPI app with auth middleware (Ory Kratos/Hydra validation)
- `tests/` — pytest tests
- `selfmemory-mcp/` — MCP server (uv workspace member)
- `selfmemory-ts/` — TypeScript SDK

## CI

GitHub Actions (`ci.yml`): ruff lint → pytest with coverage → build wheel (on master push only).

## Auth Integration

- Validates sessions against Ory Kratos (identity) and Hydra (OAuth2)
- Multi-tenant: Organizations → Projects → Users with RBAC
- `make restart-auth` / `make clean-auth` — manage Ory Docker stack from here
