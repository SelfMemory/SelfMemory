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
from selfmemory.knowledge.session import (
    AgentRunner,
    AgentSessionError,
    OpencodeRunner,
    SessionResult,
)
from selfmemory.knowledge.store import (
    DEFAULT_SCHEMA_DOC,
    ConcurrentEditError,
    KnowledgeStore,
    SQLiteKnowledgeStore,
)
from selfmemory.knowledge.workspace import Workspace

__all__ = [
    "DEFAULT_SCHEMA_DOC",
    "AgentRunner",
    "AgentSessionError",
    "Answer",
    "CompactionResult",
    "ConcurrentEditError",
    "Finding",
    "IndexEntry",
    "KnowledgeMemory",
    "KnowledgeStore",
    "LogEntry",
    "OpencodeRunner",
    "Page",
    "PageEdit",
    "SessionResult",
    "SQLiteKnowledgeStore",
    "Source",
    "Workspace",
]
