"""
Retry utilities with exponential backoff for Kratos API calls.

Implements resilient API communication patterns to handle transient failures.
"""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from ory_kratos_client.exceptions import ApiException

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_exponential_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> T:
    """
    Retry a function with exponential backoff on transient failures.
    
    Only retries on network errors and 5xx server errors.
    Does NOT retry on authentication errors (401, 403) or client errors (4xx).
    
    Args:
        func: Function to retry (should be a callable with no arguments)
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 10.0)
        
    Returns:
        Result of the function call
        
    Raises:
        Exception: Re-raises the last exception if all retries exhausted
        
    Example:
        ```python
        def fetch_session():
            return frontend_api.to_session()
        
        session = retry_with_exponential_backoff(fetch_session)
        ```
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except ApiException as e:
            last_exception = e

            # Don't retry on client errors (4xx) - these are permanent failures
            if 400 <= e.status < 500:
                logger.warning(
                    f"API call failed with client error {e.status}, not retrying: {e.reason}"
                )
                raise

            # Retry on server errors (5xx) or network issues
            if attempt < max_retries - 1:
                # Calculate exponential backoff: min(base_delay * 2^attempt, max_delay)
                delay = min(base_delay * (2 ** attempt), max_delay)

                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay}s: {e.reason}"
                )

                time.sleep(delay)
            else:
                logger.error(
                    f"API call failed after {max_retries} attempts: {e.reason}"
                )
        except Exception as e:
            last_exception = e

            # For other exceptions, retry if it looks like a network error
            if _is_network_error(e):
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"Network error (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay}s: {str(e)}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Network error after {max_retries} attempts: {str(e)}"
                    )
            else:
                # Unknown error - don't retry
                logger.error(f"Unexpected error, not retrying: {str(e)}")
                raise

    # All retries exhausted - raise the last exception
    raise last_exception


def _is_network_error(exception: Exception) -> bool:
    """
    Check if exception is a network-related error.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if exception indicates a network error
    """
    error_message = str(exception).lower()

    network_keywords = [
        'connection',
        'timeout',
        'network',
        'unreachable',
        'refused',
        'reset',
        'dns',
    ]

    return any(keyword in error_message for keyword in network_keywords)
