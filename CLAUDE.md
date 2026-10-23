# CLAUDE.md — selfmemory-core

Python FastAPI backend. Package manager is `uv` (not pip).

## Commands

```bash
make install-dev          # Install with dev dependencies
make run                  # Dev server with reload (:8081)
make test                 # All tests (pytest)
make test-unit            # Unit tests only
make test-wiki            # Wiki engine, access, runs and /api/v1/wiki tests
make worker               # Standalone run worker (when SELFMEMORY_WORKER=off)
make isolation            # Which agent sandbox this host provides
make coverage             # Tests + coverage report
make quality              # Lint + format (ruff)
make lint-imports         # Layer contracts (import-linter)
make lint-fix             # Auto-fix lint issues
make run-mcp              # MCP server dev mode
```

## Code Style

- Ruff for linting and formatting (config in `pyproject.toml`)
- Line length: 88
- Double quotes, space indent
- Pre-commit hooks enforce ruff check + format + commitizen

## Structure

Target architecture: `docs/architecture/index.html`. uv workspace; the library is
`packages/selfmemory` (src layout, `uv_build`), Python 3.13.

- `packages/selfmemory/src/selfmemory/`
  - `config.py` (pydantic-settings), `wiki_settings.py` (data root, sandbox, agent)
  - `kernel/` — pure helpers: `safe_paths` (scope path safety), validators, crypto,
    `feature.py` (Feature registry, `selfmemory.features` entry-point group)
  - `features/<name>/` — vertical slices with `domain/`, `adapters/`, `service.py`,
    `interfaces/` (http, mcp). Each exposes `FEATURE`; `features.BUILTIN` lists them.
    - `wiki/` — scope layout, files, git per scope, graph/timeline, search, `/wiki` router,
      MCP tools
    - `runs/` — Mongo job queue/leases/chats (`store.py`), worker, opencode runner and its
      prompts (`schema/`)
    - `uploads/` — markitdown conversion
    - `tenancy/` — orgs/projects/invitations routers; `access.py` is the only authz gate
    - `api_keys/`
    - `a2a/` — A2A JSON-RPC at `/api/v1/a2a` + `/.well-known/agent-card.json`;
      contextId = chat of kind "a2a", task = query job
  - `platform/` — mongo, ory (Kratos/Hydra validation), sandbox (bwrap/docker + isolation
    probe), telemetry, mcp (OAuth + auth middleware), `dependencies.py`
  - `apps/` — `api.py` (mounts features at `/api/v1`, legacy `/api` alias hidden from
    OpenAPI), `worker.py`, `mcp.py`
- `deploy/` — docker compose, sandbox image
- `scripts/devstack/` — `make run` stack manager
- `tests/unit/<feature>/`, `tests/integration/`
- `selfmemory-ts/` — TypeScript SDK

Layer rules are import-linter contracts in `pyproject.toml` (`make lint-imports`):
apps → features → platform → kernel, and `features.wiki.domain` imports no I/O.

## CI

GitHub Actions (`ci.yml`): ruff lint + lint-imports → pytest with coverage → build wheel (on master push only).

## Wiki model

- Data root `SELFMEMORY_DATA_ROOT/orgs/<org>/{raw,wiki}/{org,projects/<p>[/<child>],users/<u>}`;
  every wiki scope dir is its own git repo. Sub-projects nest inside the parent dir, so walks,
  mounts and commits of a parent must mask/exclude them (`Scope.nested`).
- No LLM, embeddings or vector store in the server: all model work is `opencode run` per job.
- One sandbox per run (no long-lived per-user sandboxes). A chat's opencode session
  continues only while the run's mount set is unchanged (`worker.scope_digest`); HOME is
  per (org, owner, digest). Turns of one chat run one at a time (unique index);
  per-owner/per-org caps give fair share.
- Agent runs refuse to start when isolation is required (production) and the probe fails.

## Auth Integration

- Validates sessions against Ory Kratos (identity) and Hydra (OAuth2)
- Multi-tenant: Organizations → Projects → Users with RBAC
