import logging
import asyncio
from typing import Optional
from urllib.parse import urljoin
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from starlette.background import BackgroundTask
import uvicorn
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app for reverse proxy
app = FastAPI(
    title="InMemory Reverse Proxy",
    version="1.0.0", 
    description="Reverse proxy for Tailscale deployment - routes MCP and Core API"
)

# Backend servers configuration
MCP_SERVER_URL = "http://localhost:8080"
CORE_API_SERVER_URL = "http://localhost:8081"

# HTTP client for making proxy requests
client = httpx.AsyncClient(timeout=30.0)

async def cleanup():
    """Cleanup function to close HTTP client."""
    await client.aclose()

@app.on_event("shutdown")
async def shutdown_event():
    """Handle app shutdown."""
    await cleanup()

async def proxy_request(
    request: Request, 
    target_url: str, 
    path: str = ""
) -> Response:
    """
    Proxy HTTP request to target server.
    
    Args:
        request: Incoming FastAPI request
        target_url: Target server base URL
        path: Additional path to append
        
    Returns:
        Response from target server
    """
    try:
        # Build target URL
        if path:
            url = urljoin(target_url.rstrip('/') + '/', path.lstrip('/'))
        else:
            url = target_url
            
        # Get request body if present
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
        
        # Prepare headers (exclude hop-by-hop headers)
        headers = {}
        for name, value in request.headers.items():
            if name.lower() not in ["host", "connection", "upgrade", "proxy-connection"]:
                headers[name] = value
        
        # Add original host info for debugging
        headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
        headers["X-Forwarded-Proto"] = "https"  # Since coming through Tailscale HTTPS
        headers["X-Original-Path"] = str(request.url.path)
        
        logger.info(f"Proxying {request.method} {request.url.path} → {url}")
        
        # Make the proxy request
        response = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            params=request.query_params,
            content=body,
            follow_redirects=False
        )
        
        # Handle streaming responses (important for SSE)
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            return StreamingResponse(
                response.aiter_bytes(),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="text/event-stream"
            )
        
        # Handle regular responses
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
        
    except httpx.ConnectError as e:
        logger.error(f"Connection error to {target_url}: {e}")
        raise HTTPException(
            status_code=502, 
            detail=f"Backend server unavailable: {target_url}"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error to {target_url}: {e}")
        raise HTTPException(
            status_code=504, 
            detail=f"Backend server timeout: {target_url}"
        )
    except Exception as e:
        logger.error(f"Proxy error to {target_url}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Proxy error: {str(e)}"
        )

@app.api_route("/mcp", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_mcp_root(request: Request):
    """Proxy requests to /mcp to MCP server root."""
    return await proxy_request(request, MCP_SERVER_URL, "/")

@app.api_route("/mcp/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_mcp_path(request: Request, path: str):
    """Proxy requests to /mcp/* to MCP server."""
    return await proxy_request(request, MCP_SERVER_URL, path)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_core_api(request: Request, path: str):
    """Proxy all other requests to Core API server."""
    return await proxy_request(request, CORE_API_SERVER_URL, path)

@app.get("/")
async def proxy_root(request: Request):
    """Proxy root requests to Core API server."""
    return await proxy_request(request, CORE_API_SERVER_URL, "/")

@app.get("/health")
async def health_check():
    """Health check endpoint for the proxy itself."""
    try:
        # Check if backend servers are accessible
        mcp_health = await client.get(f"{MCP_SERVER_URL}/health", timeout=5.0)
        core_health = await client.get(f"{CORE_API_SERVER_URL}/v1/health", timeout=5.0)
        
        return {
            "status": "healthy",
            "service": "InMemory Reverse Proxy",
            "version": "1.0.0",
            "backends": {
                "mcp_server": {
                    "url": MCP_SERVER_URL,
                    "status": "healthy" if mcp_health.status_code == 200 else "unhealthy",
                    "status_code": mcp_health.status_code
                },
                "core_api_server": {
                    "url": CORE_API_SERVER_URL, 
                    "status": "healthy" if core_health.status_code == 200 else "unhealthy",
                    "status_code": core_health.status_code
                }
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "InMemory Reverse Proxy",
            "error": str(e)
        }

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='InMemory Reverse Proxy for Tailscale')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Port to listen on (default: 8000)')
    parser.add_argument('--mcp-url', default='http://localhost:8080', help='MCP server URL')
    parser.add_argument('--core-api-url', default='http://localhost:8081', help='Core API server URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    # Update backend URLs if provided
    MCP_SERVER_URL = args.mcp_url
    CORE_API_SERVER_URL = args.core_api_url

    logger.info("Starting InMemory Reverse Proxy...")
    logger.info(f"Proxy server: http://{args.host}:{args.port}")
    logger.info(f"Routing /mcp/* → {MCP_SERVER_URL}")
    logger.info(f"Routing /* → {CORE_API_SERVER_URL}")
    logger.info(f"Health check: http://{args.host}:{args.port}/health")
    
    # Run the proxy server
    uvicorn.run(
        app, 
        host=args.host, 
        port=args.port, 
        log_level="debug" if args.debug else "info"
    )
