"""Tests for SelfMemory SDK add/search/delete flows with mocked services."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

MOCK_EMBEDDING = [0.1] * 768


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed.return_value = MOCK_EMBEDDING
    return embedder


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.collection_name = "test_collection"
    return store


@pytest.fixture
def memory_instance(mock_embedder, mock_vector_store):
    with (
        patch(
            "selfmemory.memory.main.EmbedderFactory.create",
            return_value=mock_embedder,
        ),
        patch(
            "selfmemory.memory.main.VectorStoreFactory.create",
            return_value=mock_vector_store,
        ),
    ):
        from selfmemory import SelfMemory

        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "test_collection",
                    "embedding_model_dims": 768,
                    "host": "localhost",
                    "port": 6333,
                },
            },
            "embedding": {
                "provider": "ollama",
                "config": {
                    "model": "nomic-embed-text",
                    "ollama_base_url": "http://localhost:11434",
                },
            },
        }
        memory = SelfMemory(config=config)
        yield memory


class TestSelfMemoryAdd:
    def test_add_calls_embed_and_insert(
        self, memory_instance, mock_embedder, mock_vector_store
    ):
        result = memory_instance.add("I have a BMW bike.", user_id="demo")

        assert result["success"] is True
        assert "memory_id" in result
        mock_embedder.embed.assert_called_once_with("I have a BMW bike.")
        mock_vector_store.insert.assert_called_once()

        call_kwargs = mock_vector_store.insert.call_args[1]
        assert call_kwargs["vectors"] == [MOCK_EMBEDDING]
        assert len(call_kwargs["ids"]) == 1
        assert call_kwargs["payloads"][0]["data"] == "I have a BMW bike."

    def test_add_stores_metadata(self, memory_instance, mock_vector_store):
        memory_instance.add(
            "Meeting with Sarah about budget",
            user_id="demo",
            tags="work,meeting",
            people_mentioned="Sarah",
            topic_category="finance",
        )

        payload = mock_vector_store.insert.call_args[1]["payloads"][0]
        assert payload["tags"] == "work,meeting"
        assert payload["people_mentioned"] == "Sarah"
        assert payload["topic_category"] == "finance"

    def test_add_includes_user_id_in_metadata(self, memory_instance, mock_vector_store):
        memory_instance.add("Test memory", user_id="alice")

        payload = mock_vector_store.insert.call_args[1]["payloads"][0]
        assert "user_id" in payload
        assert payload["user_id"] != ""

    def test_add_empty_content_fails(self, memory_instance):
        result = memory_instance.add("", user_id="demo")
        assert result.get("success") is False

    def test_add_returns_unique_ids(self, memory_instance, mock_vector_store):
        result1 = memory_instance.add("Memory one", user_id="demo")
        result2 = memory_instance.add("Memory two", user_id="demo")

        assert result1["memory_id"] != result2["memory_id"]


class TestSelfMemorySearch:
    def test_search_calls_embed_and_query(
        self, memory_instance, mock_embedder, mock_vector_store
    ):
        mock_vector_store.search.return_value = []

        memory_instance.search("bike", user_id="demo")

        mock_embedder.embed.assert_called_with("bike")
        mock_vector_store.search.assert_called_once()

    def test_search_returns_formatted_results(self, memory_instance, mock_vector_store):
        mock_point = MagicMock()
        mock_point.id = str(uuid.uuid4())
        mock_point.score = 0.95
        mock_point.payload = {
            "data": "I have a BMW bike.",
            "user_id": "demo_hash",
            "tags": "vehicle",
        }
        mock_vector_store.search.return_value = [mock_point]

        results = memory_instance.search("bike", user_id="demo")

        assert "results" in results
        assert len(results["results"]) == 1
        assert results["results"][0]["content"] == "I have a BMW bike."
        assert results["results"][0]["score"] == 0.95

    def test_search_passes_user_filters(self, memory_instance, mock_vector_store):
        mock_vector_store.search.return_value = []

        memory_instance.search("food", user_id="alice")

        call_kwargs = mock_vector_store.search.call_args[1]
        assert "filters" in call_kwargs
        assert "user_id" in call_kwargs["filters"]

    def test_search_empty_query_returns_all(self, memory_instance, mock_vector_store):
        mock_vector_store.search.return_value = []

        results = memory_instance.search("", user_id="demo")

        assert "results" in results


class TestSelfMemoryDeleteAll:
    def test_delete_all_deletes_user_memories(self, memory_instance, mock_vector_store):
        mock_point = MagicMock()
        mock_point.id = "mem-123"
        mock_point.payload = {"user_id": "demo_hash", "data": "old memory"}
        mock_vector_store.list.return_value = [mock_point]
        mock_vector_store.delete.return_value = True

        result = memory_instance.delete_all(user_id="demo")

        assert result["success"] is True
        assert result["deleted_count"] == 1
        mock_vector_store.delete.assert_called_once_with("mem-123")

    def test_delete_all_no_memories(self, memory_instance, mock_vector_store):
        mock_vector_store.list.return_value = []

        result = memory_instance.delete_all(user_id="demo")

        assert result["success"] is True
        assert result["deleted_count"] == 0
