"""Public entry point for knowledge-base memory.

    from selfmemory.knowledge import KnowledgeMemory

    mem = KnowledgeMemory(db_path="memory.db", llm_provider="anthropic")
    mem.remember("Shrijayan uses uv, never pip, on the selfmemory repo.")
    print(mem.ask("what package manager does Shrijayan use?").text)

Four operations -- ``remember``, ``ask``, ``page``, ``lint`` -- instead of a
vector-store and embedder factory pair.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from selfmemory.knowledge.compactor import Compactor
from selfmemory.knowledge.lint import Finding, Linter
from selfmemory.knowledge.retrieval import Answer, Retriever
from selfmemory.knowledge.session import (
    AgentRunner,
    OpencodeRunner,
    extract_citations,
)
from selfmemory.knowledge.store import (
    DEFAULT_SCHEMA_DOC,
    KnowledgeStore,
    SQLiteKnowledgeStore,
)
from selfmemory.knowledge.workspace import Workspace
from selfmemory.utils.factory import LlmFactory

if TYPE_CHECKING:
    from selfmemory.knowledge.models import CompactionResult, LogEntry, Page

logger = logging.getLogger(__name__)

DEFAULT_PROJECT = "default"


class KnowledgeMemory:
    def __init__(
        self,
        db_path: str = ":memory:",
        llm_provider: str = "anthropic",
        llm_config: dict | None = None,
        store: KnowledgeStore | None = None,
        llm=None,
        project_id: str = DEFAULT_PROJECT,
        runner: AgentRunner | None = None,
    ):
        self.store = store or SQLiteKnowledgeStore(db_path)
        self.project_id = project_id
        self.runner = runner or OpencodeRunner()

        # The LLM is built on first use, not here: research() runs an external
        # agent, so a caller using only that path should not have to configure
        # a provider at all.
        self._llm = llm
        self._llm_provider = llm_provider
        self._llm_config = llm_config

    @property
    def llm(self):
        if self._llm is None:
            self._llm = LlmFactory.create(self._llm_provider, self._llm_config)
        return self._llm

    @property
    def compactor(self) -> Compactor:
        return Compactor(self.store, self.llm)

    @property
    def retriever(self) -> Retriever:
        return Retriever(self.store, self.llm)

    @property
    def linter(self) -> Linter:
        return Linter(self.store, self.llm)

    def _project(self, project_id: str | None) -> str:
        return project_id or self.project_id

    # -- write ---------------------------------------------------------

    def remember(
        self,
        text: str,
        metadata: dict | None = None,
        project_id: str | None = None,
    ) -> CompactionResult:
        """Ingest one source and merge it into the affected pages.

        This is the expensive path -- two model calls. The server runs it as a
        background job off an append-only inbox rather than inline on the
        request.
        """
        return self.compactor.compact(
            self._project(project_id), text, metadata=metadata
        )

    # -- read ----------------------------------------------------------

    def ask(self, question: str, project_id: str | None = None) -> Answer:
        return self.retriever.ask(self._project(project_id), question)

    def search(
        self, query: str, limit: int = 8, project_id: str | None = None
    ) -> list[Page]:
        return self.retriever.search(self._project(project_id), query, limit=limit)

    def page(self, slug: str, project_id: str | None = None) -> Page | None:
        return self.store.get_page(self._project(project_id), slug)

    def pages(self, project_id: str | None = None) -> list[Page]:
        return self.store.list_pages(self._project(project_id))

    def index(self, project_id: str | None = None):
        return self.store.index(self._project(project_id))

    def log(self, limit: int = 50, project_id: str | None = None) -> list[LogEntry]:
        return self.store.log(self._project(project_id), limit=limit)

    def research(
        self,
        question: str,
        project_ids: list[str] | None = None,
        timeout: int = 180,
    ) -> Answer:
        """Answer by running an agent over the pages themselves.

        Slower and more expensive than ``ask``, and better at anything needing
        more than one hop -- following links, reconciling two pages, tracing
        when a decision changed.

        The caller passes the projects it has already resolved as permitted;
        this does not check access. Nothing outside that list is written to the
        workspace, so nothing outside it can be read.
        """
        projects = project_ids or [self.project_id]
        with Workspace.materialize(self.store, projects, writable=False) as ws:
            prompt = (
                "Answer the question from the pages in this directory.\n\n"
                "Start with index.md, then open only the pages you need and "
                "follow [[slug]] links between them. Cite every page you used "
                "as [[slug]]. If the pages do not answer the question, say so "
                "plainly rather than guessing.\n\n"
                f"Question: {question}"
            )
            result = self.runner.run(
                ws.session_root, prompt, writable=False, timeout=timeout
            )

        known = {p.slug for pid in projects for p in self.store.list_pages(pid)}
        cited = extract_citations(result.text, known)
        pages = [
            page
            for slug in cited
            for pid in projects
            if (page := self.store.get_page(pid, slug)) is not None
        ]
        return Answer(text=result.text, pages=pages)

    # -- maintenance ---------------------------------------------------

    def lint(self, project_id: str | None = None) -> list[Finding]:
        return self.linter.lint(self._project(project_id))

    # -- schema --------------------------------------------------------

    @property
    def schema_doc(self) -> str:
        return self.store.get_schema_doc(self.project_id)

    def set_schema_doc(self, text: str, project_id: str | None = None) -> None:
        self.store.set_schema_doc(self._project(project_id), text)


__all__ = ["DEFAULT_SCHEMA_DOC", "KnowledgeMemory"]
