"""
Tests for API documentation security features.

Verifies that documentation endpoints are properly disabled in production
to prevent information disclosure vulnerabilities.
"""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_docs_enabled_in_development():
    """Test that documentation endpoints are available in development environment."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        # Import after setting environment variable
        from server.main import app

        client = TestClient(app)

        # Test /docs endpoint
        response = client.get("/docs")
        assert response.status_code == 200
        assert "Swagger UI" in response.text or "swagger" in response.text.lower()

        # Test /redoc endpoint
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()

        # Test /openapi.json endpoint
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        openapi_data = response.json()
        assert "openapi" in openapi_data
        assert "paths" in openapi_data


def test_docs_disabled_in_production():
    """Test that documentation endpoints are disabled in production environment."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        # Import after setting environment variable
        from server.main import app

        client = TestClient(app)

        # Test /docs endpoint returns 404
        response = client.get("/docs")
        assert response.status_code == 404

        # Test /redoc endpoint returns 404
        response = client.get("/redoc")
        assert response.status_code == 404

        # Test /openapi.json endpoint returns 404
        response = client.get("/openapi.json")
        assert response.status_code == 404


def test_docs_enabled_in_staging():
    """Test that documentation endpoints are available in staging environment."""
    with patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=False):
        # Import after setting environment variable
        from server.main import app

        client = TestClient(app)

        # Test /docs endpoint
        response = client.get("/docs")
        assert response.status_code == 200

        # Test /redoc endpoint
        response = client.get("/redoc")
        assert response.status_code == 200

        # Test /openapi.json endpoint
        response = client.get("/openapi.json")
        assert response.status_code == 200


def test_api_endpoints_still_work_in_production():
    """Test that API endpoints still function normally in production."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        # Import after setting environment variable
        from server.main import app

        client = TestClient(app)

        # Test health endpoint still works
        response = client.get("/health")
        assert response.status_code == 200

        # Test health endpoint requires no auth
        response = client.get("/health")
        assert response.status_code == 200
