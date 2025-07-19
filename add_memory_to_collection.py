import random
from qdrant_db import client
from generate_embeddings import get_only_embeddings
from qdrant_client.models import PointStruct
from constants import VectorConstants

def add_memorys(user_memory: str) -> str:
    memory_id = random.randint(1, 1000000)
    print(f"Adding memory with ID: {memory_id}")
    vector = get_only_embeddings(user_memory.strip())
    client.upsert(
        collection_name=VectorConstants.COLLECTION_NAME,
        wait=True,
        points=[
            PointStruct(id=memory_id, vector=vector, payload={"memory": user_memory.strip()})
        ],
    )
    return "Memory added Successfully!"

if __name__ == "__main__":
    user_memory = "This is a test memory."
    result = add_memorys(user_memory)
    print(result)  # Output the result of adding memory