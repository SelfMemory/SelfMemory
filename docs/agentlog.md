# Agent Log

Append-only. Newest entries at the bottom. Read the last entry to resume.

---

## 2026-10-08 — Session resume audit

### Branch state
- Branch: `feat/knowledge-memory-2.0` (NOT pushed; no `origin/feat/knowledge-memory-2.0`).
- Local-only commits (5), in order:
  - `5894eaa` feat: add knowledge-page memory engine
  - `8b9eba1` feat: add agent sessions over disposable workspaces
  - `0a06e49` docs: resolve encryption to global, correct the search tradeoff
  - `80ef989` feat: expose knowledge memory over HTTP with a Bruno collection
- Previous release tag baseline: `b348b5e 0.9.6`. CHANGELOG has no `Unreleased` section yet.

### Uncommitted work in the working tree
1. **`SelfMemory.get(memory_id, *, user_id)`** — `selfmemory/memory/main.py`
   - New SDK read-by-id method. Fetches the vector point, decrypts payload when
     global encryption is on, then enforces strict ownership: `payload["user_id"]`
     must equal the requested `user_id`, else returns `{"success": False, "error":
     "Memory not found"}` (generic error on purpose, so it does not leak that
     another tenant's memory exists).
   - Why it matters: `GET /api/memories/{memory_id}` was raising `AttributeError`
     (HTTP 500) because this method did not exist.
2. **Regression tests** — `tests/test_sdk_memory.py` → `TestSelfMemoryGet`
   - 3 cases: owned memory returns content; missing memory returns failure instead
     of raising; cross-user access denied.
   - `uv run pytest tests/test_sdk_memory.py -q` → **14 passed**.
3. **Bruno collection migrated from `.bru` to `.yml`** (uncommitted)
   - Deleted: `bruno/bruno.json`, `bruno/collection.bru`, `bruno/environments/{local,
     staging}.bru`, and 7 `bruno/knowledge/*.bru` request files.
   - Added: `bruno/opencollection.yml`, `bruno/environments/{local,staging}.yml`, and
     7 `bruno/knowledge/*.yml` request files.
   - Net: same 9 endpoints, new OpenCollection YAML format.
4. **`scripts/dev_seed_api_key.py`** (untracked) — dev-only seeder that writes user /
   org / project / API-key docs straight into MongoDB and prints the key, so the
   knowledge endpoints can be exercised without standing up Ory Kratos. Refuses to
   run against a non-local Mongo URI.
5. `uv.lock` has a one-line diff (drift from a `uv` run).

### Not yet done
- Nothing is committed for any of the above; nothing is pushed.
- No `docs/agentlog.md` existed before this entry.
- CHANGELOG not updated for the knowledge-memory-2.0 work.

### Next suggested steps
1. Commit the `SelfMemory.get()` + tests as a `fix:` commit.
2. Commit the Bruno `.bru` → `.yml` migration as a separate `chore:`/`refactor:` commit.
3. Commit `scripts/dev_seed_api_key.py` as a `chore(dev):` commit.
4. Open a PR, then add a CHANGELOG entry.
