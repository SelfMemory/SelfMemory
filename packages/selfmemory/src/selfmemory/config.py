"""Typed server configuration (pydantic-settings).

Every section reads its values from the environment (and ``.env``) once, at
import time. Attribute names and environment variable names are unchanged
from the previous hand-rolled loader, so ``config.database.URI`` still reads
``MONGODB_URI``.
"""

import os
from typing import Annotated

from dotenv import load_dotenv
from pydantic import AfterValidator, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables
load_dotenv()


class _Section(BaseSettings):
    """A config section populated from environment variables."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)


class ErrorConfig(_Section):
    """Configuration for error handling and logging."""

    # Whether to expose detailed error information to API responses
    # Should ALWAYS be False in production
    EXPOSE_DETAILS: bool = Field(False, validation_alias="ERROR_EXPOSE_DETAILS")

    # Log level for the application
    LOG_LEVEL: Annotated[str, AfterValidator(str.upper)] = Field(
        "INFO", validation_alias="LOG_LEVEL"
    )

    # Whether to include request IDs in error responses
    INCLUDE_REQUEST_ID: bool = True

    # Whether to log stack traces for errors
    LOG_STACK_TRACES: bool = True


class DatabaseConfig(_Section):
    """Configuration for MongoDB database."""

    URI: str = Field(
        "mongodb://localhost:27017/selfmemory", validation_alias="MONGODB_URI"
    )
    TIMEOUT: int = Field(30, validation_alias="MONGODB_TIMEOUT")
    MAX_POOL_SIZE: int = Field(100, validation_alias="MONGODB_MAX_POOL_SIZE")

    # Transaction configuration
    TRANSACTION_TIMEOUT: int = Field(30, validation_alias="MONGODB_TRANSACTION_TIMEOUT")
    RETRY_WRITES: bool = Field(True, validation_alias="MONGODB_RETRY_WRITES")

    WRITE_CONCERN: str = Field("majority", validation_alias="MONGODB_WRITE_CONCERN")


class SecurityConfig(_Section):
    """Configuration for security features."""

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(False, validation_alias="RATE_LIMIT_ENABLED")
    RATE_LIMIT_STORAGE_URL: str | None = Field(
        None, validation_alias="RATE_LIMIT_STORAGE_URL"
    )

    # Token expiry
    INVITATION_TOKEN_EXPIRY_HOURS: int = Field(
        24, validation_alias="INVITATION_TOKEN_EXPIRY_HOURS"
    )
    API_KEY_DEFAULT_EXPIRY_DAYS: int | None = Field(
        None, validation_alias="API_KEY_DEFAULT_EXPIRY_DAYS"
    )


class AuthConfig(_Section):
    """Configuration for authentication and API key verification."""

    # Maximum number of Argon2 hash verifications per authentication attempt
    # Protects against performance attacks via prefix collision
    MAX_HASH_VERIFICATIONS: int = Field(
        10, validation_alias="AUTH_MAX_HASH_VERIFICATIONS"
    )

    # Threshold to warn about high prefix collision
    # If exceeded, logs warning about potential system issue
    COLLISION_WARNING_THRESHOLD: int = Field(
        50, validation_alias="AUTH_COLLISION_WARNING_THRESHOLD"
    )


class PaginationConfig(_Section):
    """Configuration for pagination."""

    DEFAULT_LIMIT: int = Field(10, validation_alias="PAGINATION_DEFAULT_LIMIT")
    MAX_LIMIT: int = Field(100, validation_alias="PAGINATION_MAX_LIMIT")


class EmailConfig(_Section):
    """Configuration for email/SMTP."""

    SMTP_HOST: str | None = Field(None, validation_alias="SMTP_HOST")
    SMTP_PORT: int = Field(587, validation_alias="SMTP_PORT")
    SMTP_USERNAME: str | None = Field(None, validation_alias="SMTP_USERNAME")
    SMTP_PASSWORD: str | None = Field(None, validation_alias="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(
        "noreply@selfmemory.com", validation_alias="SMTP_FROM_EMAIL"
    )
    SMTP_FROM_NAME: str = Field("SelfMemory", validation_alias="SMTP_FROM_NAME")
    SMTP_USE_TLS: bool = Field(True, validation_alias="SMTP_USE_TLS")

    SMTP_TIMEOUT: int = Field(10, validation_alias="SMTP_TIMEOUT")


class AppConfig(_Section):
    """General application configuration."""

    FRONTEND_URL: str = Field("http://localhost:3000", validation_alias="FRONTEND_URL")
    BACKEND_URL: str = Field("http://localhost:8081", validation_alias="BACKEND_URL")
    ENVIRONMENT: str = Field("development", validation_alias="ENVIRONMENT")

    # Timezone configuration
    TIMEZONE: str = Field("UTC", validation_alias="TIMEZONE")
    DEFAULT_DISPLAY_TIMEZONE: str = Field(
        "UTC", validation_alias="DEFAULT_DISPLAY_TIMEZONE"
    )


class ServerConfig(_Section):
    """Configuration for server runtime."""

    HOST: str = Field("0.0.0.0", validation_alias="SELFMEMORY_SERVER_HOST")
    PORT: int = Field(8081, validation_alias="SELFMEMORY_SERVER_PORT")


class ValidationConfig(BaseModel):
    """Configuration for input validation."""

    # Organization name validation
    ORG_NAME_MIN_LENGTH: int = 2
    ORG_NAME_MAX_LENGTH: int = 100
    ORG_NAME_PATTERN: str = r"^[a-zA-Z0-9\s\-\_]+$"

    # Project name validation
    PROJECT_NAME_MIN_LENGTH: int = 2
    PROJECT_NAME_MAX_LENGTH: int = 100
    PROJECT_NAME_PATTERN: str = r"^[a-zA-Z0-9\s\-\_]+$"

    # Tag validation
    TAG_MIN_LENGTH: int = 1
    TAG_MAX_LENGTH: int = 50
    TAG_PATTERN: str = r"^[a-zA-Z0-9\-\_]+$"

    # Memory content validation
    MEMORY_CONTENT_MAX_LENGTH: int = 10000


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""

    # Invitation endpoints (strict)
    INVITATION_CREATE: str = "5/minute"
    INVITATION_ACCEPT: str = "3/minute"

    # Memory operations
    MEMORY_CREATE: str = "20/minute"
    MEMORY_READ: str = "60/minute"
    MEMORY_SEARCH: str = "30/minute"

    # Project/Organization creation
    PROJECT_CREATE: str = "10/minute"
    ORGANIZATION_CREATE: str = "10/minute"

    # Default for other operations
    DEFAULT: str = "120/minute"


class HealthConfig(_Section):
    """Configuration for health checks."""

    ENABLE_DETAILED_CHECKS: bool = Field(
        True, validation_alias="HEALTH_ENABLE_DETAILED_CHECKS"
    )
    TIMEOUT_SECONDS: int = Field(5, validation_alias="HEALTH_TIMEOUT_SECONDS")
    MEMORY_THRESHOLD_MB: int = Field(900, validation_alias="HEALTH_MEMORY_THRESHOLD_MB")


class MetricsConfig(_Section):
    """Configuration for metrics and monitoring."""

    ENABLED: bool = Field(False, validation_alias="METRICS_ENABLED")

    ENDPOINT: str = "/metrics"
    INCLUDE_REQUEST_DURATION: bool = True
    INCLUDE_RESPONSE_SIZE: bool = True


class LoggingConfig(_Section):
    """Configuration for structured logging."""

    FORMAT: str = Field("json", validation_alias="LOGGING_FORMAT")  # json or text
    LEVEL: Annotated[str, AfterValidator(str.upper)] = Field(
        "INFO", validation_alias="LOG_LEVEL"
    )
    INCLUDE_REQUEST_ID: bool = True
    SAMPLE_RATE: float = Field(1.0, validation_alias="LOGGING_SAMPLE_RATE")


class MCPConfig(_Section):
    """Configuration for Model Context Protocol (MCP) support."""

    # Whether MCP is enabled
    ENABLED: bool = Field(True, validation_alias="MCP_ENABLED")

    # MCP server URL (this backend's public URL)
    SERVER_URL: str = Field("http://localhost:8081", validation_alias="MCP_SERVER_URL")

    # Ory Hydra configuration for OAuth
    HYDRA_PUBLIC_URL: str = Field(
        "http://127.0.0.1:4444", validation_alias="HYDRA_PUBLIC_URL"
    )
    HYDRA_ADMIN_URL: str = Field(
        "http://127.0.0.1:4445", validation_alias="HYDRA_ADMIN_URL"
    )

    # MCP scopes - supports both MCP standard scopes and memory-specific scopes
    SCOPES_SUPPORTED: list[str] = [
        "memories:read",
        "memories:write",
        "mcp:tools",
        "mcp:resources",
    ]

    # Resource documentation
    RESOURCE_DOCUMENTATION_URL: str = Field(
        "https://docs.selfmemory.com", validation_alias="MCP_RESOURCE_DOCUMENTATION_URL"
    )


class OTelConfig(_Section):
    """Configuration for OpenTelemetry observability (production only)."""

    # Whether OpenTelemetry is enabled
    ENABLED: bool = Field(False, validation_alias="OTEL_ENABLED")

    # Service name for identification in SigNoz
    SERVICE_NAME: str = Field("selfmemory-api", validation_alias="OTEL_SERVICE_NAME")

    # OTLP exporter endpoint (SigNoz gRPC endpoint)
    OTLP_ENDPOINT: str = Field(
        "http://localhost:4317", validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    # Protocol: grpc or http/protobuf
    PROTOCOL: str = Field("grpc", validation_alias="OTEL_EXPORTER_OTLP_PROTOCOL")

    # Trace sampling configuration
    TRACES_SAMPLER: str = Field(
        "parentbased_traceidratio", validation_alias="OTEL_TRACES_SAMPLER"
    )
    TRACES_SAMPLER_ARG: float = Field(1.0, validation_alias="OTEL_TRACES_SAMPLER_ARG")


# Main configuration object
class Config:
    """Main configuration class that aggregates all config sections."""

    error = ErrorConfig()
    database = DatabaseConfig()
    security = SecurityConfig()
    auth = AuthConfig()
    pagination = PaginationConfig()
    email = EmailConfig()
    app = AppConfig()
    server = ServerConfig()
    validation = ValidationConfig()
    rate_limit = RateLimitConfig()
    health = HealthConfig()
    metrics = MetricsConfig()
    logging = LoggingConfig()
    mcp = MCPConfig()
    otel = OTelConfig()

    @classmethod
    def validate(cls) -> list[str]:
        """
        Validate configuration on startup.

        Returns:
            list[str]: List of validation errors (empty if all valid)
        """
        errors = []

        # Check required configurations
        if not cls.database.URI:
            errors.append("MONGODB_URI is required")

        if cls.security.RATE_LIMIT_ENABLED and not cls.security.RATE_LIMIT_STORAGE_URL:
            errors.append(
                "RATE_LIMIT_STORAGE_URL is required when rate limiting is enabled"
            )

        # Validate environment
        if cls.app.ENVIRONMENT not in ["development", "staging", "production"]:
            errors.append(f"Invalid ENVIRONMENT: {cls.app.ENVIRONMENT}")

        # Security checks for production
        if cls.app.ENVIRONMENT == "production" and cls.error.EXPOSE_DETAILS:
            errors.append("ERROR_EXPOSE_DETAILS must be false in production")

        return errors

    @classmethod
    def log_config(cls) -> None:
        """Log current configuration (excluding sensitive values)."""
        import logging

        logger = logging.getLogger(__name__)

        logger.info("=" * 50)
        logger.info("SERVER CONFIGURATION")
        logger.info("=" * 50)
        logger.info(f"Environment: {cls.app.ENVIRONMENT}")
        logger.info(f"Server: {cls.server.HOST}:{cls.server.PORT}")
        logger.info(f"Frontend URL: {cls.app.FRONTEND_URL}")
        logger.info(f"Backend URL: {cls.app.BACKEND_URL}")
        logger.info(f"Database Timeout: {cls.database.TIMEOUT}s")
        logger.info(
            f"Rate Limiting: {'Enabled' if cls.security.RATE_LIMIT_ENABLED else 'Disabled'}"
        )
        logger.info(f"SMTP Configured: {'Yes' if cls.email.SMTP_HOST else 'No'}")
        logger.info(
            "Wiki data root: "
            f"{os.getenv('SELFMEMORY_DATA_ROOT') or '~/.selfmemory/data'}"
        )
        logger.info(f"Metrics: {'Enabled' if cls.metrics.ENABLED else 'Disabled'}")
        logger.info(f"Log Level: {cls.logging.LEVEL}")
        logger.info(f"Error Details Exposed: {cls.error.EXPOSE_DETAILS}")
        logger.info("=" * 50)


# Create singleton config instance
config = Config()
