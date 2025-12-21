"""
Server-specific OpenTelemetry initialization.
Handles FastAPI, MongoDB, and HTTP client auto-instrumentation.
"""

import logging

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor

from selfmemory.utils.telemetry_otel import setup_opentelemetry

from .config import config

logger = logging.getLogger(__name__)


def initialize_telemetry(app) -> None:
    """
    Initialize OpenTelemetry for the server (production only).

    This function:
    1. Sets up core OpenTelemetry (traces, metrics, logs)
    2. Auto-instruments FastAPI (HTTP requests/responses)
    3. Auto-instruments pymongo (database queries)
    4. Auto-instruments httpx (external HTTP calls)

    Args:
        app: FastAPI application instance
    """
    # Only initialize in production
    if config.app.ENVIRONMENT != "production":
        logger.info(
            f"🔭 OpenTelemetry disabled (environment={config.app.ENVIRONMENT}, production only)"
        )
        return

    # Check if OpenTelemetry is enabled
    if not config.otel.ENABLED:
        logger.info("🔭 OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    logger.info("🔭 Initializing OpenTelemetry for production environment...")

    # Setup core OpenTelemetry (traces, metrics, logs)
    setup_opentelemetry(
        service_name=config.otel.SERVICE_NAME,
        otlp_endpoint=config.otel.OTLP_ENDPOINT,
        environment=config.app.ENVIRONMENT,
    )

    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    logger.info("✅ FastAPI auto-instrumentation enabled")

    # Auto-instrument pymongo (MongoDB)
    PymongoInstrumentor().instrument()
    logger.info("✅ PyMongo auto-instrumentation enabled")

    # Auto-instrument httpx (HTTP client)
    HTTPXClientInstrumentor().instrument()
    logger.info("✅ HTTPX auto-instrumentation enabled")

    logger.info(
        f"🚀 OpenTelemetry fully initialized - sending to {config.otel.OTLP_ENDPOINT}"
    )
