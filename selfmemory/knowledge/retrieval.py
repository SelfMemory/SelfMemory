"""Reading the knowledge base.

Retrieval is full-text over page bodies plus the index -- no embeddings, no
vector database. Pages are already compiled and deduplicated by the compactor,
so keyword recall over a few hundred short pages is enough, and the index gives
the model a map of everything it did not retrieve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from selfmemory.knowledge import prompts

if TYPE_CHECKING:
    from selfmemory.knowledge.models import Page
    from selfmemory.knowledge.store import KnowledgeStore

MAX_CONTEXT_PAGES = 8


@dataclass
class Answer:
    text: str
    pages: list[Page] = field(default_factory=list)

    @property
    def citations(self) -> list[str]:
        return [p.slug for p in self.pages]


class Retriever:
    def __init__(self, store: KnowledgeStore, llm):
        self.store = store
        self.llm = llm

    def search(self, project_id: str, query: str, limit: int = 8) -> list[Page]:
        return self.store.search(project_id, query, limit=limit)

    def ask(self, project_id: str, question: str) -> Answer:
        pages = self.search(project_id, question, limit=MAX_CONTEXT_PAGES)
        index = self.store.index(project_id)
        if not index:
            return Answer(text="The knowledge base is empty.", pages=[])

        user = (
            f"## Page index\n{prompts.render_index(index)}\n\n"
            f"## Retrieved pages\n{prompts.render_pages(pages)}\n\n"
            f"## Question\n{question}"
        )
        text = self.llm.generate_response(
            [
                {"role": "system", "content": prompts.ANSWER_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        return Answer(text=(text or "").strip(), pages=pages)
