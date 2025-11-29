"""
Server Configuration Module

Following Uncle Bob's Clean Code principles:
- Single source of truth for all configuration
- No hardcoded values in application code
- Environment variable overrides
- Type-safe configuration access
"""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ErrorConfig:
    """Configuration for error handling and logging."""

    # Whether to expose detailed error information to API responses
    # Should ALWAYS be False in production
    EXPOSE_DETAILS: bool = os.getenv("ERROR_EXPOSE_DETAILS", "false").lower() == "true"

    # Log level for the application
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Whether to include request IDs in error responses
    INCLUDE_REQUEST_ID: bool = True

    # Whether to log stack traces for errors
    LOG_STACK_TRACES: bool = True


class DatabaseConfig:
    """Configuration for MongoDB database."""

    URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/selfmemory")
    TIMEOUT: int = int(os.getenv("MONGODB_TIMEOUT", "30"))
    MAX_POOL_SIZE: int = int(os.getenv("MONGODB_MAX_POOL_SIZE", "100"))

    # Transaction configuration
    TRANSACTION_TIMEOUT: int = int(os.getenv("MONGODB_TRANSACTION_TIMEOUT", "30"))
    RETRY_WRITES: bool = os.getenv("MONGODB_RETRY_WRITES", "true").lower() == "true"
    WRITE_CONCERN: str = os.getenv("MONGODB_WRITE_CONCERN", "majority")


class SecurityConfig:
    """Configuration for security features."""

    # CSRF Protection
    CSRF_SECRET_KEY: str | None = os.getenv("CSRF_SECRET_KEY")
    CSRF_COOKIE_SECURE: bool = os.getenv("CSRF_COOKIE_SECURE", "true").lower() == "true"
    CSRF_COOKIE_SAMESITE: str = os.getenv("CSRF_COOKIE_SAMESITE", "Strict")
    CSRF_COOKIE_HTTPONLY: bool = True
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    CSRF_COOKIE_NAME: str = "csrf_token"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = (
        os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
    )
    RATE_LIMIT_STORAGE_URL: str | None = os.getenv("RATE_LIMIT_STORAGE_URL")

    # Token expiry
    INVITATION_TOKEN_EXPIRY_HOURS: int = int(
        os.getenv("INVITATION_TOKEN_EXPIRY_HOURS", "24")
    )
    API_KEY_DEFAULT_EXPIRY_DAYS: int | None = (
        int(os.getenv("API_KEY_DEFAULT_EXPIRY_DAYS"))
        if os.getenv("API_KEY_DEFAULT_EXPIRY_DAYS")
        else None
    )


class AuthConfig:
    """Configuration for authentication and API key verification."""

    # Maximum number of Argon2 hash verifications per authentication attempt
    # Protects against performance attacks via prefix collision
    MAX_HASH_VERIFICATIONS: int = int(os.getenv("AUTH_MAX_HASH_VERIFICATIONS", "10"))

    # Threshold to warn about high prefix collision
    # If exceeded, logs warning about potential system issue
    COLLISION_WARNING_THRESHOLD: int = int(
        os.getenv("AUTH_COLLISION_WARNING_THRESHOLD", "50")
    )


class PaginationConfig:
    """Configuration for pagination."""

    DEFAULT_LIMIT: int = int(os.getenv("PAGINATION_DEFAULT_LIMIT", "10"))
    MAX_LIMIT: int = int(os.getenv("PAGINATION_MAX_LIMIT", "100"))


class EmailConfig:
    """Configuration for email/SMTP."""

    SMTP_HOST: str | None = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str | None = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@selfmemory.com")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "SelfMemory")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_TIMEOUT: int = int(os.getenv("SMTP_TIMEOUT", "10"))


class AppConfig:
    """General application configuration."""

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Timezone configuration
    TIMEZONE: str = os.getenv("TIMEZONE", "UTC")
    DEFAULT_DISPLAY_TIMEZONE: str = os.getenv("DEFAULT_DISPLAY_TIMEZONE", "UTC")


class ServerConfig:
    """Configuration for server runtime."""

    HOST: str = os.getenv("SELFMEMORY_SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("SELFMEMORY_SERVER_PORT", "8000"))


class VectorStoreConfig:
    """Configuration for vector store."""

    PROVIDER: str | None = os.getenv("VECTOR_STORE_PROVIDER")
    COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "memories")
    HOST: str | None = os.getenv("QDRANT_HOST")
    PORT: int | None = (
        int(os.getenv("QDRANT_PORT")) if os.getenv("QDRANT_PORT") else None
    )


class EmbeddingConfig:
    """Configuration for embeddings."""

    PROVIDER: str | None = os.getenv("EMBEDDING_PROVIDER")
    MODEL: str | None = os.getenv("EMBEDDING_MODEL")
    OLLAMA_BASE_URL: str | None = os.getenv("OLLAMA_BASE_URL")


class ValidationConfig:
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


class RateLimitConfig:
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


class HealthConfig:
    """Configuration for health checks."""

    ENABLE_DETAILED_CHECKS: bool = (
        os.getenv("HEALTH_ENABLE_DETAILED_CHECKS", "true").lower() == "true"
    )
    TIMEOUT_SECONDS: int = int(os.getenv("HEALTH_TIMEOUT_SECONDS", "5"))
    MEMORY_THRESHOLD_MB: int = int(os.getenv("HEALTH_MEMORY_THRESHOLD_MB", "900"))


class MetricsConfig:
    """Configuration for metrics and monitoring."""

    ENABLED: bool = os.getenv("METRICS_ENABLED", "false").lower() == "true"
    ENDPOINT: str = "/metrics"
    INCLUDE_REQUEST_DURATION: bool = True
    INCLUDE_RESPONSE_SIZE: bool = True


class LoggingConfig:
    """Configuration for structured logging."""

    FORMAT: str = os.getenv("LOGGING_FORMAT", "json")  # json or text
    LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    INCLUDE_REQUEST_ID: bool = True
    SAMPLE_RATE: float = float(os.getenv("LOGGING_SAMPLE_RATE", "1.0"))


class MCPConfig:
    """Configuration for Model Context Protocol (MCP) support."""

    # Whether MCP is enabled
    ENABLED: bool = os.getenv("MCP_ENABLED", "true").lower() == "true"

    # MCP server URL (this backend's public URL)
    SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8081")

    # Ory Hydra configuration for OAuth
    HYDRA_PUBLIC_URL: str = os.getenv("HYDRA_PUBLIC_URL", "http://127.0.0.1:4444")
    HYDRA_ADMIN_URL: str = os.getenv("HYDRA_ADMIN_URL", "http://127.0.0.1:4445")

    # MCP scopes - supports both MCP standard scopes and memory-specific scopes
    SCOPES_SUPPORTED: list[str] = [
        "memories:read",
        "memories:write",
        "mcp:tools",
        "mcp:resources",
    ]

    # Resource documentation
    RESOURCE_DOCUMENTATION_URL: str = os.getenv(
        "MCP_RESOURCE_DOCUMENTATION_URL", "https://docs.selfmemory.com"
    )


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
    vector_store = VectorStoreConfig()
    embedding = EmbeddingConfig()
    validation = ValidationConfig()
    rate_limit = RateLimitConfig()
    health = HealthConfig()
    metrics = MetricsConfig()
    logging = LoggingConfig()
    mcp = MCPConfig()

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
        if cls.app.ENVIRONMENT == "production":
            if cls.error.EXPOSE_DETAILS:
                errors.append("ERROR_EXPOSE_DETAILS must be false in production")

            if not cls.security.CSRF_SECRET_KEY:
                errors.append("CSRF_SECRET_KEY is required in production")

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
        logger.info(f"Vector Store: {cls.vector_store.PROVIDER or 'Not configured'}")
        logger.info(f"Embedding Provider: {cls.embedding.PROVIDER or 'Not configured'}")
        logger.info(f"Metrics: {'Enabled' if cls.metrics.ENABLED else 'Disabled'}")
        logger.info(f"Log Level: {cls.logging.LEVEL}")
        logger.info(f"Error Details Exposed: {cls.error.EXPOSE_DETAILS}")
        logger.info("=" * 50)


# Create singleton config instance
config = Config()
