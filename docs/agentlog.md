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

---

## 2026-10-08 — Pushed and opened PR #160

### Commits added this session
```
d665788  fix(core): add SelfMemory.get() with strict tenant isolation
79f68fd  refactor(bruno): migrate collection to OpenCollection YAML
33f2237  chore(dev): add local API key seed script
cf0d380  chore(deps): resync uv.lock to 0.9.6
aed3f70  docs: add agent log for cross-session handoff
2d71933  fix(security): sanitize user input before it reaches the log
```

PR: https://github.com/SelfMemory/SelfMemory/pull/160 (base `master`, 10 commits).
Note: the repo moved — remote is now `SelfMemory/SelfMemory`, not
`selfmemory/selfmemory`. Git redirects, but the local remote URL is stale.

### CI result
Run Tests, Code Quality, and all three Analyze jobs pass. **CodeQL is red.**

### CodeQL: two real bugs found and fixed (`2d71933`)
CodeQL caught two genuine log-injection alerts in the `SelfMemory.get()` written
earlier that session — both interpolated request-controlled `user_id` /
`memory_id` into a log record, so a newline in either value lets a caller forge
a log line. Fixed by adding `sanitize_for_log()` in `selfmemory/utils/logging.py`.

Placement matters: the helper lives in the SDK, not `server/`, because both
layers need it and `server` already depends on `selfmemory`. Putting it in
`server/` would make the published package import the web app.

Also removed a dead `_sanitize_log()` from `server/routes/organizations.py` —
written for alerts fixed in `5662083`, but those were resolved by dropping
values from the messages, so nothing called it afterwards.

Lesson worth keeping: **always let CodeQL run before calling a PR done.** The
`get()` fix shipped with an injection hole in its own error path, and it was
only visible because CI was checked rather than assumed.

### CodeQL: six alerts still open, none from the follow-up commits
All from the earlier engine/HTTP commits on this branch:
- `session.py:109` command-line-injection — **false positive**; list-form
  `subprocess.run`, no `shell=True`, prompt is one argv entry
- `dev_seed_api_key.py:117` clear-text-logging — **true but deliberate**; the
  script exists to print the key, dev-only, refuses non-local Mongo
- `knowledge.py:141`, `dependencies.py:171`, `dependencies.py:198`
  log-injection — **not examined**
- `store.py:147` path-injection — **not examined**

Proposal posted on the PR: land #160, clear the four unexamined ones in a
follow-up.

### Verification at time of push
`ruff check` clean, `ruff format --check` clean (121 files), `pytest` 178 passed.

### Next actions
1. Review PR #160 and merge.
2. Follow-up PR for the four unexamined CodeQL alerts.
3. Decide on `dev_seed_api_key.py` — leave the alert, or `# nosec` + comment,
   or gate the print behind `--print-key`.
4. Update the local git remote to `SelfMemory/SelfMemory`.
5. CHANGELOG has no `Unreleased` section; confirm whether this repo wants
   hand-written entries or relies on python-semantic-release.

---

## 2026-10-20 — Cleared the four unexamined CodeQL alerts

### Commit
`0ab527f fix(security): close remaining log- and path-injection alerts` — local
only, **not pushed**. CodeQL has not re-run, so the alerts are fixed in code but
not yet confirmed closed.

### What each alert actually was
Pulled the taint paths from the SARIF rather than reading line numbers, which had
drifted under uncommitted edits.
- **#234, #202, #203 log-injection** — real. Request-supplied `project_id` reached
  log lines. Fixed with `sanitize_for_log`, plus three sibling `User not found`
  lines with the same shape.
- **#231 path-injection** — source is `os.getenv("SELFMEMORY_KNOWLEDGE_DB")`, not a
  request. Operator config, low real risk, but the store `mkdir(parents=True)`s
  whatever it is handed. Added `selfmemory/utils/paths.py::resolve_within()`,
  confining the DB to the server's working directory. Bad values fail at startup.

### Decision worth knowing
Did **not** reuse `SELFMEMORY_DATA_DIR` as the base. It is documented (default
`~/.selfmemory`, legacy file store) but nothing reads it; adopting it would
silently move the DB for anyone who exported it and break the devstack's
`REPO_ROOT / knowledge.db` assumption.

### Still open on PR #160
- **#233** `session.py` command-line-injection — false positive. List-form
  `subprocess.run`, no shell; the prompt is one argv entry and always begins with
  fixed text, so it cannot be parsed as a flag either.
- **#232** `dev_seed_api_key.py` clear-text-logging — deliberate; the script exists
  to print a key, and refuses non-local Mongo.
CodeQL stays red until these two are dismissed with a reason — a GitHub action,
left for the user.

### Working tree left untouched
Uncommitted from an earlier session, deliberately not swept into this commit:
the LLM provider fix in `server/routes/knowledge.py` and `selfmemory/llms/*`,
`server/main.py`, `Makefile`, and the untracked devstack
(`docker-compose.yml`, `scripts/devstack/`, `tests/test_devstack.py`,
`tests/test_llm_params.py`). The `knowledge.py` fix was committed by staging a
patched copy of HEAD, so the provider-fix hunks stay unstaged.

### Verification
`pytest` 278 passed. `ruff check` clean on all touched files. Server import
checked under four `SELFMEMORY_KNOWLEDGE_DB` values: default and `stores/kb.db`
boot; `../escape.db` and `/etc/kb.db` refused at startup.

### Next actions
1. Push `0ab527f` and confirm CodeQL closes #202, #203, #231, #234.
2. Dismiss #233 (false positive) and #232 (won't fix) with the reasons above.
3. Commit the provider fix and devstack.
4. Update the local git remote to `SelfMemory/SelfMemory`.

---

## 2026-10-21 — Backend rebuilt on the Org Brain model (branch `feat/orgbrain-backend`)

Branched from `feat/knowledge-memory-2.0` with its uncommitted work still in the
tree. A copy of that uncommitted diff and the untracked devstack files was saved
to the session scratchpad before anything changed.

### What the backend is now
The design of `projects/tw/orgbrain` (Next.js) reimplemented in this Python/FastAPI
repo. Ory auth, API keys, and org/project RBAC are unchanged.
- **Scopes** map onto the existing tenancy: the org room, a project, a sub-project
  (new `projects.parentProjectId`, one level deep, membership of the parent grants
  nothing), and personal notes. On disk they live at
  `SELFMEMORY_DATA_ROOT/orgs/<org>/{raw,wiki}/...`, and each wiki scope is its own
  git repository.
- **All model work is opencode** (`opencode run --format json --agent
  selfmemory-ingest|selfmemory-query`, run per job). The server has no LLM,
  embeddings, or vector store.
- **Isolation**: bwrap or docker, checked by a probe before any run. Runs fail
  closed in production; unconfined runs need `SELFMEMORY_UNISOLATED_ACK=1`.
- **Durable job queue** in Mongo (`wiki_jobs`, `wiki_job_events`, `wiki_leases`,
  `wiki_chats`, `wiki_chat_messages`). Events stream over SSE and resume from
  `Last-Event-ID`. The worker runs in-process, or alone via
  `python -m server.wiki.worker`.
- **Promotion review**: listing proposals and approving them into the org room.
  Orgbrain planned this but never built it.

### Improvements over orgbrain, found while porting
- A parent project's sandbox mount and its graph walk exposed the sub-projects
  nested inside it. Nested sub-projects are now masked in the mount (tmpfs) and
  excluded from walks and from the parent's git index (`.git/info/exclude`).
  Docker rejects a mask and a bind at the same path, so a readable child gets
  only its bind.
- opencode v2 dropped `--dir` and `--command`. The command prompts are now
  rendered by the server, and `--standalone` gives each run a private server
  instead of the shared background service, which sits outside the sandbox.
- An unconfined spawn path that actually works in development. Orgbrain's fell
  through to docker.
- Lint accepts an empty message. Orgbrain returned 400 for it.
- Ingests into one scope are serialised by a lease. A busy scope requeues the job
  with `notBefore`, without spending an attempt.

### Verified
- 56 wiki tests pass in a clean `--extra test` environment (mongomock, a fake
  agent for the worker, FastAPI TestClient for the routes).
- Real docker checks: confinement holds; a masked child is hidden; a readable
  child is read-only.
- Live end-to-end run against local Mongo (database `selfmemory_e2e`) with real
  opencode (`opencode/big-pickle`). Upload, ingest, commit, query with citations,
  graph, search, timeline, a queued promotion, and the MCP client all worked.

### Not done / follow-ups
- Legacy modules are still in the tree pending deletion approval. See the final
  message of the session.
- Not ported: the Google Drive connector, and per-user Google sign-in (Ory stays).
- `selfmemory-ts` and the dashboard (separate repo) still call `/api/memories`
  and `/api/knowledge` and need moving to `/api/wiki`.
- `docs/` (Docusaurus) still documents the old SDK.
- The sandbox image (`scripts/sandbox-image`) has not been built on a host yet,
  so the docker agent probe was only seen to fail with "opencode not found", as
  expected.

## 2026-10-21 — Blueprint phases 0 and 1 (restructure)

Followed `docs/architecture/index.html`, phases 0–1.

### Done
- uv workspace: library at `packages/selfmemory` (src layout, `uv_build`, Python
  3.13, `server` extra); root `pyproject.toml` holds dev group + tool config.
  `selfmemory-mcp` is no longer a workspace member, folded into `selfmemory.apps.mcp`
  + `platform/mcp` + `features/wiki/interfaces/mcp`.
- Layout `kernel/ features/{wiki,runs,uploads,tenancy,api_keys} platform/ apps/`.
  Module moves are in the README layout section; notable: `server.wiki.access` →
  `features.tenancy.access`, `selfmemory.wiki.paths` → `kernel.safe_paths`,
  `selfmemory.wiki.settings` → `selfmemory.wiki_settings`, `server.wiki.worker` →
  `features.runs.worker`, prompts → `features/runs/schema/`.
- `config.py` is pydantic-settings (same attribute and env names).
- Feature registry (`kernel/feature.py`, `features.BUILTIN`, entry-point group
  `selfmemory.features`); `apps/api.py` only mounts. Inline org/project create
  endpoints moved into the tenancy routers.
- API versioned at `/api/v1`; `/api/*` still mounted but hidden from OpenAPI for
  the old dashboard. Tests, MCP wiki client, Bruno and devstack use `/api/v1`.
- import-linter contracts (layers + pure wiki domain) in `make lint` and CI.
- `docker-compose.yml` and the sandbox image moved to `deploy/`.
- Fixed a stale `create_project_client` export that stopped the MCP server from importing.

### Not done / follow-ups
- Deleting the legacy stack was blocked by the permission classifier. It has all been
  moved to `legacy/` (selfmemory memory/vector/LLM code, old `server/` leftovers
  incl. chat + knowledge routes, `selfmemory-mcp/pyproject.toml`, legacy tests,
  `bruno/knowledge`); delete that directory to finish phase 1.
- Wiki `domain/` is only `layout.py` so far; ports (`WikiRepo`, `JobQueue`,
  `Sandbox`, …) and a `bootstrap.py` composition root are not written yet.
- Phases 2+ (FTS index, OpenAPI contract tests, TS client, MCP at `/mcp`, CLI, A2A).
