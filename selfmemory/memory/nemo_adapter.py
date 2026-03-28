import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from selfmemory.memory.base import MemoryBase

logger = logging.getLogger(__name__)


@dataclass
class NemoMemoryItem:
    memory: str | None = None
    conversation: list[dict[str, str]] | None = None
    user_id: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


def _get_memory_item_class():
    try:
        from nat.memory.models import MemoryItem

        return MemoryItem
    except ImportError:
        return NemoMemoryItem


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _build_nemo_editor(config):
    provider = config.provider
    provider_config = config.config

    if provider == "mem0":
        from mem0 import AsyncMemoryClient
        from nat.plugins.mem0ai.mem0_editor import Mem0Editor

        api_key = config.api_key
        client = AsyncMemoryClient(api_key=api_key, **provider_config)
        return Mem0Editor(client)

    if provider == "redis":
        from nat.plugins.redis.redis_editor import RedisEditor

        return RedisEditor(**provider_config)

    if provider == "zep":
        from nat.plugins.zep_cloud.zep_editor import ZepEditor

        return ZepEditor(**provider_config)

    raise ValueError(
        f"Unsupported NeMo memory provider: '{provider}'. "
        f"Supported: 'mem0', 'redis', 'zep'"
    )


class NemoMemoryAdapter(MemoryBase):

    def __init__(self, config):
        self._editor = _build_nemo_editor(config)
        self._config = config
        self._memory_item_cls = _get_memory_item_class()
        logger.info(f"NemoMemoryAdapter initialized with provider: {config.provider}")

    def add(
        self,
        messages,
        *,
        user_id: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        project_id: str | None = None,
        organization_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        infer: bool = True,
    ) -> dict[str, Any]:
        memory_content = self._extract_content(messages)
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        item_metadata = metadata or {}
        if people_mentioned:
            item_metadata["people_mentioned"] = people_mentioned
        if topic_category:
            item_metadata["topic_category"] = topic_category
        if project_id:
            item_metadata["project_id"] = project_id
        if organization_id:
            item_metadata["organization_id"] = organization_id

        conversation = self._to_conversation(messages)
        item = self._memory_item_cls(
            memory=memory_content,
            conversation=conversation,
            user_id=user_id,
            tags=tag_list,
            metadata=item_metadata,
        )

        _run_async(self._editor.add_items([item]))

        memory_id = str(uuid.uuid4())
        logger.info(f"Memory added via NeMo ({self._config.provider}): {memory_id}")
        return {"id": memory_id, "success": True}

    def search(
        self,
        query: str = "",
        *,
        user_id: str,
        limit: int = 10,
        tags: list[str] | None = None,
        people_mentioned: list[str] | None = None,
        topic_category: str | None = None,
        temporal_filter: str | None = None,
        threshold: float | None = None,
        match_all_tags: bool = False,
        include_metadata: bool = True,
        sort_by: str = "relevance",
        project_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        nemo_results = _run_async(
            self._editor.search(query, top_k=limit, user_id=user_id)
        )
        formatted = self._format_nemo_results(nemo_results, include_metadata)

        if tags:
            formatted = self._filter_by_tags(formatted, tags, match_all_tags)
        if people_mentioned:
            formatted = self._filter_by_people(formatted, people_mentioned)
        if topic_category:
            formatted = [
                r
                for r in formatted
                if r.get("metadata", {}).get("topic_category") == topic_category
            ]
        if threshold is not None:
            formatted = [r for r in formatted if r.get("score", 0) >= threshold]

        return {"results": formatted[:limit]}

    def get_all(
        self,
        *,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        project_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        nemo_results = _run_async(
            self._editor.search("", top_k=limit, user_id=user_id)
        )
        formatted = self._format_nemo_results(nemo_results, include_metadata=True)
        return {"results": formatted[offset : offset + limit]}

    def delete(self, memory_id: str) -> dict[str, Any]:
        _run_async(self._editor.remove_items(memory_id=memory_id))
        logger.info(f"Memory {memory_id} deleted via NeMo")
        return {"success": True, "message": "Memory deleted successfully"}

    def delete_all(
        self,
        *,
        user_id: str,
        project_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        _run_async(self._editor.remove_items(user_id=user_id))
        logger.info(f"All memories deleted via NeMo for user: {user_id}")
        return {"success": True, "message": "All memories deleted"}

    def get_stats(self) -> dict[str, Any]:
        return {
            "provider": f"nemo_{self._config.provider}",
            "status": "active",
        }

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "provider": f"nemo_{self._config.provider}",
        }

    def close(self) -> None:
        logger.info("NemoMemoryAdapter closed")

    @staticmethod
    def _extract_content(messages) -> str:
        if isinstance(messages, str):
            return messages
        if isinstance(messages, dict):
            return messages.get("content", str(messages))
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    return msg.get("content", "")
            if messages and isinstance(messages[0], dict):
                return messages[0].get("content", "")
        return str(messages)

    @staticmethod
    def _to_conversation(messages) -> list[dict[str, str]]:
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]
        if isinstance(messages, dict):
            return [messages]
        if isinstance(messages, list):
            return messages
        return [{"role": "user", "content": str(messages)}]

    @staticmethod
    def _format_nemo_results(
        nemo_items, include_metadata: bool = True
    ) -> list[dict[str, Any]]:
        results = []
        for item in nemo_items:
            item_metadata = item.metadata if item.metadata else {}
            result = {
                "id": item_metadata.get("id", str(uuid.uuid4())),
                "content": item.memory or "",
            }
            if include_metadata:
                result["metadata"] = {
                    "data": item.memory or "",
                    "user_id": item.user_id,
                    "tags": ",".join(item.tags) if item.tags else "",
                    **item_metadata,
                }
            results.append(result)
        return results

    @staticmethod
    def _filter_by_tags(
        results: list[dict], tags: list[str], match_all: bool
    ) -> list[dict]:
        filtered = []
        for r in results:
            stored_tags = r.get("metadata", {}).get("tags", "")
            stored_set = {t.strip().lower() for t in stored_tags.split(",") if t.strip()}
            search_set = {t.lower() for t in tags}
            if match_all and search_set.issubset(stored_set):
                filtered.append(r)
            elif not match_all and search_set & stored_set:
                filtered.append(r)
        return filtered

    @staticmethod
    def _filter_by_people(
        results: list[dict], people: list[str]
    ) -> list[dict]:
        filtered = []
        for r in results:
            stored_people = r.get("metadata", {}).get("people_mentioned", "").lower()
            if any(p.lower() in stored_people for p in people):
                filtered.append(r)
        return filtered
