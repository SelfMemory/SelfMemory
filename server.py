import logging
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from retrieve_memory_from_collection import retrieve_memories, search_memories_with_filter
from add_memory_to_collection import add_memory as add_memory_func, add_memory_enhanced
from src.search.enhanced_search_engine import EnhancedSearchEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mcp = FastMCP("usermemory", dependencies=["qdrant-client", "ollama"])

# Initialize enhanced search engine
search_engine = EnhancedSearchEngine()

# === LEGACY TOOLS (Backward Compatibility) ===

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
    keyword_to_filter: Annotated[str, "Optional: keyword to narrow down the search results. This will act like AND filter."] = "",
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

@mcp.tool()
def add_memory_with_metadata(
    memory_content: Annotated(str, "The memory text to store"),
    tags: Annotated[str, "Comma-separated tags to categorize the memory (e.g., 'work,meeting,project')"] = "",
    people_mentioned: Annotated[str, "Comma-separated names of people mentioned (e.g., 'John,Sarah,Mike')"] = "",
    topic_category: Annotated[str, "Category/topic of the memory (e.g., 'work', 'personal', 'learning')"] = "",
    check_duplicates: Annotated[bool, "Whether to check for similar memories before adding (default: True)"] = True
) -> str:
    """
    Add a memory with rich metadata including tags, people mentioned, topic category, and automatic temporal data.
    Includes duplicate detection to prevent storing similar memories.
    
    Args:
        memory_content: The memory text to store
        tags: Comma-separated tags for categorization
        people_mentioned: Comma-separated names of people mentioned
        topic_category: Category or topic of the memory
        check_duplicates: Whether to check for duplicates before adding
        
    Returns:
        Formatted result with memory ID and metadata details
    """
    try:
        result = add_memory_enhanced(
            memory_content=memory_content,
            tags=tags,
            people_mentioned=people_mentioned,
            topic_category=topic_category,
            check_duplicates=check_duplicates
        )
        return result
    except Exception as e:
        logger.error(f"Failed to add enhanced memory via MCP: {str(e)}")
        return f"❌ Error: Failed to add memory - {str(e)}"

@mcp.tool()
def search_memories_enhanced(
    query: Annotated[str, "Semantic search query to find relevant memories"],
    limit: Annotated[int, "Maximum number of results to return (1-20, default: 5)"] = 5,
    score_threshold: Annotated[float, "Minimum similarity score threshold (0.0-1.0, default: 0.7)"] = 0.7,
    tags: Annotated[str, "Filter by comma-separated tags (e.g., 'work,meeting')"] = "",
    people_mentioned: Annotated[str, "Filter by comma-separated people names (e.g., 'John,Sarah')"] = "",
    topic_category: Annotated[str, "Filter by topic category (e.g., 'work', 'personal')"] = "",
    temporal_filter: Annotated[str, "Temporal filter (e.g., 'yesterday', 'this_week', 'weekends')"] = ""
) -> str:
    """
    Enhanced memory search with comprehensive filtering options including semantic similarity, 
    metadata filtering, and temporal constraints.
    
    Args:
        query: Semantic search query
        limit: Maximum number of results
        score_threshold: Minimum similarity score
        tags: Filter by specific tags
        people_mentioned: Filter by people mentioned
        topic_category: Filter by topic category
        temporal_filter: Time-based filter
        
    Returns:
        Formatted search results with metadata
    """
    try:
        # Parse comma-separated filters
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None
        people_list = [person.strip() for person in people_mentioned.split(",") if person.strip()] if people_mentioned else None
        category = topic_category.strip() if topic_category else None
        temporal = temporal_filter.strip() if temporal_filter else None
        
        results = search_engine.search_memories(
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category,
            temporal_filter=temporal
        )
        
        if not results:
            return "🔍 No memories found matching your search criteria."
        
        # Format results
        formatted_results = [f"🧠 Found {len(results)} memories:\n"]
        
        for i, result in enumerate(results, 1):
            score_emoji = "🎯" if result.get('score', 0) > 0.9 else "✅" if result.get('score', 0) > 0.8 else "📝"
            formatted_results.append(f"{score_emoji} {i}. {result['memory']}")
            
            # Add metadata if available
            metadata_parts = []
            if result.get('tags'):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get('people_mentioned'):
                metadata_parts.append(f"People: {', '.join(result['people_mentioned'])}")
            if result.get('topic_category'):
                metadata_parts.append(f"Topic: {result['topic_category']}")
            if result.get('temporal_data'):
                temporal_data = result['temporal_data']
                if temporal_data.get('day_of_week'):
                    metadata_parts.append(f"Time: {temporal_data.get('day_of_week')}, Q{temporal_data.get('quarter', '?')} {temporal_data.get('year', '?')}")
            
            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")
            
            if result.get('score'):
                formatted_results.append(f"   🎯 Similarity: {result['score']:.3f}")
            
            formatted_results.append("")  # Empty line between results
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Enhanced search failed via MCP: {str(e)}")
        return f"❌ Error: Search failed - {str(e)}"

@mcp.tool()
def temporal_search(
    temporal_query: Annotated[str, "Natural language time query (e.g., 'yesterday', 'this_week', 'weekends', 'q3', 'morning')"],
    semantic_query: Annotated[str, "Optional semantic search query to combine with temporal filter"] = "",
    limit: Annotated[int, "Maximum number of results (1-20, default: 5)"] = 5
) -> str:
    """
    Search memories based on time/temporal criteria with optional semantic filtering.
    
    Supported temporal queries:
    - 'today', 'yesterday'
    - 'this_week', 'weekends', 'weekdays'
    - 'q1', 'q2', 'q3', 'q4' (quarters)
    - 'morning', 'afternoon', 'evening'
    - Day names: 'monday', 'tuesday', etc.
    
    Args:
        temporal_query: Natural language time query
        semantic_query: Optional semantic search to combine
        limit: Maximum number of results
        
    Returns:
        Formatted temporal search results
    """
    try:
        results = search_engine.temporal_search(
            temporal_query=temporal_query,
            semantic_query=semantic_query if semantic_query.strip() else None,
            limit=limit
        )
        
        if not results:
            return f"🕒 No memories found for '{temporal_query}'{f' + \"{semantic_query}\"' if semantic_query else ''}."
        
        # Format results
        formatted_results = [f"🕒 Found {len(results)} memories for '{temporal_query}'{f' + \"{semantic_query}\"' if semantic_query else ''}:\n"]
        
        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")
            
            # Add temporal context
            if result.get('temporal_data'):
                temporal_data = result['temporal_data']
                time_context = []
                if temporal_data.get('day_of_week'):
                    time_context.append(f"{temporal_data['day_of_week'].title()}")
                if temporal_data.get('quarter'):
                    time_context.append(f"Q{temporal_data['quarter']}")
                if temporal_data.get('year'):
                    time_context.append(f"{temporal_data['year']}")
                if temporal_data.get('hour') is not None:
                    hour = temporal_data['hour']
                    time_period = "Morning" if 6 <= hour < 12 else "Afternoon" if 12 <= hour < 18 else "Evening"
                    time_context.append(f"{time_period} ({hour}:00)")
                
                if time_context:
                    formatted_results.append(f"   🕒 {' | '.join(time_context)}")
            
            # Add other metadata
            metadata_parts = []
            if result.get('tags'):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get('topic_category'):
                metadata_parts.append(f"Topic: {result['topic_category']}")
            
            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")
            
            formatted_results.append("")  # Empty line
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Temporal search failed via MCP: {str(e)}")
        return f"❌ Error: Temporal search failed - {str(e)}"

@mcp.tool()
def search_by_tags(
    tags: Annotated[str, "Comma-separated tags to search for (e.g., 'work,meeting,project')"],
    semantic_query: Annotated[str, "Optional semantic search query to combine with tag filtering"] = "",
    match_all_tags: Annotated[bool, "Whether to match ALL tags (AND) or ANY tag (OR). Default: False (OR)"] = False,
    limit: Annotated[int, "Maximum number of results (1-20, default: 5)"] = 5
) -> str:
    """
    Search memories by tags with optional semantic filtering.
    
    Args:
        tags: Comma-separated tags to search for
        semantic_query: Optional semantic search to combine
        match_all_tags: Whether to match all tags (AND) or any tag (OR)
        limit: Maximum number of results
        
    Returns:
        Formatted tag search results
    """
    try:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if not tag_list:
            return "❌ Please provide at least one tag to search for."
        
        results = search_engine.tag_search(
            tags=tag_list,
            semantic_query=semantic_query if semantic_query.strip() else None,
            match_all_tags=match_all_tags,
            limit=limit
        )
        
        if not results:
            match_type = "all" if match_all_tags else "any"
            return f"🏷️ No memories found with {match_type} of these tags: {', '.join(tag_list)}"
        
        # Format results
        match_type = "all" if match_all_tags else "any"
        formatted_results = [f"🏷️ Found {len(results)} memories with {match_type} of: {', '.join(tag_list)}\n"]
        
        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")
            
            # Highlight matching tags
            if result.get('tags'):
                all_tags = result['tags']
                matching_tags = [tag for tag in all_tags if tag in [t.lower() for t in tag_list]]
                other_tags = [tag for tag in all_tags if tag not in matching_tags]
                
                tag_display = []
                if matching_tags:
                    tag_display.append(f"✅ {', '.join(matching_tags)}")
                if other_tags:
                    tag_display.append(f"📋 {', '.join(other_tags)}")
                
                formatted_results.append(f"   🏷️ {' | '.join(tag_display)}")
            
            # Add other metadata
            metadata_parts = []
            if result.get('people_mentioned'):
                metadata_parts.append(f"People: {', '.join(result['people_mentioned'])}")
            if result.get('topic_category'):
                metadata_parts.append(f"Topic: {result['topic_category']}")
            
            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")
            
            formatted_results.append("")  # Empty line
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Tag search failed via MCP: {str(e)}")
        return f"❌ Error: Tag search failed - {str(e)}"

@mcp.tool()
def search_by_people(
    people: Annotated[str, "Comma-separated names of people to search for (e.g., 'John,Sarah,Mike')"],
    semantic_query: Annotated[str, "Optional semantic search query to combine with people filtering"] = "",
    limit: Annotated[int, "Maximum number of results (1-20, default: 5)"] = 5
) -> str:
    """
    Search memories by people mentioned with optional semantic filtering.
    
    Args:
        people: Comma-separated names of people to search for
        semantic_query: Optional semantic search to combine
        limit: Maximum number of results
        
    Returns:
        Formatted people search results
    """
    try:
        people_list = [person.strip() for person in people.split(",") if person.strip()]
        if not people_list:
            return "❌ Please provide at least one person's name to search for."
        
        results = search_engine.people_search(
            people=people_list,
            semantic_query=semantic_query if semantic_query.strip() else None,
            limit=limit
        )
        
        if not results:
            return f"👥 No memories found mentioning: {', '.join(people_list)}"
        
        # Format results
        formatted_results = [f"👥 Found {len(results)} memories mentioning: {', '.join(people_list)}\n"]
        
        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")
            
            # Highlight mentioned people
            if result.get('people_mentioned'):
                all_people = result['people_mentioned']
                matching_people = [person for person in all_people if person in people_list]
                other_people = [person for person in all_people if person not in matching_people]
                
                people_display = []
                if matching_people:
                    people_display.append(f"✅ {', '.join(matching_people)}")
                if other_people:
                    people_display.append(f"👤 {', '.join(other_people)}")
                
                formatted_results.append(f"   👥 {' | '.join(people_display)}")
            
            # Add other metadata
            metadata_parts = []
            if result.get('tags'):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get('topic_category'):
                metadata_parts.append(f"Topic: {result['topic_category']}")
            
            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")
            
            formatted_results.append("")  # Empty line
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"People search failed via MCP: {str(e)}")
        return f"❌ Error: People search failed - {str(e)}"

@mcp.tool()
def search_by_topic(
    topic_category: Annotated[str, "Topic category to search for (e.g., 'work', 'personal', 'learning', 'technology')"],
    semantic_query: Annotated[str, "Optional semantic search query to combine with topic filtering"] = "",
    limit: Annotated[int, "Maximum number of results (1-20, default: 5)"] = 5
) -> str:
    """
    Search memories by topic category with optional semantic filtering.
    
    Args:
        topic_category: Topic category to search for
        semantic_query: Optional semantic search to combine  
        limit: Maximum number of results
        
    Returns:
        Formatted topic search results
    """
    try:
        if not topic_category.strip():
            return "❌ Please provide a topic category to search for."
        
        results = search_engine.topic_search(
            topic_category=topic_category.strip(),
            semantic_query=semantic_query if semantic_query.strip() else None,
            limit=limit
        )
        
        if not results:
            return f"📂 No memories found in topic: '{topic_category}'"
        
        # Format results
        formatted_results = [f"📂 Found {len(results)} memories in topic: '{topic_category}'\n"]
        
        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")
            
            # Add metadata
            metadata_parts = []
            if result.get('tags'):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get('people_mentioned'):
                metadata_parts.append(f"People: {', '.join(result['people_mentioned'])}")
            
            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")
            
            # Add temporal context
            if result.get('temporal_data'):
                temporal_data = result['temporal_data']
                if temporal_data.get('day_of_week'):
                    formatted_results.append(f"   🕒 {temporal_data['day_of_week'].title()}, Q{temporal_data.get('quarter', '?')} {temporal_data.get('year', '?')}")
            
            formatted_results.append("")  # Empty line
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Topic search failed via MCP: {str(e)}")
        return f"❌ Error: Topic search failed - {str(e)}"

if __name__ == "__main__":
    logger.info("Starting Enhanced MCP Memory Server...")
    mcp.run(transport="sse", debug=True)
