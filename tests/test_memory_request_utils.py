"""Tests for lightweight memory request helper functions."""

from server.memory_request_utils import (
    build_search_kwargs,
    serialize_messages,
    split_csv_values,
    split_memory_metadata,
)


class DummyMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def model_dump(self):
        return {"role": self.role, "content": self.content}


def test_serialize_messages_preserves_roles():
    messages = [
        DummyMessage("system", "Rules"),
        DummyMessage("user", "Remember this"),
    ]

    assert serialize_messages(messages) == [
        {"role": "system", "content": "Rules"},
        {"role": "user", "content": "Remember this"},
    ]


def test_split_memory_metadata_preserves_custom_fields():
    tags, people, topic, metadata = split_memory_metadata(
        {
            "tags": ["work", "meeting"],
            "people_mentioned": "Alice, Bob",
            "topic_category": "planning",
            "source": "mcp_unified",
        }
    )

    assert tags == "work,meeting"
    assert people == "Alice, Bob"
    assert topic == "planning"
    assert metadata == {"source": "mcp_unified"}


def test_split_csv_values_normalizes_strings_and_lists():
    assert split_csv_values("Alice, Bob , Alice") == ["Alice", "Bob"]
    assert split_csv_values(["Alice", " Bob ", ""]) == ["Alice", "Bob"]


def test_build_search_kwargs_normalizes_scope_and_people_filters():
    search_kwargs = build_search_kwargs(
        scope_user_id="project-123",
        filters={"limit": 5, "tags": "auth,security", "people_mentioned": "Alice,Bob"},
    )

    assert search_kwargs == {
        "user_id": "project-123",
        "limit": 5,
        "tags": ["auth", "security"],
        "people_mentioned": ["Alice", "Bob"],
    }


def test_top_level_people_filter_takes_precedence():
    search_kwargs = build_search_kwargs(
        scope_user_id="project-123",
        filters={"people_mentioned": "Bob"},
        people_mentioned="Alice,Charlie",
    )

    assert search_kwargs["people_mentioned"] == ["Alice", "Charlie"]
