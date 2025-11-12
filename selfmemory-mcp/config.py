"""Configuration management for SelfMemory MCP Server.

Loads configuration from environment variables with no fallback mechanisms.
All required values must be provided via .env file.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Configuration error - raised when required config is missing or invalid."""
    pass


class ConfigValidationError(Exception):
    """Configuration validation error - raised when config values are invalid."""
    pass


def get_required_env(key: str) -> str:
    """Get required environment variable.
    
    Args:
        key: Environment variable name
        
    Returns:
        Environment variable value
        
    Raises:
        ConfigError: If environment variable is not set
    """
    value = os.getenv(key)
    if not value:
        raise ConfigError(f"Required environment variable {key} is not set")
    return value


def get_optional_env(key: str, default: str | None = None) -> str | None:
    """Get optional environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


class HydraConfig:
    """Ory Hydra OAuth 2.1 configuration."""

    def __init__(self):
        # Required Hydra URLs
        self.admin_url = get_required_env("HYDRA_ADMIN_URL")
        self.public_url = get_required_env("HYDRA_PUBLIC_URL")
        self.mcp_server_url = get_required_env("MCP_SERVER_URL")
        
        # RFC 8707: Canonical resource URL (no trailing slash)
        # Used as the `resource` parameter in OAuth flows and token audience validation
        self.resource_url = self.mcp_server_url.rstrip('/')

        # Scopes supported by MCP server
        # Include both custom MCP scopes and standard OAuth/OIDC scopes
        # that clients like VS Code and ChatGPT expect
        self.scopes_supported = [
            "memories:read",      # Custom: Read memories
            "memories:write",     # Custom: Create/modify memories
            "offline",            # OAuth: Refresh token support (legacy)
            "offline_access",     # OAuth: Refresh token support (standard)
            "openid",             # OIDC: User authentication
        ]

        # Bearer methods supported (RFC 9728)
        self.bearer_methods_supported = ["header"]


class ServerConfig:
    """MCP server configuration."""

    def __init__(self):
        self.host = get_optional_env("MCP_SERVER_HOST", "0.0.0.0")
        self.port = int(get_optional_env("MCP_SERVER_PORT", "8080"))
        self.selfmemory_api_host = get_required_env("SELFMEMORY_API_HOST")


class Config:
    """Main configuration container."""

    def __init__(self):
        self.hydra = HydraConfig()
        self.server = ServerConfig()

    def validate(self) -> None:
        """Validate configuration on startup.
        
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        errors = []

        # Validate Hydra admin URL format
        if not self.hydra.admin_url.startswith(('http://', 'https://')):
            errors.append("HYDRA_ADMIN_URL must start with http:// or https://")

        # Validate Hydra public URL format
        if not self.hydra.public_url.startswith(('http://', 'https://')):
            errors.append("HYDRA_PUBLIC_URL must start with http:// or https://")

        # Validate MCP server URL format
        if not self.hydra.mcp_server_url.startswith(('http://', 'https://')):
            errors.append("MCP_SERVER_URL must start with http:// or https://")

        # Validate server port is in valid range
        if not (1 <= self.server.port <= 65535):
            errors.append("MCP_SERVER_PORT must be between 1 and 65535")

        # Validate SelfMemory API host format
        if not self.server.selfmemory_api_host.startswith(('http://', 'https://')):
            errors.append("SELFMEMORY_API_HOST must start with http:// or https://")

        # Raise all errors together
        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ConfigValidationError(error_message)


def validate_config() -> Config:
    """Load and validate configuration.
    
    Returns:
        Validated Config instance
        
    Raises:
        ConfigError: If required environment variables are missing
        ConfigValidationError: If configuration values are invalid
    """
    try:
        cfg = Config()
        cfg.validate()
        return cfg
    except ConfigError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease ensure all required environment variables are set in your .env file.")
        print("See .env.example for reference.\n")
        raise
    except ConfigValidationError as e:
        print(f"\n❌ {e}\n")
        raise


# Global configuration instance
config = validate_config()
