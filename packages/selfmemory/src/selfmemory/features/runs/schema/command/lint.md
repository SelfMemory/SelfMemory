Lint the wiki against OKF v0.2 + SelfMemory rules. Scope hint (optional): $ARGUMENTS

Check every scope you can read for:

- concept pages missing required OKF `type` frontmatter
- top-level `timestamp` still in use (should be `generated.at`)
- `sources` that are bare strings instead of objects with `resource`
- concept pages dumped at the scope root that should live under a category folder
  (reserved: `index.md`, `log.md`, `promotions.md` at root are fine)
- `index.md` with frontmatter other than root-only `okf_version`
- folders with concept children but no `index.md`
- `log.md` not using `## YYYY-MM-DD` newest-first grouping
- pages whose `scope:` frontmatter disagrees with the directory they are in
- links that point downward (org -> project, project -> user) — always a bug
- broken bundle-absolute (`/…`), relative, or `[[wiki-links]]`
- orphan pages with no inbound links
- contradictions / superseded claims; `stale_after` in the past
- concepts referenced repeatedly but with no page of their own
- broken image references (markdown `![..](images/..)` pointing at a missing file)
- `images/` files that no page references (orphan media)
- image links with empty or placeholder captions that a vision pass could fill
- entries sitting in any `promotions.md` awaiting review

Report findings grouped by severity, each with the file path. Do not fix anything —
this is a read-only report.
