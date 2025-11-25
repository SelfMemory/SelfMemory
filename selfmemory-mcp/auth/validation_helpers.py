"""Helper functions for token validation with caching and telemetry.

This module extracts common patterns from OAuth and API key validation
to follow the DRY principle.
"""

import logging
import time
from typing import Callable, TypeVar, Any

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

T = TypeVar("T")


def validate_with_cache(
    token: str,
    cache_getter: Callable[[str], dict | None],
    cache_setter: Callable[[str, dict], None],
    validator_func: Callable[[str], T],
    operation_name: str,
    context_converter: Callable[[T], dict] | None = None,
) -> T:
    """Generic validation function with caching support.

    Reduces duplication between OAuth and API key validation by providing
    a generic caching wrapper.

    Args:
        token: The token to validate
        cache_getter: Function to retrieve from cache
        cache_setter: Function to store in cache
        validator_func: Function that performs actual validation
        operation_name: Name for logging/tracing (e.g., "oauth_token", "api_key")
        context_converter: Optional function to convert validator result to dict for caching

    Returns:
        Result from validator_func or cache
    """
    with tracer.start_as_current_span(f"validate_{operation_name}") as span:
        span_start = time.time()

        # Check cache first
        cached_context = cache_getter(token)
        if cached_context:
            span.set_attribute("cache.hit", True)
            cache_duration = (time.time() - span_start) * 1000
            span.set_attribute("cache.duration_ms", cache_duration)
            logger.info(
                f"✅ {operation_name.upper()} CACHE HIT: "
                f"user={cached_context.get('user_id')} ({cache_duration:.2f}ms)"
            )
            # If context_converter is provided, convert back from dict
            if context_converter:
                return context_converter(cached_context)
            return cached_context

        span.set_attribute("cache.hit", False)
        logger.info(f"❌ {operation_name.upper()} CACHE MISS - validating")

        try:
            # Validate with provided validator function
            with tracer.start_as_current_span(f"{operation_name}_validator"):
                validation_start = time.time()
                result = validator_func(token)
                validation_duration = time.time() - validation_start

            span.set_attribute(f"{operation_name}.validation_ms", validation_duration * 1000)

            if validation_duration > 3.0:
                logger.warning(f"⚠️  Slow {operation_name} validation: {validation_duration:.2f}s")
                span.add_event(f"slow_{operation_name}_warning", {"threshold_ms": 3000})

            logger.info(
                f"✅ {operation_name} validated successfully in {validation_duration:.2f}s"
            )

            # Cache the result if converter is provided
            if context_converter:
                result_dict = context_converter(result)
            else:
                result_dict = result if isinstance(result, dict) else result.to_dict()

            cache_setter(token, result_dict)

            return result

        except Exception as e:
            logger.debug(f"{operation_name} validation failed: {e}")
            span.record_exception(e)
            raise


def set_token_attributes(
    span: Any,
    user_id: str,
    project_id: str | None,
    auth_type: str,
    scopes: list[str],
) -> None:
    """Set common token attributes on telemetry span.

    Reduces duplication of attribute setting across different validation contexts.

    Args:
        span: OpenTelemetry span object
        user_id: User ID from token
        project_id: Project ID from token
        auth_type: Type of authentication ("oauth" or "api_key")
        scopes: List of scopes granted to token
    """
    span.set_attribute("auth.user_id", user_id)
    span.set_attribute("auth.project_id", project_id or "")
    span.set_attribute("auth.type", auth_type)
    span.set_attribute("auth.scopes", ",".join(scopes))
