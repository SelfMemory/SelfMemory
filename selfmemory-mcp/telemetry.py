"""OpenTelemetry instrumentation for SigNoz integration.

This module initializes distributed tracing AND logging for the MCP server with SigNoz,
providing detailed performance insights, bottleneck identification, and centralized logs.
"""

import logging
import os

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

        # Configure root logger to ensure INFO level is captured
        root_logger = logging.getLogger()

        # Set root logger level to INFO (or lower if DEBUG is set)
        log_level = (
            logging.DEBUG
            if os.getenv("DEBUG", "false").lower() == "true"
            else logging.INFO
        )
        root_logger.setLevel(log_level)

        # Add OTLP handler to root logger
        root_logger.addHandler(handler)

        print(
            f"✅ Logging configured: level={logging.getLevelName(log_level)}, handler=OTLP"
        )

        # ============================================================
        # INSTRUMENTATION
        # ============================================================

        # Instrument FastAPI and HTTPX automatically
        FastAPIInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        tracer = trace.get_tracer(__name__)
        print(f"✅ OpenTelemetry initialized with SigNoz: {otlp_endpoint}")
        print("✅ Logs will be sent to SigNoz (centralized logging enabled)")
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
