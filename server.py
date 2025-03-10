import random
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("usermemory", dependencies=["chromadb"])

try:
    from db import collection
    print("Successfully imported ChromaDB collection", file=sys.stderr)
except Exception as e:
    print(f"Error importing collection: {e}", file=sys.stderr)
    # Create a mock collection as fallback
    class MockCollection:
        def add(self, ids, documents):
            return "Error: Database not available - memory not persisted"
        
        def query(self, query_texts, n_results=3):
            return {"documents": [["Error: Database not available - no memories to retrieve"]]}
    
    collection = MockCollection()
    print("Using mock collection as fallback", file=sys.stderr)

@mcp.tool()
def add_memory(user_memory: str) -> str:
    """Add text or memory to the collection. You automatically store user information which you think is important."""
    try:
        if not user_memory or not user_memory.strip():
            return "Error: Cannot add empty memory"
        
        memory_id = str(random.randint(1, 100000))
        result = collection.add(
            ids=[memory_id],
            documents=[user_memory.strip()]
        )
        
        print(f"Added memory with ID {memory_id}: {user_memory[:50]}...", file=sys.stderr)
        return "Added to Memory Successfully!"
    
    except Exception as e:
        error_msg = f"Error adding memory: {str(e)}"
        print(error_msg, file=sys.stderr)
        return error_msg

@mcp.tool()
def retrieve_memory(question_to_retrieve_from_memory: str) -> str:
    """Retrieve text or memory from the collection. It can be personal information, or just a memory of the conversation."""
    # try:
    #     if not llm_memory or not llm_memory.strip():
    #         return "Error: Cannot search with empty query"
        
    results = collection.query(
        query_texts=[question_to_retrieve_from_memory],
        n_results=3
    )
    return results["documents"]
        
    #     if results and "documents" in results and results["documents"]:
    #         documents = results["documents"][0] if results["documents"] else []
    #         if documents:
    #             print(f"Retrieved {len(documents)} memories for query: {llm_memory[:50]}...", file=sys.stderr)
    #             return documents
        
    #     print(f"No memories found for query: {llm_memory[:50]}...", file=sys.stderr)
    #     return ["No Memory Found"]
    
    # except Exception as e:
    #     error_msg = f"Error retrieving memory: {str(e)}"
    #     print(error_msg, file=sys.stderr)
    #     return [error_msg]

# Execute and return the stdio output
if __name__ == "__main__":
    print("Starting MCP server...", file=sys.stderr)
    mcp.run(transport="stdio")
