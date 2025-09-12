"""
InMemory Test Suite

This package contains comprehensive tests for the InMemory library,
following pytest best practices and  testing patterns.

Test Structure:
- Unit tests: Test individual components in isolation
- Integration tests: Test component interactions and workflows
- Fixtures: Shared test utilities and mock objects

Usage:
    # Run all tests
    pytest tests/

    # Run with coverage
    pytest tests/ --cov=inmemory --cov-report=html

    # Run specific test categories
    pytest -m "unit" tests/
    pytest -m "integration" tests/
"""
