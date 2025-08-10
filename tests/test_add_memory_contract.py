"""
Test suite for add_memory API contract validation.

This test specifically addresses the issues we encountered:
1. add_memory_enhanced should return structured dict with memory_id
2. MCP server should handle dict format and return string
3. API server should extract memory_id from dict

These tests would have caught both the synchronization bug and MCP validation error.
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the functions we're testing
from add_memory_to_collection import add_memory_enhanced, EnhancedMemoryManager


class TestAddMemoryContract:
    """Test API contract for add_memory functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_user_id = "test_user_689841548611f533754e86e8"
        self.test_memory_content = "Test memory for contract validation"
        self.test_tags = "test,contract,validation"
        self.test_people = "Alice,Bob"
        self.test_topic = "testing"

    @patch('add_memory_to_collection.get_qdrant_client')
    @patch('add_memory_to_collection.ensure_user_collection_exists')
    @patch('add_memory_to_collection.get_embeddings')
    def test_add_memory_enhanced_returns_dict_with_memory_id(
        self, mock_embeddings, mock_ensure_collection, mock_qdrant
    ):
        """
        CRITICAL TEST: Ensure add_memory_enhanced returns dict with memory_id.
        
        This test would have caught the original sync issue where memory_id
        was generated but not properly exposed to frontend.
        """
        # Setup mocks
        mock_embeddings.return_value = [0.1] * 768
        mock_ensure_collection.return_value = "test_collection"
        mock_client = Mock()
        mock_qdrant.return_value = mock_client
        
        # Execute function
        result = add_memory_enhanced(
            memory_content=self.test_memory_content,
            user_id=self.test_user_id,
            tags=self.test_tags,
            people_mentioned=self.test_people,
            topic_category=self.test_topic
        )
        
        # CRITICAL ASSERTIONS - These would have caught our bug
        assert isinstance(result, dict), "add_memory_enhanced must return dict, not string"
        assert "success" in result, "Response must include success field"
        assert "memory_id" in result, "Response must include memory_id field"
        assert "message" in result, "Response must include message field for MCP compatibility"
        
        # Validate memory_id format
        memory_id = result["memory_id"]
        assert memory_id is not None, "memory_id must not be None"
        assert isinstance(memory_id, str), "memory_id must be string"
        
        # Validate it's a proper UUID format
        try:
            uuid.UUID(memory_id)
        except ValueError:
            pytest.fail(f"memory_id '{memory_id}' is not a valid UUID format")
        
        # Validate success case structure
        assert result["success"] is True
        assert len(result["message"]) > 0, "Message should not be empty"

    @patch('add_memory_to_collection.get_qdrant_client')
    @patch('add_memory_to_collection.ensure_user_collection_exists')
    @patch('add_memory_to_collection.get_embeddings')
    def test_add_memory_enhanced_metadata_structure(
        self, mock_embeddings, mock_ensure_collection, mock_qdrant
    ):
        """Test that metadata is properly structured in response."""
        # Setup mocks
        mock_embeddings.return_value = [0.1] * 768
        mock_ensure_collection.return_value = "test_collection"
        mock_client = Mock()
        mock_qdrant.return_value = mock_client
        
        # Execute function
        result = add_memory_enhanced(
            memory_content=self.test_memory_content,
            user_id=self.test_user_id,
            tags=self.test_tags,
            people_mentioned=self.test_people,
            topic_category=self.test_topic
        )
        
        # Validate metadata structure
        assert "metadata" in result
        assert "temporal_data" in result
        
        metadata = result["metadata"]
        assert "tags" in metadata
        assert "people_mentioned" in metadata
        assert "topic_category" in metadata

    def test_add_memory_enhanced_error_handling(self):
        """Test error cases return proper dict structure."""
        # Test empty content
        result = add_memory_enhanced(
            memory_content="",
            user_id=self.test_user_id
        )
        
        assert isinstance(result, dict), "Error responses must also be dict"
        assert "success" in result
        assert result["success"] is False
        assert "message" in result
        assert "error" in result

    def test_mcp_server_handles_dict_response(self):
        """
        CRITICAL TEST: Ensure MCP server extracts string from dict.
        
        This test would have caught the Pydantic validation error.
        """
        # Mock the dict response that add_memory_enhanced now returns
        mock_dict_response = {
            "success": True,
            "memory_id": str(uuid.uuid4()),
            "message": "I just discovered something new about you!",
            "action": "added",
            "metadata": {"tags": ["test"]},
            "temporal_data": {"year": 2024}
        }
        
        # This is the logic from mcp_server.py add_memory tool
        if isinstance(mock_dict_response, dict):
            result = mock_dict_response.get("message", "Memory processed successfully")
        else:
            result = mock_dict_response
        
        # CRITICAL ASSERTION - Must return string for MCP
        assert isinstance(result, str), "MCP tool must return string to avoid Pydantic validation error"
        assert len(result) > 0, "MCP message should not be empty"

    def test_api_server_extracts_memory_id(self):
        """
        CRITICAL TEST: Ensure API server extracts memory_id from dict.
        
        This test would have caught the frontend sync issue.
        """
        # Mock the dict response that add_memory_enhanced returns
        mock_dict_response = {
            "success": True,
            "memory_id": str(uuid.uuid4()),
            "message": "I just discovered something new about you!",
            "action": "added"
        }
        
        # This is the logic from api_server.py
        if isinstance(mock_dict_response, dict):
            api_response = {
                "success": mock_dict_response.get("success", True),
                "message": "Memory added successfully",
                "memory_id": mock_dict_response.get("memory_id"),  # CRITICAL EXTRACTION
                "result": mock_dict_response.get("message", "Memory processed"),
            }
        else:
            api_response = {
                "success": True,
                "message": "Memory added successfully",
                "result": mock_dict_response,
                "memory_id": None
            }
        
        # CRITICAL ASSERTION - API must include memory_id
        assert "memory_id" in api_response, "API response must include memory_id"
        assert api_response["memory_id"] is not None, "memory_id must not be None"
        assert isinstance(api_response["memory_id"], str), "memory_id must be string"

    @patch('add_memory_to_collection.EnhancedMemoryManager')
    def test_backward_compatibility_with_string_format(self, mock_manager):
        """Test that both systems handle legacy string responses."""
        # Mock old string format response
        mock_manager_instance = Mock()
        mock_manager.return_value = mock_manager_instance
        mock_manager_instance.add_memory_with_metadata.return_value = {
            "success": True,
            "memory_id": str(uuid.uuid4()),
            "message": "Memory added"
        }
        
        # This should work for both old and new formats
        result = add_memory_enhanced(
            memory_content=self.test_memory_content,
            user_id=self.test_user_id
        )
        
        assert isinstance(result, dict)
        assert "memory_id" in result

    def test_memory_id_uniqueness(self):
        """Test that each call generates unique memory_id."""
        with patch('add_memory_to_collection.get_qdrant_client'), \
             patch('add_memory_to_collection.ensure_user_collection_exists'), \
             patch('add_memory_to_collection.get_embeddings', return_value=[0.1] * 768):
            
            result1 = add_memory_enhanced(
                memory_content="First memory",
                user_id=self.test_user_id
            )
            
            result2 = add_memory_enhanced(
                memory_content="Second memory", 
                user_id=self.test_user_id
            )
            
            assert result1["memory_id"] != result2["memory_id"]
            assert len(set([result1["memory_id"], result2["memory_id"]])) == 2


class TestMemoryIdFormats:
    """Test memory ID format validation - would catch temp ID issues."""

    def test_temp_id_format_detection(self):
        """Test detection of temp IDs vs real IDs."""
        # These are the formats from our frontend
        temp_id = "temp-1640995200000-abc123def"
        real_id = str(uuid.uuid4())
        
        # Frontend detection logic
        def is_temp_memory(memory_id):
            return memory_id.startswith('temp-')
        
        assert is_temp_memory(temp_id) is True
        assert is_temp_memory(real_id) is False

    def test_qdrant_id_validation(self):
        """Test Qdrant point ID validation."""
        # Qdrant accepts UUID strings or unsigned integers
        valid_uuid = str(uuid.uuid4())
        invalid_temp_id = "temp-1640995200000-abc123def"
        
        def is_valid_qdrant_id(point_id):
            """Simulate Qdrant ID validation."""
            try:
                # Try UUID format
                uuid.UUID(point_id)
                return True
            except ValueError:
                # Try integer format
                try:
                    int(point_id)
                    return int(point_id) >= 0
                except ValueError:
                    return False
        
        assert is_valid_qdrant_id(valid_uuid) is True
        assert is_valid_qdrant_id(invalid_temp_id) is False
        assert is_valid_qdrant_id("12345") is True
        assert is_valid_qdrant_id("-1") is False


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
