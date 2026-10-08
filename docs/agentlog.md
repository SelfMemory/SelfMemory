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
