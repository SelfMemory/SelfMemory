"""Maintenance pass.

Knowledge bases decay: pages contradict each other, duplicates accumulate,
links rot. The lint pass is what keeps the base worth reading, and it runs as a
scheduled job rather than on the write path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from selfmemory.knowledge import prompts
from selfmemory.knowledge.json_utils import parse_json_object
from selfmemory.knowledge.models import LogEntry, utcnow

if TYPE_CHECKING:
    from selfmemory.knowledge.store import KnowledgeStore

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

VALID_KINDS = {"contradiction", "duplicate", "stale", "orphan", "broken_link"}


@dataclass
class Finding:
    kind: str
    slugs: list[str] = field(default_factory=list)
    detail: str = ""
    fix: str = ""


class Linter:
    def __init__(self, store: KnowledgeStore, llm):
        self.store = store
        self.llm = llm

    def lint(self, project_id: str) -> list[Finding]:
        pages = self.store.list_pages(project_id)
        if not pages:
            return []

        findings = self._broken_links(pages)
        findings.extend(self._llm_findings(project_id, pages))

        self.store.apply(
            project_id,
            [],
            [
                LogEntry(
                    ts=utcnow(),
                    op="lint",
                    detail=f"{len(pages)} pages, {len(findings)} findings",
                )
            ],
        )
        return findings

    def _broken_links(self, pages) -> list[Finding]:
        """Deterministic check -- no reason to spend a model call on this."""
        known = {p.slug for p in pages}
        findings = []
        for page in pages:
            for target in sorted(set(_LINK_RE.findall(page.body))):
                if target not in known:
                    findings.append(
                        Finding(
                            kind="broken_link",
                            slugs=[page.slug],
                            detail=f"{page.slug} links to [[{target}]], "
                            "which does not exist",
                            fix=f"create {target} or remove the link",
                        )
                    )
        return findings

    def _llm_findings(self, project_id, pages) -> list[Finding]:
        user = (
            f"## Page index\n{prompts.render_index(self.store.index(project_id))}\n\n"
            f"## All pages\n{prompts.render_pages(pages)}"
        )
        raw = self.llm.generate_response(
            [
                {"role": "system", "content": prompts.LINT_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        data = parse_json_object(raw)

        known = {p.slug for p in pages}
        findings = []
        for item in data.get("findings", []):
            if not isinstance(item, dict):
                continue
            kind = item.get("kind", "")
            if kind not in VALID_KINDS or kind == "broken_link":
                continue
            slugs = [s for s in item.get("slugs", []) if s in known]
            if not slugs:
                continue
            findings.append(
                Finding(
                    kind=kind,
                    slugs=slugs,
                    detail=item.get("detail", ""),
                    fix=item.get("fix", ""),
                )
            )
        return findings
