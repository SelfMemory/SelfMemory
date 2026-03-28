"""Helpers for translating memory HTTP requests into core memory calls."""

from typing import Any, Iterable

SUPPORTED_SEARCH_FILTERS = {
    "include_metadata",
    "limit",
    "match_all_tags",
    "people_mentioned",
    "sort_by",
    "tags",
    "temporal_filter",
    "threshold",
    "topic_category",
}


def serialize_messages(messages: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert request message models into plain dictionaries."""
    serialized_messages = []
    for message in messages:
        if hasattr(message, "model_dump"):
            serialized_messages.append(message.model_dump())
        else:
            serialized_messages.append(dict(message))
    return serialized_messages


def split_memory_metadata(
    metadata: dict[str, Any] | None,
) -> tuple[str, str, str, dict[str, Any]]:
    """Separate reserved memory fields from arbitrary metadata."""
    custom_metadata = dict(metadata or {})
    custom_metadata.pop("project_id", None)
    custom_metadata.pop("organization_id", None)
    tags = _coerce_metadata_text(custom_metadata.pop("tags", ""))
    people_mentioned = _coerce_metadata_text(
        custom_metadata.pop("people_mentioned", "")
    )
    topic_category = _coerce_metadata_text(custom_metadata.pop("topic_category", ""))
    return tags, people_mentioned, topic_category, custom_metadata


def split_csv_values(value: str | list[str] | None) -> list[str] | None:
    """Normalize string or list filters into a clean list of unique values."""
    if value is None:
        return None

    raw_values = value.split(",") if isinstance(value, str) else value
    normalized = []
    for raw_value in raw_values:
        cleaned = str(raw_value).strip()
        if cleaned:
            normalized.append(cleaned)

    if not normalized:
        return None

    return list(dict.fromkeys(normalized))


def build_search_kwargs(
    *,
    scope_user_id: str,
    filters: dict[str, Any] | None = None,
    people_mentioned: str | list[str] | None = None,
) -> dict[str, Any]:
    """Build a clean kwargs dict for ``SelfMemory.search``."""
    search_kwargs: dict[str, Any] = {"user_id": scope_user_id}
    request_filters = dict(filters or {})

    for filter_key in SUPPORTED_SEARCH_FILTERS:
        if filter_key in {"people_mentioned", "tags"}:
            continue

        filter_value = request_filters.get(filter_key)
        if filter_value is not None:
            search_kwargs[filter_key] = filter_value

    normalized_tags = split_csv_values(request_filters.get("tags"))
    if normalized_tags:
        search_kwargs["tags"] = normalized_tags

    normalized_people = split_csv_values(people_mentioned) or split_csv_values(
        request_filters.get("people_mentioned")
    )
    if normalized_people:
        search_kwargs["people_mentioned"] = normalized_people

    return search_kwargs


def _coerce_metadata_text(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    if value is None:
        return ""
    return str(value).strip()
