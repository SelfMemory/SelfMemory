Ingest this source into the wiki: $ARGUMENTS

Work in this order, and do not skip steps. Target **OKF v0.2**
(https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md):

1. Read `$SCOPE_ROOT/index.md` first (and relevant nested category `index.md` files).
2. Read the source file(s) named above in full.
3. Decide: update an existing concept or create a new one? Prefer updating.
4. Choose a **nested** path under `$SCOPE_ROOT` — do not dump concepts at the scope root.
   Example: `policies/security-policy.md`, `tables/orders.md`.
5. Write OKF concept frontmatter: required `type`; recommended `title`, `description`,
   `resource`, `tags`, `generated: { by: selfmemory-ingest/agent, at: <ISO-8601 Z> }`,
   `status`, structured `sources` (each entry has `resource`, ideally `id` + `title`),
   and SelfMemory `scope`. Do **not** use top-level `timestamp`.
6. Body: structured markdown; attribute claims with footnotes keyed to `sources[].id`.
6a. Images: if the source carries images (decks, diagrams, screenshots), file them
    hierarchically under `<concept>/images/` inside `$SCOPE_ROOT`, reference them
    from the page with relative `![caption](images/...)` links, and if your model
    has vision, view each and encode its content into the page text (charts → tables,
    diagrams → prose description). No vision → keep the reference with the caption
    `not yet described; run a vision ingest pass`. Never delete or skip images.
7. Link with bundle-absolute markdown links where possible:
   `[customers](/tables/customers.md)`. Same-scope or upward only — never downward.
8. Refresh every touched folder’s `index.md` (no frontmatter except root
   `okf_version: "0.2"`). List `* [Title](rel) - description`.
9. Prepend to `$SCOPE_ROOT/log.md` under today’s `## YYYY-MM-DD` (newest date first):
   `* **Creation**: …` / `* **Update**: …` with links to paths you touched.
10. Org-wide facts from a project/user ingest → `$SCOPE_ROOT/promotions.md` proposals only.
    Never write into `wiki/org/` yourself from a narrower scope.

End with a 3–6 line summary: paths created, paths updated, promotions queued.
