import unittest
from unittest.mock import MagicMock, patch

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    PointIdsList,
    PointStruct,
)

from selfmemory.vector_stores.qdrant import Qdrant


class TestQdrant(unittest.TestCase):
    def setUp(self):
        self.client_mock = MagicMock(spec=QdrantClient)
        # Mock the create_col method during initialization to avoid side effects
        with patch.object(Qdrant, "create_col"):
            self.qdrant = Qdrant(
                collection_name="test_collection",
                embedding_model_dims=384,
                client=self.client_mock,
            )
        # Reset the mock after initialization
        self.client_mock.reset_mock()

    def test_init_with_client(self):
        """Test initialization with existing client."""
        client_mock = MagicMock(spec=QdrantClient)
        qdrant = Qdrant(
            collection_name="test_collection",
            embedding_model_dims=384,
            client=client_mock,
        )

        self.assertEqual(qdrant.client, client_mock)
        self.assertEqual(qdrant.collection_name, "test_collection")
        self.assertEqual(qdrant.embedding_model_dims, 384)
        self.assertFalse(qdrant.is_local)

    @patch("selfmemory.vector_stores.qdrant.QdrantClient")
    def test_init_with_host_port(self, mock_client_class):
        """Test initialization with host and port."""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        qdrant = Qdrant(
            collection_name="test_collection",
            embedding_model_dims=384,
            host="localhost",
            port=6333,
        )

        mock_client_class.assert_called_once_with(host="localhost", port=6333)
        self.assertEqual(qdrant.client, mock_client_instance)
        self.assertFalse(qdrant.is_local)

    @patch("selfmemory.vector_stores.qdrant.QdrantClient")
    @patch("selfmemory.vector_stores.qdrant.shutil")
    @patch("selfmemory.vector_stores.qdrant.Path")
    def test_init_with_path_local(self, mock_path, mock_shutil, mock_client_class):
        """Test initialization with local path."""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Mock path operations
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True

        qdrant = Qdrant(
            collection_name="test_collection",
            embedding_model_dims=384,
            path="./test_db",
            on_disk=False,
        )

        # Should remove existing directory when on_disk=False
        mock_shutil.rmtree.assert_called_once_with(mock_path_instance)
        mock_client_class.assert_called_once_with(path="./test_db")
        self.assertTrue(qdrant.is_local)

    def test_create_col_existing_collection(self):
        """Test create_col when collection already exists."""
        # Mock existing collection
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        self.client_mock.get_collections.return_value = MagicMock(
            collections=[mock_collection]
        )

        # Should not create collection if it exists
        self.qdrant.create_col(vector_size=384, on_disk=True)

        self.client_mock.create_collection.assert_not_called()
        self.client_mock.get_collections.assert_called()

    def test_create_col_new_collection(self):
        """Test create_col for new collection."""
        # Mock no existing collections
        self.client_mock.get_collections.return_value = MagicMock(collections=[])

        self.qdrant.create_col(vector_size=384, on_disk=True)

        # Verify create_collection was called with correct parameters
        calls = self.client_mock.create_collection.call_args_list
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["collection_name"], "test_collection")
        self.assertEqual(calls[0][1]["vectors_config"].size, 384)
        self.assertEqual(calls[0][1]["vectors_config"].on_disk, True)

    def test_create_filter_indexes_local(self):
        """Test filter index creation for local Qdrant (should skip)."""
        self.qdrant.is_local = True

        # Reset mock to clear any previous calls
        self.client_mock.reset_mock()

        # Should not create payload indexes for local Qdrant
        self.qdrant._create_filter_indexes()

        self.client_mock.create_payload_index.assert_not_called()

    def test_create_filter_indexes_remote(self):
        """Test filter index creation for remote Qdrant."""
        self.qdrant.is_local = False

        self.qdrant._create_filter_indexes()

        # Should attempt to create indexes for common fields
        self.assertGreater(self.client_mock.create_payload_index.call_count, 0)

    def test_insert(self):
        """Test inserting vectors."""
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payloads = [
            {"user_id": "alice", "data": "test1"},
            {"user_id": "bob", "data": "test2"},
        ]
        ids = ["id-1", "id-2"]

        self.qdrant.insert(vectors=vectors, payloads=payloads, ids=ids)

        self.client_mock.upsert.assert_called_once()
        points = self.client_mock.upsert.call_args[1]["points"]

        self.assertEqual(len(points), 2)
        for point in points:
            self.assertIsInstance(point, PointStruct)

        self.assertEqual(points[0].id, "id-1")
        self.assertEqual(points[0].payload, payloads[0])
        self.assertEqual(points[1].id, "id-2")
        self.assertEqual(points[1].payload, payloads[1])

    def test_insert_without_payloads_and_ids(self):
        """Test inserting vectors without payloads and IDs."""
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        self.qdrant.insert(vectors=vectors)

        self.client_mock.upsert.assert_called_once()
        points = self.client_mock.upsert.call_args[1]["points"]

        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].id, 0)
        self.assertEqual(points[0].payload, {})
        self.assertEqual(points[1].id, 1)
        self.assertEqual(points[1].payload, {})

    def test_create_filter_with_multiple_conditions(self):
        """Test _create_filter with multiple conditions."""
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        result = self.qdrant._create_filter(filters)

        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 3)

        # Check that all conditions are present
        conditions = {cond.key: cond.match.value for cond in result.must}
        self.assertEqual(conditions["user_id"], "alice")
        self.assertEqual(conditions["agent_id"], "agent1")
        self.assertEqual(conditions["run_id"], "run1")

    def test_create_filter_with_range_condition(self):
        """Test _create_filter with range condition."""
        filters = {"user_id": "alice", "count": {"gte": 5, "lte": 10}}
        result = self.qdrant._create_filter(filters)

        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 2)

        # Check range condition
        range_conditions = [
            cond
            for cond in result.must
            if hasattr(cond, "range") and cond.range is not None
        ]
        self.assertEqual(len(range_conditions), 1)
        self.assertEqual(range_conditions[0].key, "count")

        # Check string condition
        string_conditions = [
            cond
            for cond in result.must
            if hasattr(cond, "match") and cond.match is not None
        ]
        self.assertEqual(len(string_conditions), 1)
        self.assertEqual(string_conditions[0].key, "user_id")

    def test_create_filter_empty(self):
        """Test _create_filter with no filters."""
        result = self.qdrant._create_filter(None)
        self.assertIsNone(result)

        result = self.qdrant._create_filter({})
        self.assertIsNone(result)

    def test_search_without_filters(self):
        """Test search without filters."""
        vectors = [[0.1, 0.2, 0.3]]
        mock_point = MagicMock(id="test-id", score=0.95, payload={"user_id": "alice"})
        self.client_mock.query_points.return_value = MagicMock(points=[mock_point])

        results = self.qdrant.search(query="test", vectors=vectors, limit=5)

        self.client_mock.query_points.assert_called_once_with(
            collection_name="test_collection",
            query=vectors,
            query_filter=None,
            limit=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "test-id")
        self.assertEqual(results[0].score, 0.95)

    def test_search_with_filters(self):
        """Test search with user isolation filters."""
        vectors = [[0.1, 0.2, 0.3]]
        mock_point = MagicMock(
            id="test-id", score=0.95, payload={"user_id": "alice", "data": "test"}
        )
        self.client_mock.query_points.return_value = MagicMock(points=[mock_point])

        filters = {"user_id": "alice"}
        results = self.qdrant.search(
            query="test", vectors=vectors, limit=5, filters=filters
        )

        # Verify that _create_filter was called and query_filter was passed
        call_args = self.client_mock.query_points.call_args[1]
        self.assertEqual(call_args["collection_name"], "test_collection")
        self.assertEqual(call_args["query"], vectors)
        self.assertEqual(call_args["limit"], 5)

        # Verify that a Filter object was created
        query_filter = call_args["query_filter"]
        self.assertIsInstance(query_filter, Filter)
        self.assertEqual(len(query_filter.must), 1)
        self.assertEqual(query_filter.must[0].key, "user_id")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].payload["user_id"], "alice")

    def test_delete(self):
        """Test deleting a vector."""
        vector_id = "test-id"
        self.qdrant.delete(vector_id=vector_id)

        self.client_mock.delete.assert_called_once_with(
            collection_name="test_collection",
            points_selector=PointIdsList(points=[vector_id]),
        )

    def test_update(self):
        """Test updating a vector."""
        vector_id = "test-id"
        updated_vector = [0.2, 0.3, 0.4]
        updated_payload = {"user_id": "alice", "data": "updated"}

        self.qdrant.update(
            vector_id=vector_id, vector=updated_vector, payload=updated_payload
        )

        self.client_mock.upsert.assert_called_once()
        point = self.client_mock.upsert.call_args[1]["points"][0]
        self.assertEqual(point.id, vector_id)
        self.assertEqual(point.vector, updated_vector)
        self.assertEqual(point.payload, updated_payload)

    def test_get(self):
        """Test retrieving a vector by ID."""
        vector_id = "test-id"
        mock_result = {"id": vector_id, "payload": {"user_id": "alice"}}
        self.client_mock.retrieve.return_value = [mock_result]

        result = self.qdrant.get(vector_id=vector_id)

        self.client_mock.retrieve.assert_called_once_with(
            collection_name="test_collection", ids=[vector_id], with_payload=True
        )
        self.assertEqual(result, mock_result)

    def test_get_not_found(self):
        """Test retrieving a non-existent vector."""
        vector_id = "non-existent"
        self.client_mock.retrieve.return_value = []

        result = self.qdrant.get(vector_id=vector_id)

        self.assertIsNone(result)

    def test_list_cols(self):
        """Test listing collections."""
        mock_collections = MagicMock()
        self.client_mock.get_collections.return_value = mock_collections

        # Reset mock to clear any previous calls
        self.client_mock.reset_mock()
        self.client_mock.get_collections.return_value = mock_collections

        result = self.qdrant.list_cols()

        self.assertEqual(result, mock_collections)
        self.client_mock.get_collections.assert_called_once()

    def test_delete_col(self):
        """Test deleting a collection."""
        self.qdrant.delete_col()
        self.client_mock.delete_collection.assert_called_once_with(
            collection_name="test_collection"
        )

    def test_col_info(self):
        """Test getting collection information."""
        mock_info = {"name": "test_collection", "points_count": 100}
        self.client_mock.get_collection.return_value = mock_info

        result = self.qdrant.col_info()

        self.assertEqual(result, mock_info)
        self.client_mock.get_collection.assert_called_once_with(
            collection_name="test_collection"
        )

    def test_list_without_filters(self):
        """Test listing all vectors without filters."""
        mock_result = [
            MagicMock(id="id-1", payload={"user_id": "alice"}),
            MagicMock(id="id-2", payload={"user_id": "bob"}),
        ]
        self.client_mock.scroll.return_value = mock_result

        results = self.qdrant.list(limit=100)

        self.client_mock.scroll.assert_called_once_with(
            collection_name="test_collection",
            scroll_filter=None,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        self.assertEqual(results, mock_result)

    def test_list_with_filters(self):
        """Test listing vectors with user isolation filters."""
        mock_result = [MagicMock(id="id-1", payload={"user_id": "alice"})]
        self.client_mock.scroll.return_value = mock_result

        filters = {"user_id": "alice"}
        results = self.qdrant.list(filters=filters, limit=50)

        # Verify that _create_filter was called and scroll_filter was passed
        call_args = self.client_mock.scroll.call_args[1]
        self.assertEqual(call_args["collection_name"], "test_collection")
        self.assertEqual(call_args["limit"], 50)

        # Verify that a Filter object was created
        scroll_filter = call_args["scroll_filter"]
        self.assertIsInstance(scroll_filter, Filter)
        self.assertEqual(len(scroll_filter.must), 1)
        self.assertEqual(scroll_filter.must[0].key, "user_id")

        self.assertEqual(results, mock_result)

    def test_count(self):
        """Test getting point count."""
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 42
        self.client_mock.get_collection.return_value = mock_collection_info

        result = self.qdrant.count()

        self.assertEqual(result, 42)
        self.client_mock.get_collection.assert_called_once_with("test_collection")

    def test_count_error(self):
        """Test count with error handling."""
        self.client_mock.get_collection.side_effect = Exception("Connection error")

        result = self.qdrant.count()

        self.assertEqual(result, 0)

    def test_delete_all(self):
        """Test deleting all points."""
        # Mock the reset method
        with patch.object(self.qdrant, "reset") as mock_reset:
            result = self.qdrant.delete_all()

            mock_reset.assert_called_once()
            self.assertTrue(result)

    def test_delete_all_error(self):
        """Test delete_all with error handling."""
        with patch.object(self.qdrant, "reset", side_effect=Exception("Reset failed")):
            result = self.qdrant.delete_all()

            self.assertFalse(result)

    def test_reset(self):
        """Test resetting the collection."""
        with (
            patch.object(self.qdrant, "delete_col") as mock_delete,
            patch.object(self.qdrant, "create_col") as mock_create,
        ):
            self.qdrant.reset()

            mock_delete.assert_called_once()
            mock_create.assert_called_once_with(
                self.qdrant.embedding_model_dims, self.qdrant.on_disk
            )

    def tearDown(self):
        del self.qdrant
