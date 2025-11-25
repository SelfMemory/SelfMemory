"""Logging and OpenTelemetry instrumentation for the MCP server.

This module provides:
1. Environment-based logging (console for dev, file for prod)
2. Optional OpenTelemetry tracing/logging to SigNoz
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


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
                f"✅ Logging: level={logging.getLevelName(log_level)}, handlers=File+Console (fallback)"
            )
            print(f"✅ Log file: {log_file}")
        except Exception as e:
            print(f"⚠️  Failed to setup file logging: {e}")
            print("⚠️  Falling back to console logging only")
            # Fallback to console only
            root_logger.addHandler(console_handler)
    else:
        # Development: Console logging
        root_logger.addHandler(console_handler)

        print(f"✅ Logging: level={logging.getLevelName(log_level)}, handler=Console")


def init_telemetry(service_name: str = "selfmemory-mcp") -> trace.Tracer | None:
    """Initialize OpenTelemetry with SigNoz exporter.

    Args:
        service_name: Name of the service for SigNoz

    Returns:
        Tracer instance or None if telemetry is disabled
    """
    # Check if telemetry is enabled via environment variable
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    telemetry_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"

    if not telemetry_enabled:
        return None

    if not otlp_endpoint:
        print(
            "⚠️  OTEL_ENABLED=true but OTEL_EXPORTER_OTLP_ENDPOINT not set. "
            "Telemetry disabled. Set endpoint to enable (e.g., http://localhost:4317)"
        )
        return None

    try:
        # Create resource with service metadata
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "development"),
            }
        )

        # ============================================================
        # TRACING SETUP
        # ============================================================

        # Create OTLP trace exporter
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            timeout=30,
        )

        # Create tracer provider with SigNoz exporter
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(SimpleSpanProcessor(otlp_trace_exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(tracer_provider)

        # ============================================================
        # LOGGING SETUP (Send logs to SigNoz)
        # ============================================================

        # Create OTLP log exporter
        otlp_log_exporter = OTLPLogExporter(
            endpoint=otlp_endpoint,
            timeout=30,
        )

        # Create logger provider with SigNoz exporter
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(otlp_log_exporter)
        )
        set_logger_provider(logger_provider)

        # Attach OTLP logging handler to root logger
        handler = LoggingHandler(
            level=logging.NOTSET,  # Capture all levels
            logger_provider=logger_provider,
        )

        # Add OTLP logging handler to existing logger setup
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        print("✅ OTLP logging handler added - logs will be sent to SigNoz")
        print(f"✅ SigNoz endpoint: {otlp_endpoint}")

        # ============================================================
        # INSTRUMENTATION
        # ============================================================

        # Instrument FastAPI and HTTPX automatically
        FastAPIInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        tracer = trace.get_tracer(__name__)
        print("✅ OpenTelemetry tracing initialized with SigNoz")
        return tracer

    except Exception as e:
        print(f"❌ Failed to initialize OpenTelemetry: {e}")
        return None


def get_tracer() -> trace.Tracer | None:
    """Get current tracer instance (returns None if not initialized)."""
    try:
        return trace.get_tracer(__name__)
    except Exception:
        return None
