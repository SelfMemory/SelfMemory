"""The compactor: merge a new source into the knowledge base.

Two LLM passes, because one pass over every page does not scale and one pass
over blind full-text hits misses pages that matter but share no keywords:

1. *select* -- given the index (cheap, one line per page), pick which pages the
   source touches and which new pages it warrants. Full-text hits are offered
   as hints but the model is not limited to them.
2. *merge*  -- given those pages in full, rewrite them.

Writes apply as one optimistically-locked transaction, so two concurrent
ingests cannot silently clobber each other.
"""

from __future__ import annotations

import logging
import uuid

from selfmemory.knowledge import prompts
from selfmemory.knowledge.json_utils import parse_json_object
from selfmemory.knowledge.models import (
    CompactionResult,
    LogEntry,
    Page,
    PageEdit,
    Source,
    utcnow,
)
from selfmemory.knowledge.store import KnowledgeStore, slugify

logger = logging.getLogger(__name__)

MAX_PAGES_PER_COMPACTION = 8


class Compactor:
    def __init__(self, store: KnowledgeStore, llm):
        self.store = store
        self.llm = llm

    def compact(
        self,
        project_id: str,
        text: str,
        metadata: dict | None = None,
        source_id: str | None = None,
    ) -> CompactionResult:
        source = Source(
            id=source_id or uuid.uuid4().hex,
            content=text,
            metadata=metadata or {},
        )
        self.store.add_source(project_id, source)

        index = self.store.index(project_id)
        hints = self.store.search(project_id, text, limit=MAX_PAGES_PER_COMPACTION)
        targets = self._select(project_id, source, index, hints)

        # Capture versions at read time -- that is what the optimistic lock
        # compares against, so a concurrent ingest that lands between here and
        # the write is caught rather than silently overwritten.
        existing: list[Page] = []
        versions: dict[str, int | None] = {}
        for slug in targets["open"]:
            page = self.store.get_page(project_id, slug)
            if page is not None:
                existing.append(page)
                versions[slug] = self.store.page_version(project_id, slug)

        edits = self._merge(project_id, source, existing, targets["propose"])
        self._write(project_id, source, existing, versions, edits)

        return CompactionResult(
            source_id=source.id,
            edits=edits,
            pages_considered=[p.slug for p in existing],
        )

    # -- pass 1 --------------------------------------------------------

    def _select(self, project_id, source, index, hints) -> dict:
        if not index:
            return {"open": [], "propose": []}

        hint_line = ", ".join(p.slug for p in hints) or "(none)"
        user = (
            f"## Page index\n{prompts.render_index(index)}\n\n"
            f"## Full-text hits (hints, not a shortlist)\n{hint_line}\n\n"
            f"## New source\n{source.content}"
        )
        raw = self._ask(prompts.COMPACT_SELECT_SYSTEM, user)
        data = parse_json_object(raw)

        known = {e.slug for e in index}
        open_slugs = [
            s for s in data.get("open", []) if isinstance(s, str) and s in known
        ][:MAX_PAGES_PER_COMPACTION]

        propose = []
        for item in data.get("propose", []):
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("slug") or ""
            slug = slugify(item.get("slug") or title)
            if slug and slug not in known and slug not in {p["slug"] for p in propose}:
                propose.append({"slug": slug, "title": title or slug})

        remaining = max(0, MAX_PAGES_PER_COMPACTION - len(open_slugs))
        return {"open": open_slugs, "propose": propose[:remaining]}

    # -- pass 2 --------------------------------------------------------

    def _merge(self, project_id, source, existing, propose) -> list[PageEdit]:
        schema_doc = self.store.get_schema_doc(project_id)
        proposed_line = (
            "\n".join(f"- {p['slug']} — {p['title']}" for p in propose) or "(none)"
        )
        user = (
            f"## Schema conventions\n{schema_doc}\n\n"
            f"## New source\n{source.content}\n\n"
            f"## Existing pages to rewrite\n{prompts.render_pages(existing)}\n\n"
            f"## New pages to create\n{proposed_line}"
        )
        raw = self._ask(prompts.COMPACT_MERGE_SYSTEM, user)
        data = parse_json_object(raw)

        existing_slugs = {p.slug for p in existing}
        allowed = existing_slugs | {p["slug"] for p in propose}

        edits: list[PageEdit] = []
        seen: set[str] = set()
        for item in data.get("edits", []):
            if not isinstance(item, dict):
                continue
            slug = slugify(item.get("slug", ""))
            op = item.get("op", "")
            if slug in seen or op not in {"create", "update", "noop"}:
                continue
            # The model wandering outside the pages it was handed is fine for a
            # create -- better a new page than a dropped fact -- but it must not
            # rewrite a page it never read.
            if slug not in allowed and op != "create":
                logger.warning(
                    "compactor targeted unselected page %r with op %r; skipping",
                    slug,
                    op,
                )
                continue
            if op == "update" and slug not in existing_slugs:
                op = "create"
            if op == "create" and slug in existing_slugs:
                op = "update"
            seen.add(slug)
            edits.append(
                PageEdit(
                    op=op,
                    slug=slug,
                    title=item.get("title", "") or slug,
                    summary=item.get("summary", ""),
                    body=item.get("body", ""),
                    reason=item.get("reason", ""),
                )
            )
        return edits

    # -- apply ---------------------------------------------------------

    def _write(self, project_id, source, existing, versions, edits) -> None:
        by_slug = {p.slug: p for p in existing}
        writes: list[tuple[Page, int | None]] = []
        log_entries: list[LogEntry] = []
        now = utcnow()

        for edit in edits:
            if edit.op == "noop" or not edit.body.strip():
                continue
            current = by_slug.get(edit.slug)
            # Pages we never read are expected not to exist; if one appeared in
            # the meantime the store rejects the batch.
            version = versions.get(edit.slug)
            frontmatter = dict(current.frontmatter) if current else {}
            frontmatter["summary"] = edit.summary or frontmatter.get("summary", "")
            sources = list(frontmatter.get("sources", []))
            if source.id not in sources:
                sources.append(source.id)
            frontmatter["sources"] = sources[-50:]

            page = Page(
                slug=edit.slug,
                title=edit.title,
                body=edit.body,
                frontmatter=frontmatter,
                created_at=current.created_at if current else now,
                updated_at=now,
            )
            writes.append((page, version))
            log_entries.append(
                LogEntry(
                    ts=now,
                    op=f"ingest.{edit.op}",
                    detail=f"{edit.slug}: {edit.reason}".strip().rstrip(":"),
                )
            )

        if not writes:
            log_entries.append(
                LogEntry(ts=now, op="ingest.noop", detail=f"source {source.id}")
            )
        self.store.apply(project_id, writes, log_entries)

    # -- llm -----------------------------------------------------------

    def _ask(self, system: str, user: str) -> str:
        return self.llm.generate_response(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
