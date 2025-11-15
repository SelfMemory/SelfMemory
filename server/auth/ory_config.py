"""
Ory client configuration.

Initializes Kratos and Hydra API clients with environment-based configuration.
No fallbacks - fail fast if configuration is missing.
"""

import logging
import os

from ory_hydra_client import Configuration as HydraConfiguration
from ory_hydra_client.api_client import ApiClient as HydraApiClient
from ory_hydra_client.apis import OAuth2Api as HydraOAuth2Api
from ory_kratos_client import Configuration as KratosConfiguration
from ory_kratos_client import FrontendApi as KratosFrontendApi
from ory_kratos_client import IdentityApi as KratosIdentityApi
from ory_kratos_client.api_client import ApiClient as KratosApiClient

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


class OryConfig:
    """Ory service endpoints configuration."""

    def __init__(self):
        """Initialize Ory configuration from environment variables."""
        # Kratos endpoints
        self.kratos_public_url: str = self._get_required_env("KRATOS_PUBLIC_URL")
        self.kratos_admin_url: str = self._get_required_env("KRATOS_ADMIN_URL")

        # Hydra endpoints
        self.hydra_public_url: str = self._get_required_env("HYDRA_PUBLIC_URL")
        self.hydra_admin_url: str = self._get_required_env("HYDRA_ADMIN_URL")

        logger.info(
            f"Ory configuration loaded - "
            f"Kratos: {self.kratos_public_url}, "
            f"Hydra: {self.hydra_public_url}"
        )

    @staticmethod
    def _get_required_env(key: str) -> str:
        """
        Get required environment variable.

        Fails fast if missing - no fallbacks.

        Args:
            key: Environment variable name

        Returns:
            str: Environment variable value

        Raises:
            ValueError: If environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            error_msg = f"Required environment variable '{key}' is not set"
            logger.error(error_msg)
            raise ValueError(error_msg)
        return value


# Global configuration instance
ory_config = OryConfig()


# ============================================================================
# Kratos API Clients
# ============================================================================


class KratosClients:
    """Kratos API client instances."""

    def __init__(self, config: OryConfig):
        """
        Initialize Kratos API clients.

        Args:
            config: Ory configuration instance
        """
        # Public API configuration (for session validation from cookies)
        public_config = KratosConfiguration(host=config.kratos_public_url)
        self.public_client = KratosApiClient(configuration=public_config)
        self.frontend_api = KratosFrontendApi(api_client=self.public_client)

        # Admin API configuration (for user management)
        admin_config = KratosConfiguration(host=config.kratos_admin_url)
        self.admin_client = KratosApiClient(configuration=admin_config)
        self.identity_api = KratosIdentityApi(api_client=self.admin_client)

        logger.info("Kratos API clients initialized")


# Global Kratos client instance
kratos_clients = KratosClients(ory_config)


# ============================================================================
# Hydra API Clients
# ============================================================================


class HydraClients:
    """Hydra API client instances."""

    def __init__(self, config: OryConfig):
        """
        Initialize Hydra API clients.

        Args:
            config: Ory configuration instance
        """
        # Public API configuration (for token validation)
        public_config = HydraConfiguration(host=config.hydra_public_url)
        self.public_client = HydraApiClient(configuration=public_config)

        # Admin API configuration (for token introspection and client management)
        admin_config = HydraConfiguration(host=config.hydra_admin_url)
        self.admin_client = HydraApiClient(configuration=admin_config)
        self.oauth2_api = HydraOAuth2Api(api_client=self.admin_client)

        logger.info("Hydra API clients initialized")


# Global Hydra client instance
hydra_clients = HydraClients(ory_config)


# ============================================================================
# Public API
# ============================================================================


def get_kratos_frontend_api() -> KratosFrontendApi:
    """Get Kratos Frontend API for session validation."""
    return kratos_clients.frontend_api


def get_kratos_identity_api() -> KratosIdentityApi:
    """Get Kratos Identity API for user management."""
    return kratos_clients.identity_api


def get_hydra_oauth2_api() -> HydraOAuth2Api:
    """Get Hydra OAuth2 API for token operations."""
    return hydra_clients.oauth2_api
