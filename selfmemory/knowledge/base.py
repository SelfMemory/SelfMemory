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
from selfmemory.knowledge.store import (
    DEFAULT_SCHEMA_DOC,
    KnowledgeStore,
    SQLiteKnowledgeStore,
)
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
    ):
        self.store = store or SQLiteKnowledgeStore(db_path)
        self.llm = llm or LlmFactory.create(llm_provider, llm_config)
        self.project_id = project_id

        self.compactor = Compactor(self.store, self.llm)
        self.retriever = Retriever(self.store, self.llm)
        self.linter = Linter(self.store, self.llm)

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
