from typing import Annotated
from qdrant_db import client
from generate_embeddings import get_only_embeddings
from qdrant_client.models import PointStruct
from constants import VectorConstants

def get_memorys(user_memory: str,
                keyword_to_filter: str = None) -> str:
    vector = get_only_embeddings(user_memory.strip())
    search_result = client.query_points(
    collection_name=VectorConstants.COLLECTION_NAME,
    query=vector,
    limit=3,
    with_payload=[keyword_to_filter],
    ).points
    a = []
    for point in search_result:
        point.payload['memory']
        a.append(point.payload['memory'])
        
    return a

if __name__ == "__main__":
    user_memory = "This is a test memory."
    result = get_memorys(user_memory)
    print(result)  # Output the result of adding memory