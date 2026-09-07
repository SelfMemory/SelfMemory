"""Knowledge-base memory: LLM-maintained markdown pages instead of vectors.

Facts are compiled into interlinked pages once and kept current, rather than
re-derived from raw chunks on every query.
"""

from selfmemory.knowledge.base import KnowledgeMemory
from selfmemory.knowledge.lint import Finding
from selfmemory.knowledge.models import (
    CompactionResult,
    IndexEntry,
    LogEntry,
    Page,
    PageEdit,
    Source,
)
from selfmemory.knowledge.retrieval import Answer
from selfmemory.knowledge.store import (
    DEFAULT_SCHEMA_DOC,
    ConcurrentEditError,
    KnowledgeStore,
    SQLiteKnowledgeStore,
)

__all__ = [
    "DEFAULT_SCHEMA_DOC",
    "Answer",
    "CompactionResult",
    "ConcurrentEditError",
    "Finding",
    "IndexEntry",
    "KnowledgeMemory",
    "KnowledgeStore",
    "LogEntry",
    "Page",
    "PageEdit",
    "SQLiteKnowledgeStore",
    "Source",
]
