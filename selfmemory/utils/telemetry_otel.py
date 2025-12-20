"""
OpenTelemetry setup for SigNoz integration.
This module provides centralized OTel configuration for production environments.
"""

import logging
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def setup_opentelemetry(
    service_name: str,
    otlp_endpoint: str,
    environment: str = "production",
    service_version: Optional[str] = None,
    insecure: bool = True,
) -> None:
    """
    Setup OpenTelemetry with OTLP exporters for SigNoz.

    Args:
        service_name: Name of the service (e.g., 'selfmemory-api')
        otlp_endpoint: SigNoz OTLP endpoint (e.g., 'http://192.168.1.41:4317')
        environment: Deployment environment (e.g., 'production', 'staging')
        service_version: Version of the service (optional)
        insecure: Whether to use insecure connection (default: True for development)
    """
    logger.info(
        f"🔭 Initializing OpenTelemetry: service={service_name}, endpoint={otlp_endpoint}, env={environment}"
    )

    # Create resource with service information
    resource_attributes = {
        SERVICE_NAME: service_name,
        "deployment.environment": environment,
    }
    if service_version:
        resource_attributes["service.version"] = service_version

    resource = Resource.create(resource_attributes)

    # Setup Tracing
    trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=insecure)
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    logger.info("✅ OpenTelemetry Tracing configured")

    # Setup Metrics
    metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=insecure)
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    logger.info("✅ OpenTelemetry Metrics configured")

    # Setup Logging instrumentation (auto-correlates logs with traces)
    LoggingInstrumentor().instrument(set_logging_format=True)

    logger.info("✅ OpenTelemetry Logging instrumentation enabled")
    logger.info(f"🚀 OpenTelemetry fully initialized for {service_name}")


def get_tracer(name: str):
    """
    Get a tracer for manual instrumentation.

    Args:
        name: Name of the tracer (typically module name)

    Returns:
        OpenTelemetry tracer instance
    """
    return trace.get_tracer(name)


def get_meter(name: str):
    """
    Get a meter for manual metrics.

    Args:
        name: Name of the meter (typically module name)

    Returns:
        OpenTelemetry meter instance
    """
    return metrics.get_meter(name)
