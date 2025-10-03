"""
Health Check System

Provides comprehensive health checks for:
- Database connectivity
- Memory usage
- Disk usage
- SMTP connectivity (if configured)

Following Uncle Bob's Clean Code principles:
- Single responsibility for each check
- Clear, descriptive function names
- No fallback mechanisms (explicit failures)
- Proper error handling and logging
"""

import logging
import smtplib
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from server.config import config
from server.utils.datetime_helpers import utc_now

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Individual health check result."""

    def __init__(
        self,
        name: str,
        status: str,
        latency_ms: float | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.name = name
        self.status = status
        self.latency_ms = latency_ms
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert health check to dictionary."""
        result = {
            "status": self.status,
        }

        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)

        if self.message:
            result["message"] = self.message

        if config.health.ENABLE_DETAILED_CHECKS and self.details:
            result["details"] = self.details

        return result


def check_database_health() -> HealthCheck:
    """
    Check MongoDB database connectivity and responsiveness.

    Returns:
        HealthCheck: Database health check result
    """
    start_time = datetime.now()

    try:
        # Create a client with a short timeout
        client = MongoClient(
            config.database.URI,
            serverSelectionTimeoutMS=config.health.TIMEOUT_SECONDS * 1000,
        )

        # Ping the database
        client.admin.command("ping")

        # Get server info for details
        server_info = client.server_info()

        latency_ms = (datetime.now() - start_time).total_seconds() * 1000

        return HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=latency_ms,
            details={"version": server_info.get("version"), "connection": "successful"},
        )

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Database health check failed: {str(e)}")

        return HealthCheck(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency_ms,
            message="Database connection failed",
            details={"error": "Connection timeout or failure"},
        )

    except Exception as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Database health check error: {str(e)}")

        return HealthCheck(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency_ms,
            message="Database check failed",
            details={"error": "Unexpected error"},
        )


def check_memory_health() -> HealthCheck:
    """
    Check system memory usage.

    Returns:
        HealthCheck: Memory health check result
    """
    try:
        memory = psutil.virtual_memory()

        used_mb = memory.used / (1024 * 1024)
        total_mb = memory.total / (1024 * 1024)
        percent_used = memory.percent

        # Determine health status based on threshold
        if used_mb > config.health.MEMORY_THRESHOLD_MB:
            status = HealthStatus.DEGRADED
            message = f"Memory usage high: {used_mb:.0f}MB / {total_mb:.0f}MB"
        else:
            status = HealthStatus.HEALTHY
            message = None

        return HealthCheck(
            name="memory",
            status=status,
            message=message,
            details={
                "used_mb": round(used_mb, 2),
                "total_mb": round(total_mb, 2),
                "percent_used": round(percent_used, 2),
                "threshold_mb": config.health.MEMORY_THRESHOLD_MB,
            },
        )

    except Exception as e:
        logger.error(f"Memory health check error: {str(e)}")

        return HealthCheck(
            name="memory",
            status=HealthStatus.UNHEALTHY,
            message="Memory check failed",
            details={"error": "Failed to retrieve memory info"},
        )


def check_disk_health() -> HealthCheck:
    """
    Check disk usage for the current working directory.

    Returns:
        HealthCheck: Disk health check result
    """
    try:
        disk = psutil.disk_usage(Path.cwd())

        used_gb = disk.used / (1024 * 1024 * 1024)
        total_gb = disk.total / (1024 * 1024 * 1024)
        free_gb = disk.free / (1024 * 1024 * 1024)
        percent_used = disk.percent

        # Consider degraded if >90% full
        if percent_used > 90:
            status = HealthStatus.DEGRADED
            message = f"Disk usage high: {percent_used:.1f}% full"
        else:
            status = HealthStatus.HEALTHY
            message = None

        return HealthCheck(
            name="disk",
            status=status,
            message=message,
            details={
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "percent_used": round(percent_used, 2),
            },
        )

    except Exception as e:
        logger.error(f"Disk health check error: {str(e)}")

        return HealthCheck(
            name="disk",
            status=HealthStatus.UNHEALTHY,
            message="Disk check failed",
            details={"error": "Failed to retrieve disk info"},
        )


def check_smtp_health() -> HealthCheck | None:
    """
    Check SMTP server connectivity (if configured).

    Returns:
        Optional[HealthCheck]: SMTP health check result, or None if not configured
    """
    # Skip if SMTP not configured
    if not config.email.SMTP_HOST:
        return None

    start_time = datetime.now()

    try:
        # Connect to SMTP server
        if config.email.SMTP_USE_TLS:
            smtp = smtplib.SMTP(
                config.email.SMTP_HOST,
                config.email.SMTP_PORT,
                timeout=config.health.TIMEOUT_SECONDS,
            )
            smtp.starttls()
        else:
            smtp = smtplib.SMTP(
                config.email.SMTP_HOST,
                config.email.SMTP_PORT,
                timeout=config.health.TIMEOUT_SECONDS,
            )

        # Test login if credentials provided
        if config.email.SMTP_USERNAME and config.email.SMTP_PASSWORD:
            smtp.login(config.email.SMTP_USERNAME, config.email.SMTP_PASSWORD)

        smtp.quit()

        latency_ms = (datetime.now() - start_time).total_seconds() * 1000

        return HealthCheck(
            name="smtp",
            status=HealthStatus.HEALTHY,
            latency_ms=latency_ms,
            details={
                "host": config.email.SMTP_HOST,
                "port": config.email.SMTP_PORT,
                "connection": "successful",
            },
        )

    except smtplib.SMTPAuthenticationError as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"SMTP health check authentication failed: {str(e)}")

        return HealthCheck(
            name="smtp",
            status=HealthStatus.DEGRADED,
            latency_ms=latency_ms,
            message="SMTP authentication failed",
            details={"error": "Authentication error"},
        )

    except (
        smtplib.SMTPConnectError,
        smtplib.SMTPServerDisconnected,
        TimeoutError,
    ) as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"SMTP health check connection failed: {str(e)}")

        return HealthCheck(
            name="smtp",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency_ms,
            message="SMTP connection failed",
            details={"error": "Connection timeout or failure"},
        )

    except Exception as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"SMTP health check error: {str(e)}")

        return HealthCheck(
            name="smtp",
            status=HealthStatus.DEGRADED,
            latency_ms=latency_ms,
            message="SMTP check failed",
            details={"error": "Unexpected error"},
        )


def perform_health_checks() -> dict[str, Any]:
    """
    Perform all health checks and return aggregated results.

    Returns:
        dict: Health check results with overall status
    """
    checks: dict[str, HealthCheck] = {}

    # Run all health checks
    checks["database"] = check_database_health()
    checks["memory"] = check_memory_health()
    checks["disk"] = check_disk_health()

    # Check SMTP if configured
    smtp_check = check_smtp_health()
    if smtp_check:
        checks["smtp"] = smtp_check

    # Determine overall health status
    overall_status = HealthStatus.HEALTHY

    for check in checks.values():
        if check.status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
            break
        if (
            check.status == HealthStatus.DEGRADED
            and overall_status == HealthStatus.HEALTHY
        ):
            overall_status = HealthStatus.DEGRADED

    # Build response
    response = {
        "status": overall_status,
        "timestamp": utc_now().isoformat(),
        "checks": {name: check.to_dict() for name, check in checks.items()},
    }

    # Log unhealthy status
    if overall_status != HealthStatus.HEALTHY:
        logger.warning(f"Health check status: {overall_status}")

    return response


def is_alive() -> bool:
    """
    Liveness probe - check if application is running.

    Returns:
        bool: Always True if application is running
    """
    return True


def is_ready() -> bool:
    """
    Readiness probe - check if application is ready to serve traffic.

    Checks critical dependencies (database) to determine readiness.

    Returns:
        bool: True if ready, False otherwise
    """
    try:
        db_check = check_database_health()
        return db_check.status != HealthStatus.UNHEALTHY
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return False
