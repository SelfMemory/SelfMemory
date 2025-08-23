# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.11] - 2025-01-23

### Fixed
- **Fixed Docs**: Updated documentation for clarity and accuracy.

## [0.1.1] - 2025-01-23

### Fixed
- **Code Quality**: Fixed all 96 linting errors identified by ruff
- **Exception Handling**: Improved exception chaining with proper `from e` or `from None` usage (B904)
- **Import Management**: Cleaned up unused imports and conditional imports (F401, F821)
- **Path Handling**: Modernized path operations using pathlib instead of os.path (PTH118, PTH120, PTH110)
- **Code Style**: Applied consistent formatting and removed trailing whitespace
- **Type Annotations**: Updated isinstance calls to use modern union syntax (UP038)

### Changed
- **Pre-commit Hooks**: Enhanced pre-commit configuration for better code quality
- **Version Consistency**: Synchronized version numbers across pyproject.toml and __init__.py
- **Build System**: Prepared package for PyPI distribution with proper metadata

### Technical Improvements
- All ruff linting rules now pass without errors
- Improved exception handling throughout the codebase
- Better error messages and debugging information
- Consistent code formatting across all Python files

## [0.1.0] - 2025-01-17

### Added
- **Zero-setup Architecture**: Works immediately with file storage, no external dependencies required
- **Progressive Complexity**: Basic → Server → Enterprise → Full installation modes
- **Multiple Storage Backends**: File-based (default) and MongoDB support
- **Advanced Search Engine**: Semantic, temporal, tag-based, and people-based search
- **Enhanced Metadata Support**: Rich tagging, people mentions, topic categories, and custom metadata
- **Duplicate Detection**: Prevents storing similar memories with configurable similarity thresholds
- **Configuration Management**: Auto-detection, YAML configs, environment variables
- **CLI Interface**: Easy server management and initialization commands
- **API Server**: FastAPI-based REST API with full OpenAPI documentation
- **Managed Service Client**: Cloud-ready client with API key authentication
- **Enterprise Features**: MongoDB backend, OAuth integration, user management
- **MCP Server Support**: Model Context Protocol integration for AI agents
- **Security Features**: Encryption, secure API key generation, user isolation
- **Examples**: Comprehensive usage examples for different scenarios

### Features

**Core SDK:**
- Memory operations: add, search, get_all, delete, delete_all
- Advanced search: temporal_search, search_by_tags, search_by_people
- User management: create_user, generate_api_key, list_api_keys, revoke_api_key
- Configuration: get_config, health_check, context manager support
- Auto-detection of deployment environment (file vs enterprise)

**Storage Backends:**
- **File Storage**: JSON-based storage with atomic writes, perfect for development
- **MongoDB Storage**: Scalable enterprise backend with user collections
- **Storage Abstraction**: Clean interface for additional backends (PostgreSQL coming soon)

**Search Capabilities:**
- **Semantic Search**: Vector-based similarity search using embeddings
- **Temporal Search**: Date/time-based filtering ("yesterday", "this week", etc.)
- **Tag Search**: Single or multiple tags with AND/OR logic
- **People Search**: Find memories by mentioned people
- **Combined Search**: Mix semantic queries with metadata filters
- **Score Thresholds**: Filter results by similarity scores

**Installation Modes:**
```bash
pip install inmemory                    # Zero dependencies
pip install inmemory[server]            # + FastAPI server
pip install inmemory[enterprise]        # + MongoDB + OAuth
pip install inmemory[full]              # Everything + MCP
```

**API Server:**
- RESTful endpoints for all memory operations
- OpenAPI/Swagger documentation at `/docs`
- Health checks and status monitoring
- CORS support for web applications
- User authentication and API key management

**Configuration:**
- Auto-detection based on environment
- YAML configuration files
- Environment variable overrides
- Secure defaults for production use

### Technical Details

**Dependencies:**
- **Core**: qdrant-client, pydantic, python-dotenv, cryptography, httpx
- **Optional**: FastAPI, MongoDB, OAuth providers, MCP, embedding models
- **Python**: Requires Python 3.12+

**Architecture:**
- **Storage Layer**: Pluggable storage backends with consistent interface
- **Search Layer**: Enhanced search engine with Qdrant vector database
- **API Layer**: Optional FastAPI server for remote access
- **Security Layer**: Encryption, authentication, and user isolation

**Testing:**
- Unit tests for core functionality
- Integration tests for end-to-end workflows
- Example tests validating README code samples
- Support for multiple Python versions and platforms

### Documentation
- Comprehensive README with examples and comparisons
- Installation guide for different deployment scenarios
- API reference documentation
- Contributing guidelines
- Security best practices

### Examples
- Personal AI Assistant integration
- Customer Support Bot with memory context
- Multi-user applications with data isolation
- Configuration examples for different environments
- Migration between storage backends

---

## Release Notes

### Version 0.1.0 - "Zero Setup"

This initial release focuses on **ease of use** and **progressive complexity**. You can start using InMemory immediately with zero configuration, then scale up to enterprise features as needed.

**Key Highlights:**
- 🚀 **Zero Setup**: `pip install inmemory` and start using immediately
- 🏗️ **Flexible Architecture**: File → API Server → Enterprise MongoDB
- 🔍 **Advanced Search**: Semantic, temporal, and metadata-based search
- 🚫 **Duplicate Prevention**: Intelligent memory deduplication
- ⚙️ **Multiple Backends**: File storage and MongoDB with more coming
- 🌐 **API Ready**: Full REST API with OpenAPI documentation

### Breaking Changes
None (initial release).

### Migration Guide
This is the initial release, so no migration is needed.

### Contributors
- InMemory Team - Initial implementation and architecture
- Community contributors - Testing, feedback, and documentation improvements

---

## Development Changelog

### Development Milestones

**Phase 1: Core Architecture (Completed)**
- [x] Memory SDK with clean API
- [x] File storage backend implementation
- [x] Configuration management system
- [x] Basic search functionality

**Phase 2: Advanced Features (Completed)**
- [x] Enhanced search engine with multiple search types
- [x] MongoDB backend for enterprise use
- [x] API server with FastAPI
- [x] Security features and user management

**Phase 3: Polish & Release (In Progress)**
- [x] Comprehensive test suite
- [x] Documentation and examples
- [ ] CI/CD pipeline
- [ ] PyPI package preparation
- [ ] Security audit

**Phase 4: Community & Growth (Planned)**
- [ ] TypeScript SDK
- [ ] Additional storage backends (PostgreSQL, Redis)
- [ ] Performance optimizations
- [ ] Advanced analytics

### Acknowledgments

**Inspiration:**
- [Qdrant](https://qdrant.tech/) for high-performance vector search
- [FastAPI](https://fastapi.tiangolo.com/) for the modern Python API framework

**Dependencies:**
- Qdrant Client for vector operations
- Pydantic for data validation
- FastAPI for API server functionality
- pymongo for MongoDB integration
- cryptography for security features

---

## Support

- **Documentation**: See README.md and docs/ directory
- **Issues**: Report bugs and request features on GitHub
- **Discussions**: Ask questions in GitHub Discussions
- **Security**: Report security issues to security@inmemory.dev

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE.txt](LICENSE.txt) file for details.
