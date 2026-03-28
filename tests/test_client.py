"""Tests for SelfMemoryClient with mocked HTTP responses."""

from unittest.mock import MagicMock

import pytest

from selfmemory.client.main import SelfMemoryClient


@pytest.fixture
def mock_http_client():
    return MagicMock()


@pytest.fixture
def client(mock_http_client):
    return SelfMemoryClient(
        api_key="sk_im_test_key_12345",
        host="http://localhost:8081",
        client=mock_http_client,
    )


class TestClientInit:
    def test_requires_auth(self):
        with pytest.raises(ValueError, match="Authentication required"):
            SelfMemoryClient(host="http://localhost:8081")

    def test_requires_host(self):
        with pytest.raises(ValueError, match="Host is required"):
            SelfMemoryClient(api_key="sk_im_test")

    def test_sets_bearer_header(self, mock_http_client):
        SelfMemoryClient(
            api_key="sk_im_test_key",
            host="http://localhost:8081",
            client=mock_http_client,
        )
        headers = mock_http_client.headers.update.call_args[0][0]
        assert headers["Authorization"] == "Bearer sk_im_test_key"

    def test_prefers_oauth_token(self, mock_http_client):
        SelfMemoryClient(
            api_key="sk_im_legacy",
            oauth_token="oauth_token_123",
            host="http://localhost:8081",
            client=mock_http_client,
        )
        headers = mock_http_client.headers.update.call_args[0][0]
        assert headers["Authorization"] == "Bearer oauth_token_123"


class TestClientAdd:
    def test_sends_messages_format(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "memory_id": "abc-123"}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        result = client.add("I have a BMW bike.")

        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "/api/memories"

        payload = call_args[1]["json"]
        assert "messages" in payload
        assert payload["messages"] == [
            {"role": "user", "content": "I have a BMW bike."}
        ]
        assert "memory_content" not in payload
        assert result["success"] is True

    def test_accepts_structured_messages(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "memory_id": "abc-123"}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        messages = [
            {"role": "user", "content": "Remember that Alice likes oolong tea."},
            {"role": "assistant", "content": "Saved."},
        ]

        client.add(messages)

        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["messages"] == messages

    def test_sends_metadata(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.add(
            "Meeting notes",
            tags="work,meeting",
            people_mentioned="Sarah",
            topic_category="business",
        )

        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["metadata"]["tags"] == "work,meeting"
        assert payload["metadata"]["people_mentioned"] == "Sarah"
        assert payload["metadata"]["topic_category"] == "business"

    def test_merges_custom_metadata(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.add("Note", metadata={"custom_key": "custom_value"})

        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["metadata"]["custom_key"] == "custom_value"

    def test_handles_http_error(self, client, mock_http_client):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"detail": "Validation error"}
        mock_http_client.post.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "422", request=MagicMock(), response=mock_response
        )

        result = client.add("Test")
        assert result["success"] is False


class TestClientSearch:
    def test_sends_query(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.search("bike")

        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "/api/memories/search"
        payload = call_args[1]["json"]
        assert payload["query"] == "bike"

    def test_sends_filters(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.search("food", tags=["work", "meeting"], threshold=0.8)

        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["filters"]["tags"] == ["work", "meeting"]
        assert payload["filters"]["threshold"] == 0.8

    def test_default_limit_not_sent(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.search("test")

        payload = mock_http_client.post.call_args[1]["json"]
        assert "filters" not in payload or "limit" not in payload.get("filters", {})

    def test_custom_limit_sent(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.search("test", limit=5)

        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["filters"]["limit"] == 5

    def test_people_mentioned_joined(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        client.search("meeting", people_mentioned=["Sarah", "Mike"])

        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["people_mentioned"] == "Sarah,Mike"


class TestClientGetAll:
    def test_sends_params(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.get.return_value = mock_response

        client.get_all(limit=50, offset=10)

        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == "/api/memories"
        assert call_args[1]["params"] == {"limit": 50, "offset": 10}


class TestClientDelete:
    def test_delete_by_id(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "deleted"}
        mock_response.raise_for_status.return_value = None
        mock_http_client.delete.return_value = mock_response

        client.delete("mem-123")

        mock_http_client.delete.assert_called_once_with("/api/memories/mem-123")

    def test_delete_all(self, client, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": "All memories deleted",
            "deleted_count": 5,
        }
        mock_response.raise_for_status.return_value = None
        mock_http_client.delete.return_value = mock_response

        result = client.delete_all()

        mock_http_client.delete.assert_called_once_with("/api/memories")
        assert result["deleted_count"] == 5


class TestClientContextManager:
    def test_context_manager(self, mock_http_client):
        with SelfMemoryClient(
            api_key="sk_im_test",
            host="http://localhost:8081",
            client=mock_http_client,
        ) as client:
            assert client is not None
        mock_http_client.close.assert_called_once()
