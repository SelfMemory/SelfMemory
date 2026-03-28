from unittest.mock import AsyncMock, patch

import pytest

from selfmemory.memory.nemo_adapter import NemoMemoryAdapter, NemoMemoryItem


@pytest.fixture
def mock_editor():
    editor = AsyncMock()
    editor.add_items = AsyncMock(return_value=None)
    editor.search = AsyncMock(return_value=[])
    editor.remove_items = AsyncMock(return_value=None)
    return editor


@pytest.fixture
def nemo_config():
    from selfmemory.configs.nemo import NemoMemoryConfig

    return NemoMemoryConfig(
        provider="mem0",
        config={"api_key": "test-key", "host": "http://localhost"},
    )


@pytest.fixture
def adapter(mock_editor, nemo_config):
    with patch(
        "selfmemory.memory.nemo_adapter._build_nemo_editor",
        return_value=mock_editor,
    ), patch(
        "selfmemory.memory.nemo_adapter._get_memory_item_class",
        return_value=NemoMemoryItem,
    ):
        return NemoMemoryAdapter(nemo_config)


class TestNemoMemoryAdapterAdd:
    def test_add_string_message(self, adapter, mock_editor):
        result = adapter.add("I love pizza", user_id="alice")

        assert result["success"] is True
        assert "id" in result
        mock_editor.add_items.assert_called_once()
        items = mock_editor.add_items.call_args[0][0]
        assert len(items) == 1
        assert items[0].memory == "I love pizza"
        assert items[0].user_id == "alice"

    def test_add_with_tags(self, adapter, mock_editor):
        result = adapter.add(
            "Meeting with team",
            user_id="bob",
            tags="work,meeting",
        )

        assert result["success"] is True
        items = mock_editor.add_items.call_args[0][0]
        assert items[0].tags == ["work", "meeting"]

    def test_add_with_metadata(self, adapter, mock_editor):
        result = adapter.add(
            "Important note",
            user_id="alice",
            people_mentioned="Sarah,Mike",
            topic_category="work",
            metadata={"priority": "high"},
        )

        assert result["success"] is True
        items = mock_editor.add_items.call_args[0][0]
        assert items[0].metadata["people_mentioned"] == "Sarah,Mike"
        assert items[0].metadata["topic_category"] == "work"
        assert items[0].metadata["priority"] == "high"

    def test_add_message_list(self, adapter, mock_editor):
        messages = [
            {"role": "user", "content": "I love sushi"},
            {"role": "assistant", "content": "Noted!"},
        ]
        result = adapter.add(messages, user_id="charlie")

        assert result["success"] is True
        items = mock_editor.add_items.call_args[0][0]
        assert items[0].memory == "I love sushi"
        assert items[0].conversation == messages

    def test_add_with_project_and_org(self, adapter, mock_editor):
        result = adapter.add(
            "Project note",
            user_id="alice",
            project_id="proj_1",
            organization_id="org_1",
        )

        assert result["success"] is True
        items = mock_editor.add_items.call_args[0][0]
        assert items[0].metadata["project_id"] == "proj_1"
        assert items[0].metadata["organization_id"] == "org_1"


class TestNemoMemoryAdapterSearch:
    def test_search_returns_formatted_results(self, adapter, mock_editor):
        mock_editor.search.return_value = [
            NemoMemoryItem(
                memory="I love pizza",
                user_id="alice",
                tags=["food"],
                metadata={"id": "mem_1"},
            ),
        ]

        result = adapter.search("pizza", user_id="alice")

        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == "I love pizza"
        assert result["results"][0]["id"] == "mem_1"
        mock_editor.search.assert_called_once_with(
            "pizza", top_k=10, user_id="alice"
        )

    def test_search_with_limit(self, adapter, mock_editor):
        mock_editor.search.return_value = []

        adapter.search("test", user_id="alice", limit=5)

        mock_editor.search.assert_called_once_with(
            "test", top_k=5, user_id="alice"
        )

    def test_search_empty_results(self, adapter, mock_editor):
        mock_editor.search.return_value = []

        result = adapter.search("nothing", user_id="alice")

        assert result == {"results": []}

    def test_search_filters_by_tags(self, adapter, mock_editor):
        mock_editor.search.return_value = [
            NemoMemoryItem(
                memory="Work meeting",
                user_id="alice",
                tags=["work", "meeting"],
                metadata={"id": "mem_1"},
            ),
            NemoMemoryItem(
                memory="Personal note",
                user_id="alice",
                tags=["personal"],
                metadata={"id": "mem_2"},
            ),
        ]

        result = adapter.search("note", user_id="alice", tags=["work"])

        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == "Work meeting"

    def test_search_filters_by_topic_category(self, adapter, mock_editor):
        mock_editor.search.return_value = [
            NemoMemoryItem(
                memory="Work stuff",
                user_id="alice",
                metadata={"id": "mem_1", "topic_category": "work"},
            ),
            NemoMemoryItem(
                memory="Fun stuff",
                user_id="alice",
                metadata={"id": "mem_2", "topic_category": "personal"},
            ),
        ]

        result = adapter.search("stuff", user_id="alice", topic_category="work")

        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == "Work stuff"


class TestNemoMemoryAdapterDelete:
    def test_delete_by_id(self, adapter, mock_editor):
        result = adapter.delete("mem_123")

        assert result["success"] is True
        mock_editor.remove_items.assert_called_once_with(memory_id="mem_123")

    def test_delete_all_by_user(self, adapter, mock_editor):
        result = adapter.delete_all(user_id="alice")

        assert result["success"] is True
        mock_editor.remove_items.assert_called_once_with(user_id="alice")


class TestNemoMemoryAdapterGetAll:
    def test_get_all_delegates_to_search(self, adapter, mock_editor):
        mock_editor.search.return_value = [
            NemoMemoryItem(
                memory="Memory 1",
                user_id="alice",
                metadata={"id": "mem_1"},
            ),
        ]

        result = adapter.get_all(user_id="alice")

        assert len(result["results"]) == 1
        mock_editor.search.assert_called_once_with(
            "", top_k=100, user_id="alice"
        )

    def test_get_all_with_offset(self, adapter, mock_editor):
        mock_editor.search.return_value = [
            NemoMemoryItem(
                memory=f"Memory {i}",
                user_id="alice",
                metadata={"id": f"mem_{i}"},
            )
            for i in range(5)
        ]

        result = adapter.get_all(user_id="alice", offset=2, limit=2)

        assert len(result["results"]) == 2


class TestNemoMemoryAdapterMisc:
    def test_get_stats(self, adapter):
        stats = adapter.get_stats()
        assert stats["provider"] == "nemo_mem0"
        assert stats["status"] == "active"

    def test_health_check(self, adapter):
        health = adapter.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "nemo_mem0"

    def test_close(self, adapter):
        adapter.close()

    def test_context_manager(self, adapter):
        with adapter as mem:
            assert mem is adapter


class TestNemoMemoryConfig:
    def test_config_creation(self):
        from selfmemory.configs.nemo import NemoMemoryConfig

        config = NemoMemoryConfig(
            provider="redis",
            config={"host": "localhost", "port": 6379},
        )
        assert config.provider == "redis"
        assert config.config["host"] == "localhost"

    def test_config_api_key_from_config(self):
        from selfmemory.configs.nemo import NemoMemoryConfig

        config = NemoMemoryConfig(
            provider="mem0",
            config={"api_key": "test-key"},
        )
        assert config.api_key == "test-key"

    def test_config_api_key_from_env(self, monkeypatch):
        from selfmemory.configs.nemo import NemoMemoryConfig

        monkeypatch.setenv("NEMO_MEMORY_API_KEY", "env-key")
        config = NemoMemoryConfig(provider="mem0", config={})
        assert config.api_key == "env-key"

    def test_config_host_from_config(self):
        from selfmemory.configs.nemo import NemoMemoryConfig

        config = NemoMemoryConfig(
            provider="redis",
            config={"host": "redis.example.com"},
        )
        assert config.host == "redis.example.com"


class TestMemoryFactory:
    def test_create_nemo_mem0(self):
        with patch(
            "selfmemory.memory.nemo_adapter._build_nemo_editor",
            return_value=AsyncMock(),
        ), patch(
            "selfmemory.memory.nemo_adapter._get_memory_item_class",
            return_value=NemoMemoryItem,
        ):
            from selfmemory.utils.factory import MemoryFactory

            config = {"api_key": "test-key"}
            adapter = MemoryFactory.create("nemo_mem0", config)

            assert adapter is not None
            assert adapter._config.provider == "mem0"

    def test_create_unsupported_provider(self):
        from selfmemory.utils.factory import MemoryFactory

        with pytest.raises(ValueError, match="Unsupported memory provider"):
            MemoryFactory.create("nonexistent", {})

    def test_get_supported_providers(self):
        from selfmemory.utils.factory import MemoryFactory

        providers = MemoryFactory.get_supported_providers()
        assert "nemo_mem0" in providers
        assert "nemo_redis" in providers
        assert "nemo_zep" in providers


class TestExtractContent:
    def test_extract_from_string(self):
        assert NemoMemoryAdapter._extract_content("hello") == "hello"

    def test_extract_from_dict(self):
        msg = {"role": "user", "content": "hello"}
        assert NemoMemoryAdapter._extract_content(msg) == "hello"

    def test_extract_from_list(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        assert NemoMemoryAdapter._extract_content(msgs) == "hello"

    def test_extract_from_list_no_user_role(self):
        msgs = [{"role": "system", "content": "system prompt"}]
        assert NemoMemoryAdapter._extract_content(msgs) == "system prompt"
