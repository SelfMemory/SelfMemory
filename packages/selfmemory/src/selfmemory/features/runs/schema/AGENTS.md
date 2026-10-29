# SelfMemory — wiki schema

You are the maintainer of a scoped, multi-tenant LLM wiki for one organization. Read this
file fully before any ingest, query, or lint.

Your working directory is the organization's root. Paths below are relative to it.

## Layout

```
raw/    org/ | projects/<project>/ | users/<user>/    immutable sources — never edit
wiki/   org/ | projects/<project>/ | users/<user>/    you own this layer entirely
```

Each **scope directory is an OKF bundle** ([Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)).
Canonical spec: that repo’s `SPEC.md`. The copy under
`GoogleCloudPlatform/knowledge-catalog/okf` is a frozen snapshot — do not target it.

Reserved files in a scope:

- `index.md` — directory listing for progressive disclosure (OKF §8).
- `log.md` — chronological update history (OKF §9).
- `promotions.md` — (project and user scopes only; SelfMemory extension) facts that look
  org-wide, queued for review.

## Scope is the directory

A page's scope is the directory it lives in. There is no other scope marker that matters.

- `wiki/org/` — every employee.
- `wiki/projects/<p>/` — members of that project only.
- `wiki/projects/<p>/<c>/` — a sub-project: members of `<c>` only. Membership of `<p>` does
  not include it. Never write into a sub-project folder while ingesting into its parent.
- `wiki/users/<u>/` — that one person only.

The filesystem enforces this, not you. If you cannot read a directory, that is correct and
intentional — do not work around it, do not guess at its contents, and do not mention what
you imagine might be in it. Report only what you actually read.

## The write boundary

The environment variable `SCOPE_ROOT` names the single directory you may write inside for
this run. Writing anywhere else is a bug even when it seems helpful.

You may *read* anything the filesystem lets you read. You may *write* only under `SCOPE_ROOT`.

## Format: Open Knowledge Format (OKF) v0.2

After ingest, knowledge is an **OKF bundle**: markdown files with YAML frontmatter.
That bundle is the only intermediate form LLMs traverse — no SDK, no other serialization.

### Hierarchy

Organize concepts in nested folders. Path under the scope root is the concept's identity.
Subfolders and sub-subfolders are expected; do **not** flat-dump every concept at the
scope root (SelfMemory producer convention — OKF itself allows root concepts, we don't).

```
$SCOPE_ROOT/                          # = one OKF bundle
├── index.md                          # okf_version only (see below)
├── log.md
├── people/
│   ├── index.md
│   └── ada-lovelace.md
├── policies/
│   ├── index.md
│   └── security-policy.md
├── tables/
│   ├── index.md
│   ├── orders.md
│   └── customers.md
└── metrics/
    ├── index.md
    └── weekly_active_users.md
```

Rules:

- One concept = one `.md` file (every non-reserved `.md` is a concept).
- Create intermediate directories as needed.
- Every folder that holds concepts SHOULD have an `index.md` for progressive disclosure.
- Reserved filenames at **any** level (OKF): `index.md`, `log.md` — never use these names
  for concept documents. SelfMemory also reserves `promotions.md` at the scope root.

### Concept frontmatter (OKF §4)

Every concept starts with YAML frontmatter. **`type` is the only always-required key.**

```yaml
---
type: Policy
title: Security policy
description: Org-wide rules for handling credentials and production access.
resource: https://example.com/docs/security-policy
tags: [security, compliance]
generated: { by: selfmemory-ingest/agent, at: 2026-05-28T14:30:00Z }
status: stable
scope: org
sources:
  - id: raw-security
    resource: raw/org/security-policy.md
    title: Uploaded security policy
---
```

| Field | OKF | Meaning |
|-------|-----|---------|
| `type` | **required** | Kind of concept (unregistered string): `Person`, `Policy`, `Metric`, `Dataset`, `BigQuery Table`, `Playbook`, `API Endpoint`, `Concept`, … |
| `title` | recommended | Display name (else consumers derive from filename) |
| `description` | recommended | One sentence; used in `index.md` listings |
| `resource` | recommended | Canonical URI of the underlying asset (omit for abstract concepts) |
| `tags` | recommended | Short cross-cutting labels |
| `generated` | recommended | `{ by: <actor>, at: <ISO-8601> }` — who wrote it and when (replaces v0.1 `timestamp`) |
| `verified` | optional | Who confirmed it (mapping or list of `{ by, at }`) |
| `status` | optional | `draft` \| `stable` \| `deprecated` (default `stable`) |
| `stale_after` | optional | ISO-8601 instant after which content is stale |
| `sources` | recommended | Provenance list (see below) |
| `scope` | SelfMemory | `org` \| `project:<id>` \| `user:<id>` — must match the directory |

**Actors** (`generated.by`, `verified[].by`): `selfmemory-ingest/<model>`, `human:<id>`, or
`process:<id>` (OKF §7). Use the `human:` prefix for hand-authored or human-confirmed content.

**`sources` entries** (OKF §5.1): each entry MUST have `resource`. Optional: `id`, `title`,
`author`, `usage_count`, `last_modified`. For SelfMemory uploads, point `resource` at the
raw path under the data root (e.g. `raw/org/foo.md`) or an absolute URL. When the body
cites a source, set `id` and use a matching footnote:

```markdown
Credentials must not be committed to git.[^raw-security]

[^raw-security]: Uploaded security policy
```

Unknown extra frontmatter keys are allowed; consumers must not reject them.

Do **not** use top-level `timestamp` (retired in v0.2 — use `generated.at`).

### Index files (OKF §8)

`index.md` files have **no frontmatter**, except the **bundle-root** (scope-root) index
MAY declare the format version:

```markdown
---
okf_version: "0.2"
---

# Policies

* [Security policy](policies/security-policy.md) - Org-wide credential rules

# Tables

* [Orders](tables/orders.md) - One row per completed order
* [Customers](tables/) - Customer dimension
```

List children with relative links and the concept’s `description`. Keep category
`index.md` files in sync when you add or move pages.

### Log files (OKF §9)

`log.md` is date-grouped, **newest first**, no concept frontmatter:

```markdown
# Directory Update Log

## 2026-05-28
* **Creation**: Added [Security policy](/policies/security-policy.md).
* **Update**: Enriched [Orders](/tables/orders.md) schema from new source.

## 2026-05-15
* **Initialization**: Created foundational directory structure.
```

Date headings MUST be `YYYY-MM-DD`. Leading bold words (`**Creation**`, `**Update**`,
`**Deprecation**`) are conventional.

### Links (OKF §6)

Prefer **bundle-absolute** links (path from the scope / bundle root, leading `/`):

```markdown
Joined with [customers](/tables/customers.md) on `customer_id`.
```

Relative links (`./other.md`, `../tables/customers.md`) are also valid.
`[[wiki-links]]` are accepted for same-scope / upward SelfMemory navigation.

## Link direction (SelfMemory)

Links may point sideways (same scope) or up (toward org). Never down.

- OK: a project page links `[security policy](../../org/policies/security-policy.md)`
- OK: within a scope, `[orders](/tables/orders.md)`
- Never: an org page links to a project or user page — most readers cannot follow it, and the
  link title alone leaks the existence of scoped work.

## Images & media assets (SelfMemory)

Raw sources and wiki pages carry images (deck screenshots, architecture diagrams,
charts, photos). They are first-class wiki assets, not decoration.

**Location** — file images hierarchically inside the scope, mirroring the concept
they illustrate:

```
$SCOPE_ROOT/industries/retail-banking/
├── index.md
├── retail-banking.md
└── images/                        # per-concept images
    ├── landscape-diagram.png
    └── slide05-architecture.png
```

- An `images/` folder sits beside the concept page(s) it belongs to. Category-wide
  assets go in `<category>/images/`; per-concept assets in `<concept>/images/`.
- Never write an image outside `$SCOPE_ROOT`, and never reference one outside the
  bundle — a page and its images must share the same scope so access and rendering
  stay consistent with the scope's access rules.

**Reference** — embed images with **relative** markdown links and a *descriptive
caption* (alt text). The caption is the text-layer meaning of the image; text-only
LLMs read captions, vision models read pixels:

```markdown
![Banking service landscape: 13 BIAN business domains, grouped into 5 layers](images/landscape-diagram.png)
```

Declare attachments in frontmatter when useful:

```yaml
images: [images/landscape-diagram.png, images/slide05-architecture.png]
```

**Image understanding (vision pass)** — if your runtime model has image
understanding (a vision-capable model), you are expected to *view* each attached
image and encode what it shows into the page text:

- diagrams → describe the structure, boxes, arrows, and labels in prose
- charts → transcribe the data into a markdown table
- screenshots/slides → extract the visible text and layout meaning

Keep **both**: the textual encoding (for text-only consumers) and the image
reference (for renderers and vision consumers). Never drop the image because you
described it.

**No vision model available** — keep the reference with a caption marking it
unread, so a later vision-capable ingest can fill it in:

```markdown
![images/landscape-diagram.png — not yet described; run a vision ingest pass](images/landscape-diagram.png)
```

Never delete the image just because you cannot read it.

**Query** — when a question depends on an image (a diagram, chart, or screenshot),
view the referenced image if a vision-capable model is available and answer from
it, citing both the page and the image file (`wiki/<scope>/<nested>/images/<file>`).
If no vision model is available, answer from the caption and say the image itself
has not been read.

**Lint** — check: broken image references, `images/` files no page references
(orphans), and image links without a descriptive caption.

## Fact routing (the rule that matters most)

Files are not the unit of secrecy — facts are. A project document routinely contains a mix
of project-only facts and facts that are really org-wide.

While ingesting into a project or user scope, if a fact clearly belongs to the whole org
(a policy, a company-wide decision, a shared definition):

**Do not write it upward.** Append a proposal to `promotions.md` in the current scope:

```
## [YYYY-MM-DD] proposed | <one-line fact>
source: <raw path>
rationale: <why this is org-wide, not project-specific>
```

A human with org write access reviews and merges it later. Silent upward propagation is the
one failure mode this whole system exists to prevent.

Downward context is free: read org pages freely while working in a project scope.

## Operations

**Ingest** — read the source, then: write or update OKF concept page(s) under the right
*nested* path inside `SCOPE_ROOT`, refresh category + root `index.md` files, prepend
today’s entries on `log.md` (newest-first), and queue anything org-wide into
`promotions.md`. Prefer updating existing pages; check indexes first.

**Query** — read each readable scope’s root `index.md`, drill through nested indexes into
concept pages. Cite as `wiki/<scope>/<nested/path>.md`. Read-only. If thin, say what is
missing — never present model knowledge as wiki content.

**Lint** — report only: missing `type`, concept pages using reserved names, flat root
clutter, indexes with illegal frontmatter (other than root `okf_version`), log format
drift, contradictions, orphans, downward links, `scope` disagreeing with directory,
broken links, stale `promotions.md` / `stale_after` entries.
