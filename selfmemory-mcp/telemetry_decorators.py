"""Telemetry decorators to reduce instrumentation duplication in tools.

This module provides decorators for common telemetry patterns used in MCP tools,
eliminating the need to repeat span wrapping and timing logic.
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def track_tool_execution(tool_name: str, slow_threshold_ms: int = 5000):
    """Decorator to automatically track MCP tool execution with telemetry.

    Wraps tool execution in a span and records:
    - Tool name and execution time
    - Exception details if failures occur
    - Warnings for slow executions

    Args:
        tool_name: Name of the tool being tracked
        slow_threshold_ms: Threshold in milliseconds to warn about slow execution

    Example:
        @track_tool_execution("search", slow_threshold_ms=3000)
        async def search(query: str, ctx: Context) -> dict:
            # implementation
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(f"mcp_tool.{tool_name}") as span:
                span.set_attribute("tool.name", tool_name)
                tool_start = time.time()

                try:
                    logger.info(f"🔧 Executing tool: {tool_name}")
                    result = await func(*args, **kwargs)

                    tool_duration = time.time() - tool_start
                    duration_ms = tool_duration * 1000
                    span.set_attribute("tool.duration_ms", duration_ms)
                    span.set_attribute("tool.status", "success")

                    if duration_ms > slow_threshold_ms:
                        logger.warning(
                            f"⚠️  Slow tool execution ({tool_name}): {tool_duration:.2f}s "
                            f"(threshold: {slow_threshold_ms}ms)"
                        )
                        span.add_event(
                            "slow_tool_warning",
                            {
                                "threshold_ms": slow_threshold_ms,
                                "actual_ms": duration_ms,
                            },
                        )
                    else:
                        logger.info(
                            f"✅ Tool completed ({tool_name}): {tool_duration:.3f}s"
                        )

                    return result

                except Exception as e:
                    tool_duration = time.time() - tool_start
                    span.set_attribute("tool.duration_ms", tool_duration * 1000)
                    span.set_attribute("tool.status", "error")
                    span.record_exception(e)
                    logger.error(f"❌ Tool failed ({tool_name}): {str(e)}")
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(f"mcp_tool.{tool_name}") as span:
                span.set_attribute("tool.name", tool_name)
                tool_start = time.time()

                try:
                    logger.info(f"🔧 Executing tool: {tool_name}")
                    result = func(*args, **kwargs)

                    tool_duration = time.time() - tool_start
                    duration_ms = tool_duration * 1000
                    span.set_attribute("tool.duration_ms", duration_ms)
                    span.set_attribute("tool.status", "success")

                    if duration_ms > slow_threshold_ms:
                        logger.warning(
                            f"⚠️  Slow tool execution ({tool_name}): {tool_duration:.2f}s "
                            f"(threshold: {slow_threshold_ms}ms)"
                        )
                        span.add_event(
                            "slow_tool_warning",
                            {
                                "threshold_ms": slow_threshold_ms,
                                "actual_ms": duration_ms,
                            },
                        )
                    else:
                        logger.info(
                            f"✅ Tool completed ({tool_name}): {tool_duration:.3f}s"
                        )

                    return result

                except Exception as e:
                    tool_duration = time.time() - tool_start
                    span.set_attribute("tool.duration_ms", tool_duration * 1000)
                    span.set_attribute("tool.status", "error")
                    span.record_exception(e)
                    logger.error(f"❌ Tool failed ({tool_name}): {str(e)}")
                    raise

        # Return appropriate wrapper based on whether function is async
        if hasattr(func, "__name__") and "async" in str(func.__code__.co_flags):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def track_operation(operation_name: str, slow_threshold_ms: int = 3000):
    """Decorator to track generic operations with telemetry.

    Lighter-weight than track_tool_execution, useful for helper functions
    and internal operations.

    Args:
        operation_name: Name of the operation
        slow_threshold_ms: Threshold in milliseconds to warn about slow execution
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(f"operation.{operation_name}") as span:
                op_start = time.time()

                try:
                    result = await func(*args, **kwargs)
                    op_duration = time.time() - op_start

                    span.set_attribute("operation.duration_ms", op_duration * 1000)

                    if (op_duration * 1000) > slow_threshold_ms:
                        logger.warning(
                            f"⚠️  Slow operation ({operation_name}): {op_duration:.2f}s"
                        )

                    return result

                except Exception as e:
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(f"operation.{operation_name}") as span:
                op_start = time.time()

                try:
                    result = func(*args, **kwargs)
                    op_duration = time.time() - op_start

                    span.set_attribute("operation.duration_ms", op_duration * 1000)

                    if (op_duration * 1000) > slow_threshold_ms:
                        logger.warning(
                            f"⚠️  Slow operation ({operation_name}): {op_duration:.2f}s"
                        )

                    return result

                except Exception as e:
                    span.record_exception(e)
                    raise

        # Return appropriate wrapper
        if hasattr(func, "__name__") and "async" in str(func.__code__.co_flags):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator
