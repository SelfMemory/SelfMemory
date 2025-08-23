import logging

from pydantic import BaseModel

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    raise ImportError(
        "The 'chromadb' library is required. Please install it using 'pip install chromadb'."
    ) from None

from inmemory.config.config import InMemoryConfig
from inmemory.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: str | None  # memory id
    score: float | None  # distance
    payload: dict | None  # metadata


class ChromaDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        config: InMemoryConfig | None = None,
        client: chromadb.Client | None = None,
        host: str | None = None,
        port: int | None = None,
        path: str | None = None,
    ):
        """
        Initialize the Chromadb vector store.

        Args:
            collection_name (str): Name of the collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            config (Optional[InMemoryConfig]): Configuration object
            client (chromadb.Client, optional): Existing chromadb client instance. Defaults to None.
            host (str, optional): Host address for chromadb server. Defaults to None.
            port (int, optional): Port for chromadb server. Defaults to None.
            path (str, optional): Path for local chromadb database. Defaults to None.
        """
        self.config = config or InMemoryConfig()

        if client:
            self.client = client
        else:
            self.settings = Settings(anonymized_telemetry=False)

            # Use config values or fallback to parameters
            chroma_host = host or getattr(self.config, "chroma_host", None)
            chroma_port = port or getattr(self.config, "chroma_port", None)
            chroma_path = path or getattr(self.config, "chroma_path", None)

            if chroma_host and chroma_port:
                self.settings.chroma_server_host = chroma_host
                self.settings.chroma_server_http_port = chroma_port
                self.settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
            else:
                if chroma_path is None:
                    chroma_path = "/tmp/chroma_db"

            self.settings.persist_directory = chroma_path
            self.settings.is_persistent = True

            self.client = chromadb.Client(self.settings)

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.collection = self.create_col(collection_name)

    def _parse_output(self, data: dict) -> list[OutputData]:
        """
        Parse the output data.

        Args:
            data (Dict): Output data.

        Returns:
            List[OutputData]: Parsed output data.
        """
        keys = ["ids", "distances", "metadatas"]
        values = []

        for key in keys:
            value = data.get(key, [])
            if isinstance(value, list) and value and isinstance(value[0], list):
                value = value[0]
            values.append(value)

        ids, distances, metadatas = values
        max_length = max(
            len(v) for v in values if isinstance(v, list) and v is not None
        )

        result = []
        for i in range(max_length):
            entry = OutputData(
                id=ids[i] if isinstance(ids, list) and ids and i < len(ids) else None,
                score=(
                    distances[i]
                    if isinstance(distances, list) and distances and i < len(distances)
                    else None
                ),
                payload=(
                    metadatas[i]
                    if isinstance(metadatas, list) and metadatas and i < len(metadatas)
                    else None
                ),
            )
            result.append(entry)

        return result

    def create_col(
        self,
        name: str,
        vector_size: int = None,
        distance: str = None,
        embedding_fn: callable | None = None,
    ):
        """
        Create a new collection.

        Args:
            name (str): Name of the collection.
            vector_size (int): Not used by ChromaDB but kept for interface compatibility
            distance (str): Not used by ChromaDB but kept for interface compatibility
            embedding_fn (Optional[callable]): Embedding function to use. Defaults to None.

        Returns:
            chromadb.Collection: The created or retrieved collection.
        """
        collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
        )
        return collection

    def insert(
        self,
        vectors: list[list],
        payloads: list[dict] | None = None,
        ids: list[str] | None = None,
    ):
        """
        Insert vectors into a collection.

        Args:
            vectors (List[list]): List of vectors to insert.
            payloads (Optional[List[Dict]], optional): List of payloads corresponding to vectors. Defaults to None.
            ids (Optional[List[str]], optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(
            f"Inserting {len(vectors)} vectors into collection {self.collection_name}"
        )
        self.collection.add(ids=ids, embeddings=vectors, metadatas=payloads)

    def search(
        self,
        query: str,
        vectors: list[list],
        limit: int = 5,
        filters: dict | None = None,
    ) -> list[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (List[list]): List of vectors to search.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Optional[Dict], optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results.
        """
        where_clause = self._generate_where_clause(filters) if filters else None
        results = self.collection.query(
            query_embeddings=vectors, where=where_clause, n_results=limit
        )
        final_results = self._parse_output(results)
        return final_results

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.collection.delete(ids=vector_id)

    def update(
        self,
        vector_id: str,
        vector: list[float] | None = None,
        payload: dict | None = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (Optional[List[float]], optional): Updated vector. Defaults to None.
            payload (Optional[Dict], optional): Updated payload. Defaults to None.
        """
        self.collection.update(ids=vector_id, embeddings=vector, metadatas=payload)

    def get(self, vector_id: str) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        result = self.collection.get(ids=[vector_id])
        return self._parse_output(result)[0]

    def list_cols(self) -> list[chromadb.Collection]:
        """
        List all collections.

        Returns:
            List[chromadb.Collection]: List of collections.
        """
        return self.client.list_collections()

    def delete_col(self):
        """
        Delete a collection.
        """
        self.client.delete_collection(name=self.collection_name)

    def col_info(self) -> dict:
        """
        Get information about a collection.

        Returns:
            Dict: Collection information.
        """
        return self.client.get_collection(name=self.collection_name)

    def list(self, filters: dict | None = None, limit: int = 100) -> list[OutputData]:
        """
        List all vectors in a collection.

        Args:
            filters (Optional[Dict], optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        where_clause = self._generate_where_clause(filters) if filters else None
        results = self.collection.get(where=where_clause, limit=limit)
        return [self._parse_output(results)]

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.collection = self.create_col(self.collection_name)

    @staticmethod
    def _generate_where_clause(where: dict[str, any]) -> dict[str, any]:
        """
        Generate a properly formatted where clause for ChromaDB.

        Args:
            where (dict[str, any]): The filter conditions.

        Returns:
            dict[str, any]: Properly formatted where clause for ChromaDB.
        """
        # If only one filter is supplied, return it as is
        # (no need to wrap in $and based on chroma docs)
        if where is None:
            return {}
        if len(where.keys()) <= 1:
            return where
        where_filters = []
        for k, v in where.items():
            if isinstance(v, str):
                where_filters.append({k: v})
        return {"$and": where_filters}
