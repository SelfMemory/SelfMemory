# SelfMemory Tests

This directory contains the test suite for the selfmemory-core package, following Uncle Bob's clean code principles and inspired by selfmemory's testing patterns.

## Test Structure

```
tests/
├── __init__.py          # Package marker
├── test_qdrant.py       # Qdrant vector store unit tests
└── README.md           # This file
```

## Running Tests

### Prerequisites
Install test dependencies:
```bash
uv sync --extra test
```

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Run Specific Test File
```bash
uv run pytest tests/test_qdrant.py -v
```

### Run with Coverage Report
```bash
uv run pytest tests/ -v --cov=selfmemory --cov-report=html
```

## Test Types

### Unit Tests (Current)
- **Location**: `test_qdrant.py`
- **Purpose**: Test individual components in isolation
- **Dependencies**: All external dependencies are mocked
- **Speed**: Very fast (milliseconds)
- **Coverage**: 96% for Qdrant vector store

### Key Features Tested

#### Qdrant Vector Store (`test_qdrant.py`)
- ✅ Initialization (client, host/port, local path)
- ✅ Collection management (create, delete, info, list)
- ✅ Vector operations (insert, search, update, delete, get)
- ✅ User isolation (critical for multi-user system)
- ✅ Filter logic (single and multiple conditions, range filters)
- ✅ Error handling and edge cases
- ✅ Index creation (local vs remote)
- ✅ Bulk operations (delete_all, reset)

## Testing Philosophy

Following **Uncle Bob's Clean Code** principles:
- **Fast**: Unit tests run in milliseconds
- **Independent**: Each test is isolated and doesn't depend on others
- **Repeatable**: Tests produce consistent results
- **Self-Validating**: Clear pass/fail results
- **Timely**: Tests are written alongside code

Following **selfmemory's proven patterns**:
- **Mock external dependencies**: No real databases or APIs needed
- **Simple structure**: Direct test files without over-engineering
- **Comprehensive coverage**: Test all methods and edge cases
- **User isolation focus**: Ensure security boundaries are maintained

## CI/CD Integration

Tests run automatically on:
- **Commits** to master branch
- **Pull requests** to master branch
- **Local development** via pre-commit hooks (future)

## Test Results

Current status: **28/28 tests passing** ✅
- All Qdrant vector store functionality tested
- 96% code coverage on core vector operations
- Zero external dependencies required
- Fast execution (< 3 seconds)

## Future Additions

Planned test expansions:
- Embedding provider tests (Ollama, OpenAI)
- SelfMemory class integration tests
- SelfMemoryClient HTTP client tests
- Configuration validation tests
