"""
Memory API client for chat tool execution

CHAT-202: Implement Memory Search API Client
"""
import httpx
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from server.chat.tools import SearchMemoriesParams

# Module-level configuration
SELFMEMORY_API_URL = os.getenv("SELFMEMORY_API_URL", "http://localhost:8081")
DEFAULT_TIMEOUT = 5.0

logger = logging.getLogger(__name__)


def _prepare_auth_headers(session_cookie: Optional[str]) -> Tuple[dict, dict]:
    """
    Prepare authentication headers and cookies for API requests.
    
    Args:
        session_cookie: Kratos session cookie value
        
    Returns:
        Tuple of (headers, cookies) dictionaries
    """
    headers = {}
    cookies = {}
    if session_cookie:
        # Pass Kratos session cookie in Authorization header (required by authenticate_api_key)
        # Also send as cookie for browser compatibility
        cookies['ory_kratos_session'] = session_cookie
        headers['Authorization'] = f'Session {session_cookie}'
    return headers, cookies


class Memory:
    """Memory data model"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.content = data.get('content', '')
        self.tags = data.get('tags', [])
        self.metadata = data.get('metadata', {})
        self.score = data.get('score', 0.0)
        self.created_at = data.get('created_at', '')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'content': self.content,
            'tags': self.tags,
            'metadata': self.metadata,
            'score': self.score,
            'createdAt': self.created_at
        }


async def search_memories(
    query: str,
    project_id: str,
    user_id: str,
    limit: int = 5,
    session_cookie: str = None
) -> List[Memory]:
    """
    Search for memories using semantic similarity
    
    Args:
        query: Search query string
        project_id: Project ID for multi-tenant isolation
        user_id: User ID for access control
        limit: Maximum number of results (default: 5)
        session_cookie: Kratos session cookie for authentication
    
    Returns:
        List of Memory objects sorted by relevance
    """
    try:
        # Validate query - return empty results for invalid queries
        if not query or not query.strip():
            logger.warning(f"Empty query provided for project {project_id}")
            return []  # Return empty results instead of changing user intent
        
        logger.debug(f"Memory search request: query='{query[:50]}...', project={project_id}, limit={limit}")
        
        # Prepare headers with session cookie for authentication
        headers, cookies = _prepare_auth_headers(session_cookie)
        
        request_payload = {
            "query": query,
            "user_id": project_id,  # Project as session identifier for shared memories
            "filters": {
                "limit": limit
            }
        }
        
        logger.debug(f"Calling memory API: {SELFMEMORY_API_URL}/api/memories/search")
        
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                f"{SELFMEMORY_API_URL}/api/memories/search",
                json=request_payload,
                params={"project_id": project_id},
                headers=headers,
                cookies=cookies
            )
            if response.status_code != 200:
                logger.error(f"Memory API error: status={response.status_code}, body={response.text[:200]}")
                return []  # Graceful degradation
            
            data = response.json()
            results = data.get('results', [])
            memories = [Memory(m) for m in results]
            
            logger.info(f"Memory search completed: found {len(memories)} results for query '{query[:50]}...'")
            if memories:
                logger.debug(f"Top result: score={memories[0].score:.4f}, content='{memories[0].content[:100]}...'")
            
            return memories
            
    except httpx.TimeoutException:
        logger.warning(f"Memory search timeout: query='{query[:50]}...', project={project_id}")
        return []  # Graceful degradation
    except Exception as e:
        logger.error(f"Memory search error: {str(e)}", exc_info=True)
        return []  # Graceful degradation


async def add_memory(
    content: str,
    project_id: str,
    user_id: str,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_cookie: str = None
) -> Optional[Memory]:
    """
    Add a new memory (Phase 3)
    
    Args:
        content: Memory content
        project_id: Project ID for multi-tenant isolation
        user_id: User ID for ownership
        tags: Optional list of tags
        metadata: Optional metadata dictionary
        session_cookie: Kratos session cookie for authentication
    
    Returns:
        Created Memory object or None on failure
    """
    try:
        logger.debug(f"Adding memory: project={project_id}, content_length={len(content)}")
        
        # Prepare metadata
        memory_metadata = metadata or {}
        if tags:
            memory_metadata["tags"] = ",".join(tags) if isinstance(tags, list) else tags
        
        # Prepare headers with session cookie for authentication
        headers, cookies = _prepare_auth_headers(session_cookie)
        
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                f"{SELFMEMORY_API_URL}/api/memories",
                json={
                    "messages": [{"role": "user", "content": content}],
                    "user_id": project_id,  # Project as session identifier
                    "metadata": memory_metadata
                },
                params={"project_id": project_id},
                headers=headers,
                cookies=cookies
            )
            
            if response.status_code != 200:
                logger.error(f"Memory add API error: status={response.status_code}, body={response.text[:200]}")
                return None
            
            data = response.json()
            memory_id = data.get('memory_id')
            if memory_id:
                memory = Memory({
                    'id': memory_id,
                    'content': content,
                    'tags': tags or [],
                    'metadata': memory_metadata,
                    'score': 1.0,
                    'created_at': data.get('created_at', '')
                })
                logger.info(f"Memory created: id={memory.id}, project={project_id}")
                return memory
            
            logger.warning("Memory add response missing memory_id")
            return None
            
    except httpx.TimeoutException:
        logger.warning(f"Memory add timeout: project={project_id}")
        return None
    except Exception as e:
        logger.error(f"Memory add error: {str(e)}", exc_info=True)
        return None
