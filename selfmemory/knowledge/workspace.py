"""Ephemeral, single-tenant materialization of projects on disk.

An agent needs files to grep, but files are the wrong source of truth: they have
no transactions, and a long-lived directory per tenant is state we do not want
to run. So a workspace is a disposable projection -- pages written out for the
length of one session, then wiped.

The isolation guarantee is structural rather than enforced: a workspace only
ever contains projects the caller resolved as permitted, so content that was
never written here cannot be reached by anything the agent is told to do.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from selfmemory.knowledge.models import Page, utcnow

if TYPE_CHECKING:
    from selfmemory.knowledge.store import KnowledgeStore

INDEX_FILE = "index.md"
SCHEMA_FILE = "schema.md"
PAGES_DIR = "pages"

# Written into the workspace so the agent runtime cannot edit or shell out
# during a read-only session. Defence in depth -- the disposable workspace
# already bounds the blast radius.
READONLY_AGENT = {
    "$schema": "https://opencode.ai/config.json",
    "agent": {
        "reader": {
            "description": "Answers questions from the knowledge base.",
            "mode": "primary",
            "tools": {
                "write": False,
                "edit": False,
                "patch": False,
                "bash": False,
                "webfetch": False,
                "read": True,
                "grep": True,
                "glob": True,
                "list": True,
            },
        }
    },
}


def page_to_markdown(page: Page) -> str:
    fm = dict(page.frontmatter)
    fm.setdefault("title", page.title)
    dumped = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n# {page.title}\n\n{page.body.strip()}\n"


def markdown_to_page(slug: str, text: str) -> Page:
    """Parse a page file back. Tolerates a missing or malformed frontmatter
    block -- an agent hand-editing markdown will occasionally produce one."""
    frontmatter: dict = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            try:
                loaded = yaml.safe_load(parts[1])
                if isinstance(loaded, dict):
                    frontmatter = loaded
                    body = parts[2]
            except yaml.YAMLError:
                pass

    body = body.strip()
    title = frontmatter.get("title", "")
    lines = body.split("\n")
    if lines and lines[0].startswith("# "):
        title = title or lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()

    return Page(
        slug=slug,
        title=title or slug,
        body=body,
        frontmatter=frontmatter,
        updated_at=utcnow(),
    )


def render_index(pages: list[Page]) -> str:
    lines = [
        "# Index",
        "",
        "Every page in this knowledge base. Read this first to orient, then open",
        "only the pages you need.",
        "",
    ]
    if not pages:
        lines.append("_No pages yet._")
    for page in sorted(pages, key=lambda p: p.slug):
        summary = page.summary or "(no summary)"
        lines.append(f"- `{page.slug}` — **{page.title}** — {summary}")
    return "\n".join(lines) + "\n"


@dataclass
class Workspace:
    """A materialized set of projects. Use as a context manager to guarantee
    teardown; the directory is the only place page bodies exist in plaintext."""

    root: Path
    project_ids: list[str]
    writable: bool = False
    _snapshot: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)

    @property
    def session_root(self) -> Path:
        """Where the agent is pointed.

        A single-project session is rooted at that project so paths in answers
        are not cluttered with an id the caller already knows; a multi-project
        session is rooted above them all so the agent can search across.
        """
        if len(self.project_ids) == 1:
            return self.root / self.project_ids[0]
        return self.root

    def project_dir(self, project_id: str) -> Path:
        return self.root / project_id

    # -- lifecycle -----------------------------------------------------

    @classmethod
    def materialize(
        cls,
        store: KnowledgeStore,
        project_ids: list[str],
        *,
        writable: bool = False,
        root: str | Path | None = None,
    ) -> Workspace:
        if not project_ids:
            raise ValueError("a workspace needs at least one project")
        if writable and len(project_ids) > 1:
            # A writable multi-project session lets content in one project
            # direct the agent to copy another into it.
            raise ValueError("writable sessions must hold exactly one project")

        base = Path(root) if root else Path(tempfile.mkdtemp(prefix="selfmem-ws-"))
        base.mkdir(parents=True, exist_ok=True)
        ws = cls(root=base, project_ids=list(project_ids), writable=writable)

        for project_id in project_ids:
            pages = store.list_pages(project_id)
            pdir = ws.project_dir(project_id)
            (pdir / PAGES_DIR).mkdir(parents=True, exist_ok=True)
            (pdir / INDEX_FILE).write_text(render_index(pages), encoding="utf-8")
            (pdir / SCHEMA_FILE).write_text(
                store.get_schema_doc(project_id), encoding="utf-8"
            )

            snapshot: dict[str, str] = {}
            for page in pages:
                text = page_to_markdown(page)
                path = ws.page_path(project_id, page.slug)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                snapshot[page.slug] = text
            ws._snapshot[project_id] = snapshot

        if not writable:
            (ws.session_root / "opencode.json").write_text(
                json.dumps(READONLY_AGENT, indent=2), encoding="utf-8"
            )
        return ws

    def page_path(self, project_id: str, slug: str) -> Path:
        return self.project_dir(project_id) / PAGES_DIR / f"{slug}.md"

    def wipe(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, *exc) -> None:
        self.wipe()

    # -- read back -----------------------------------------------------

    def changed_pages(self, project_id: str | None = None) -> list[Page]:
        """Pages the agent created or modified, by byte comparison.

        Only changed files come back, so an untouched page is never rewritten
        and never bumps its version -- which keeps the optimistic lock honest.
        """
        project_id = project_id or self.project_ids[0]
        pages_root = self.project_dir(project_id) / PAGES_DIR
        snapshot = self._snapshot.get(project_id, {})

        changed = []
        for path in sorted(pages_root.rglob("*.md")):
            slug = path.relative_to(pages_root).with_suffix("").as_posix()
            text = path.read_text(encoding="utf-8")
            if snapshot.get(slug) != text:
                changed.append(markdown_to_page(slug, text))
        return changed

    def deleted_slugs(self, project_id: str | None = None) -> list[str]:
        project_id = project_id or self.project_ids[0]
        pages_root = self.project_dir(project_id) / PAGES_DIR
        present = {
            p.relative_to(pages_root).with_suffix("").as_posix()
            for p in pages_root.rglob("*.md")
        }
        return sorted(set(self._snapshot.get(project_id, {})) - present)
