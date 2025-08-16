"""
InMemory API Server - Managed solution backend.

This module provides the API server for the managed InMemory service,
handling authentication, user management, and memory operations.
"""

from .server import InMemoryAPI, create_app

__all__ = ["create_app", "InMemoryAPI"]
