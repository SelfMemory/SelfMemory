"""Logging and OpenTelemetry instrumentation for the MCP server.

This module provides:
1. Environment-based logging (console for dev, file for prod)
2. Optional OpenTelemetry tracing/logging/metrics to SigNoz via shared setup
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from selfmemory.utils.telemetry_otel import setup_opentelemetry


def init_logging() -> None:
    """Initialize logging based on environment.

    - Development: Logs to console (terminal)
    - Production: Logs to rotating file (/var/log/selfmemory-mcp/app.log)

    Always maintains at least a console handler as fallback.
    This runs independently of OpenTelemetry configuration.
    """
    root_logger = logging.getLogger()

    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Set log level
    log_level = (
        logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO
    )
    root_logger.setLevel(log_level)

    # Get environment
    environment = os.getenv("ENVIRONMENT", "development").lower()

    # Common formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Always add console handler as fallback
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Configure logging based on environment
    if environment == "production":
        # Production: Try to add file-based logging
        log_dir = Path(os.getenv("LOG_DIR", "/var/log/selfmemory-mcp"))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "app.log"

            # Rotating file handler (max 10MB, keep 5 backup files)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Add console handler as secondary handler for important logs
            root_logger.addHandler(console_handler)

            print(
                f"Logging: level={logging.getLevelName(log_level)}, handlers=File+Console (fallback)"
            )
            print(f"Log file: {log_file}")
        except Exception as e:
            print(f"Failed to setup file logging: {e}")
            print("Falling back to console logging only")
            # Fallback to console only
            root_logger.addHandler(console_handler)
    else:
        # Development: Console logging
        root_logger.addHandler(console_handler)

        print(f"Logging: level={logging.getLevelName(log_level)}, handler=Console")


def init_telemetry(service_name: str = "selfmemory-mcp") -> trace.Tracer | None:
    """Initialize OpenTelemetry with SigNoz exporter.

    Delegates to the shared setup_opentelemetry() for traces, metrics, logs,
    and log-trace correlation. Adds FastAPI and HTTPX auto-instrumentation.

    Args:
        service_name: Name of the service for SigNoz

    Returns:
        Tracer instance or None if telemetry is disabled
    """
    telemetry_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if not telemetry_enabled:
        return None

    if not otlp_endpoint:
        print(
            "OTEL_ENABLED=true but OTEL_EXPORTER_OTLP_ENDPOINT not set. "
            "Telemetry disabled. Set endpoint to enable (e.g., http://localhost:4317)"
        )
        return None

    try:
        environment = os.getenv("ENVIRONMENT", "development")

        # Shared OTEL setup: traces (BatchSpanProcessor), metrics, logs, LoggingInstrumentor
        setup_opentelemetry(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            environment=environment,
        )

        # Auto-instrument FastAPI and HTTPX
        FastAPIInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        tracer = trace.get_tracer(__name__)
        print(
            f"OpenTelemetry initialized: service={service_name}, endpoint={otlp_endpoint}"
        )
        return tracer

    except Exception as e:
        print(f"Failed to initialize OpenTelemetry: {e}")
        return None


def get_tracer() -> trace.Tracer | None:
    """Get current tracer instance (returns None if not initialized)."""
    try:
        return trace.get_tracer(__name__)
    except Exception:
        return None
