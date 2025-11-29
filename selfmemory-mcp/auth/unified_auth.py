"""Unified authentication supporting both OAuth 2.1 and API key methods.

This module provides authentication detection and validation that works with:
1. OAuth 2.1 tokens from Hydra (JWT format)
2. Legacy API keys from SelfMemory dashboard (simple format)

Both authentication methods result in a unified token context structure that
tools can use transparently without knowing which auth method was used.

Performance optimization: Token validation results are cached to avoid
repeated expensive validation calls (OAuth: 5 min TTL, API keys: 10 min TTL).
"""

import logging
import time
from typing import Literal

from opentelemetry import trace

from server.auth.hydra_validator import HydraToken, validate_token

from .token_cache import (
    get_api_key_from_cache,
    get_oauth_token_from_cache,
    set_api_key_in_cache,
    set_oauth_token_in_cache,
)
from .token_extractor import extract_bearer_token

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


# Type for authentication methods
AuthType = Literal["oauth", "api_key"]


class TokenContext:
    """Unified token context from either OAuth or API key authentication."""

    def __init__(
        self,
        auth_type: AuthType,
        user_id: str,
        project_id: str | None,
        organization_id: str | None,
        scopes: list[str],
        raw_token: str,
    ):
        self.auth_type = auth_type
        self.user_id = user_id
        self.project_id = project_id
        self.organization_id = organization_id
        self.scopes = scopes
        self.raw_token = raw_token

    def to_dict(self) -> dict:
        """Convert to dictionary for context storage."""
        return {
            "auth_type": self.auth_type,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "organization_id": self.organization_id,
            "scopes": self.scopes,
            "raw_token": self.raw_token,
        }

    def has_scope(self, scope: str) -> bool:
        """Check if token has required scope."""
        return scope in self.scopes


def looks_like_jwt(token: str) -> bool:
    """Check if token looks like a JWT or opaque OAuth token from Hydra.

    Hydra can issue two types of OAuth tokens:
    1. JWT tokens: header.payload.signature (2 dots) - e.g., eyJhbGc...
    2. Opaque tokens: ory_at_xxx or ory_at__xxx (1 dot) - e.g., ory_at__3uErCkxc...
    
    Both are valid OAuth tokens that should be validated via Hydra introspection.
    API keys typically have a different format (e.g., sk_im_xxx or im_xxx)

    Args:
        token: Token string to check

    Returns:
        True if token appears to be an OAuth token (JWT or opaque), False otherwise
    """
    # Check for JWT format (2 dots)
    if token.count(".") == 2:
        return True
    
    # Check for Hydra opaque token format (starts with ory_at and has 1 dot)
    if token.startswith("ory_at") and token.count(".") == 1:
        return True
    
    return False


def validate_oauth_token(token: str, core_server_host: str) -> TokenContext:
    """Validate OAuth token via Hydra and create token context.

    Checks cache first to avoid expensive Hydra introspection calls.
    Cache TTL: 5 minutes.

    Args:
        token: OAuth token (JWT format)
        core_server_host: Core server URL (not used for OAuth validation)

    Returns:
        TokenContext with OAuth authentication details

    Raises:
        ValueError: If token is invalid or missing required claims
    """
    with tracer.start_as_current_span("validate_oauth_token") as span:
        span_start = time.time()

        # Check cache first
        cached_context = get_oauth_token_from_cache(token)
        if cached_context:
            span.set_attribute("cache.hit", True)
            cache_duration = (time.time() - span_start) * 1000
            span.set_attribute("cache.duration_ms", cache_duration)
            logger.info(
                f"✅ OAuth cache HIT: [user and project ID redacted] ({cache_duration:.2f}ms)"
            )
            return TokenContext(
                auth_type=cached_context["auth_type"],
                user_id=cached_context["user_id"],
                project_id=cached_context["project_id"],
                organization_id=cached_context["organization_id"],
                scopes=cached_context["scopes"],
                raw_token=token,
            )

        span.set_attribute("cache.hit", False)
        logger.info("❌ OAuth cache MISS - validating with Hydra")

        try:
            # Validate with Hydra introspection
            with tracer.start_as_current_span("hydra_validate_token"):
                hydra_token: HydraToken = validate_token(token)

            hydra_duration = time.time() - span_start
            span.set_attribute("hydra.validation_ms", hydra_duration * 1000)

            # Validate project context exists
            if not hydra_token.project_id:
                raise ValueError("OAuth token missing project context")

            logger.info(
                f"✅ OAuth token validated: user={hydra_token.subject}, "
                f"project={hydra_token.project_id}, scopes={hydra_token.scopes}"
            )

            span.set_attribute("auth.user_id", hydra_token.subject)
            span.set_attribute("auth.project_id", hydra_token.project_id or "")
            span.set_attribute("auth.scopes", ",".join(hydra_token.scopes))

            context = TokenContext(
                auth_type="oauth",
                user_id=hydra_token.subject,
                project_id=hydra_token.project_id,
                organization_id=hydra_token.organization_id,
                scopes=hydra_token.scopes,
                raw_token=token,
            )

            # Cache the result
            set_oauth_token_in_cache(token, context.to_dict())

            return context
        except Exception as e:
            logger.debug(f"OAuth token validation failed: {e}")
            span.record_exception(e)
            raise ValueError(f"Invalid OAuth token: {e}") from e


def validate_api_key(token: str, core_server_host: str) -> TokenContext:
    """Validate API key via Core server and create token context.

    Checks cache first to avoid expensive Core server API calls.
    Cache TTL: 10 minutes.

    Args:
        token: API key string
        core_server_host: Core server URL for validation

    Returns:
        TokenContext with API key authentication details

    Raises:
        ValueError: If API key is invalid
    """
    with tracer.start_as_current_span("validate_api_key") as span:
        span_start = time.time()

        # Check cache first
        cached_context = get_api_key_from_cache(token)
        if cached_context:
            span.set_attribute("cache.hit", True)
            cache_duration = (time.time() - span_start) * 1000
            span.set_attribute("cache.duration_ms", cache_duration)
            logger.info(f"✅ API KEY CACHE HIT ({cache_duration:.2f}ms)")
            return TokenContext(
                auth_type=cached_context["auth_type"],
                user_id=cached_context["user_id"],
                project_id=cached_context["project_id"],
                organization_id=cached_context["organization_id"],
                scopes=cached_context["scopes"],
                raw_token=token,
            )

        span.set_attribute("cache.hit", False)
        logger.info("❌ API KEY CACHE MISS - validating with Core server")

        try:
            # Validate API key by making a test request to Core server
            import httpx

            # Use /api/v1/ping endpoint to validate API key and get user context
            with tracer.start_as_current_span("api_key_ping_request"):
                response = httpx.get(
                    f"{core_server_host}/api/v1/ping",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )

            api_duration = time.time() - span_start
            span.set_attribute("api_key.validation_ms", api_duration * 1000)
            span.set_attribute("http.status_code", response.status_code)

            if api_duration > 3.0:
                logger.warning(f"⚠️  Slow API key validation: {api_duration:.2f}s")
                span.add_event("slow_api_key_warning", {"threshold_ms": 3000})

            if response.status_code != 200:
                raise ValueError(
                    f"API key validation returned status {response.status_code}"
                )

            user_info = response.json()

            # API keys have full access to memories
            scopes = ["memories:read", "memories:write"]

            logger.info(
                f"✅ API key validated: user={user_info.get('user_id')}, "
                f"project={user_info.get('project_id')}"
            )

            span.set_attribute("auth.user_id", user_info.get("user_id", ""))
            span.set_attribute("auth.project_id", user_info.get("project_id", ""))
            span.set_attribute("auth.scopes", ",".join(scopes))

            context = TokenContext(
                auth_type="api_key",
                user_id=user_info["user_id"],
                project_id=user_info.get("project_id"),
                organization_id=user_info.get("organization_id"),
                scopes=scopes,
                raw_token=token,
            )

            # Cache the result
            set_api_key_in_cache(token, context.to_dict())

            return context
        except httpx.HTTPError as e:
            logger.debug(f"API key validation failed (HTTP error): {e}")
            span.record_exception(e)
            raise ValueError(f"Invalid API key: {e}") from e
        except Exception as e:
            logger.debug(f"API key validation failed: {e}")
            span.record_exception(e)
            raise ValueError(f"Invalid API key: {e}") from e


async def detect_and_validate_auth(
    authorization_header: str,
    core_server_host: str,
) -> TokenContext:
    """Detect authentication method and validate token accordingly.

    This function intelligently detects whether the provided token is:
    1. OAuth token (JWT format) - validates via Hydra
    2. API key (other format) - validates via Core server

    Args:
        authorization_header: Full Authorization header value
        core_server_host: Core server URL for API key validation

    Returns:
        TokenContext with unified authentication details

    Raises:
        ValueError: If authentication fails with both methods
    """
    with tracer.start_as_current_span("detect_and_validate_auth") as span:
        detect_start = time.time()

        # Extract Bearer token
        with tracer.start_as_current_span("extract_bearer_token"):
            token = extract_bearer_token(authorization_header)

        span.set_attribute(
            "token.format_detected", "jwt" if looks_like_jwt(token) else "api_key"
        )

        # Try OAuth validation first if token looks like JWT
        if looks_like_jwt(token):
            try:
                result = validate_oauth_token(token, core_server_host)
                detect_duration = time.time() - detect_start
                span.set_attribute("auth.detection_ms", detect_duration * 1000)
                span.set_attribute("auth.method_detected", "oauth")
                return result
            except ValueError as e:
                logger.debug(f"JWT token validation failed, trying API key: {e}")

        # Try API key validation
        try:
            result = validate_api_key(token, core_server_host)
            detect_duration = time.time() - detect_start
            span.set_attribute("auth.detection_ms", detect_duration * 1000)
            span.set_attribute("auth.method_detected", "api_key")
            return result
        except ValueError as api_error:
            # Both validations failed
            if looks_like_jwt(token):
                error_msg = "Token validation failed for both OAuth and API key"
            else:
                error_msg = f"Invalid API key: {api_error}"

            logger.warning(f"❌ Authentication failed: {error_msg}")
            span.set_attribute("auth.method_detected", "none")
            span.set_attribute("auth.error", error_msg)
            span.record_exception(api_error)
            raise ValueError(error_msg) from None
