import logging
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from retrieve_memory_from_collection import retrieve_memories, search_memories_with_filter
from add_memory_to_collection import add_memory as add_memory_func

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mcp = FastMCP("usermemory", dependencies=["qdrant-client", "ollama"])

@mcp.tool()
def add_memory(
    user_memory: Annotated[str, "Text or memory to add to the collection"]
) -> str:
    """
    Add text or memory to the collection try to break it down into smaller parts if it's too long and add it seprately. Dont store all the conversation, try to store useful information for the user which can help in future interactions.
    You automatically store user information which you think is important.
    Whenever you needed add memory before, after, inbetween the conversation. 
    
    Args:
        user_memory: The text content to store as memory
        
    Returns:
        Success message string
    """
    try:
        result = add_memory_func(user_memory)
        return result
    except Exception as e:
        logger.error(f"Failed to add memory via MCP: {str(e)}")
        return f"Error: Failed to add memory - {str(e)}"

@mcp.tool()
def retrieve_memory(
    question_to_retrieve_from_memory: Annotated[str, "The user's question to search for relevant memories"],
    keyword_to_filter: Annotated[str, "Optional keyword to narrow down the search results"] = "",
    chunks_to_retrieve: Annotated[int, "Number of chunks to retrieve (default: 5)"] = 5
) -> str:
    """
    Retrieve text or memory from the collection based on a question and optional keyword filter.
    
    Args:
        question_to_retrieve_from_memory: The user's question to search for relevant memories
        keyword_to_filter: Optional keyword to filter results by
        
    Returns:
        Retrieved memory content as a formatted string
    """
    try:
        if keyword_to_filter and keyword_to_filter.strip():
            memories = search_memories_with_filter(
                question_to_retrieve_from_memory,
                keyword_to_filter.strip(),
                limit=chunks_to_retrieve
            )
        else:
            memories = retrieve_memories(question_to_retrieve_from_memory, limit=chunks_to_retrieve)
        
        if not memories:
            return "No relevant memories found."
        
        # Format the response nicely
        if len(memories) == 1:
            return memories[0]
        else:
            formatted_memories = []
            for i, memory in enumerate(memories, 1):
                formatted_memories.append(f"{i}. {memory}")
            return "\n".join(formatted_memories)
            
    except Exception as e:
        logger.error(f"Failed to retrieve memories via MCP: {str(e)}")
        return f"Error: Failed to retrieve memories - {str(e)}"

if __name__ == "__main__":
    logger.info("Starting MCP Memory Server...")
    mcp.run(transport="sse", debug=True)
