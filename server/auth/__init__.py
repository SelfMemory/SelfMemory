"""
Authentication module for Ory Kratos and Hydra integration.

Provides session validation (Kratos) and token validation (Hydra)
for multi-tenant authentication.
"""

from .hydra_validator import (
    HydraToken,
    validate_token,
    validate_token_scope,
    validate_token_with_project,
)
from .kratos_validator import KratosSession, get_identity_by_id, validate_session
from .ory_config import (
    get_hydra_oauth2_api,
    get_kratos_frontend_api,
    get_kratos_identity_api,
    ory_config,
)

__all__ = [
    # Kratos session validation
    "KratosSession",
    "validate_session",
    "get_identity_by_id",
    # Hydra token validation
    "HydraToken",
    "validate_token",
    "validate_token_with_project",
    "validate_token_scope",
    # Configuration and API clients
    "ory_config",
    "get_kratos_frontend_api",
    "get_kratos_identity_api",
    "get_hydra_oauth2_api",
]
