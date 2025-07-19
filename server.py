from typing import Annotated
from mcp.server.fastmcp import FastMCP

from retrieve_memory_from_collection import get_memorys
from qdrant_db import client
from add_memory_to_collection import add_memorys


mcp = FastMCP("usermemory", dependencies=["qdrant-client", "ollama"])

@mcp.tool()
def add_memory(
    user_memory: Annotated[str, "Text or memory to add to the collection"]
) -> str:
    """Add text or memory to the collection. You automatically store user information which you think is important."""
    result = add_memorys(user_memory)
    return str(result)

@mcp.tool()
def retrieve_memory(
    question_to_retrieve_from_memory: Annotated[str, "The user's question to search for relevant memories"],
    keyword_to_filter: Annotated[str, "Optional keyword to narrow down the search results"]
) -> str:
    """
    Retrieve text or memory from the collection based on a question and optional keyword filter.
    
    Args:
        question_to_retrieve_from_memory: The user's question to search for relevant memories
    Returns:
        Retrieved memory content as a string
    """

    return str(get_memorys(question_to_retrieve_from_memory, keyword_to_filter=keyword_to_filter))

# Execute and return the stdio output
if __name__ == "__main__":
    mcp.run(transport="sse", debug=True)
