
import sys
from constants import EmbeddingConstants
import ollama

client = ollama.Client()

def generate_embeddings(texts):
    return ollama.embed(
        model=EmbeddingConstants.EMBEDDING_MODEL,
        input=texts,
    )
    
def get_only_embeddings(texts):
    embeddings = generate_embeddings(texts)
    return embeddings['embeddings'][0]

if __name__ == "__main__":
    texts = ["H"]
    embeddings_value = get_only_embeddings(texts)
    print(embeddings_value)
