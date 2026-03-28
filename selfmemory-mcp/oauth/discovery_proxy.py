"""OAuth/OIDC Discovery Proxy for Hydra.

Proxies OAuth 2.0 Authorization Server Metadata (RFC 8414) and
OpenID Connect Discovery to Hydra, injecting the Dynamic Client
Registration endpoint.
"""

import json
import logging

import httpx
from fastapi import Request, Response

from config import config

logger = logging.getLogger(__name__)


async def proxy_discovery_metadata(request: Request) -> Response:
    """Proxy OIDC/OAuth discovery metadata from Hydra and inject DCR endpoint.

    Fetches Hydra's openid-configuration, injects our registration_endpoint,
    and returns the enriched metadata. Used by both:
    - /.well-known/oauth-authorization-server (RFC 8414)
    - /.well-known/openid-configuration (OIDC Discovery)

    Args:
        request: Incoming FastAPI request (used to derive base URL)

    Returns:
        Response with Hydra metadata + injected registration_endpoint
    """
    hydra_url = f"{config.hydra.public_url}/.well-known/openid-configuration"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(hydra_url, timeout=10.0)
            response.raise_for_status()

            config_data = response.json()

            base_url = f"{request.url.scheme}://{request.url.netloc}"
            config_data["registration_endpoint"] = f"{base_url}/register"

            logger.info(f"Proxied discovery metadata with DCR: {base_url}/register")

            return Response(
                content=json.dumps(config_data),
                status_code=200,
                media_type="application/json",
            )
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch discovery metadata from Hydra: {e}")
        return Response(
            content="Failed to fetch discovery metadata.",
            status_code=502,
            media_type="text/plain",
        )
