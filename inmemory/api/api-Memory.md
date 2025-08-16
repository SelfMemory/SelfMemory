# API Folder Memory

## Purpose
This folder contains the managed solution backend for InMemory, providing REST API endpoints for hosted memory management.

## Files

### `__init__.py`
- **Purpose**: Package initialization for the API module
- **Exports**: `create_app`, `InMemoryAPI`
- **Important functions**: 
  - Module-level imports to make API classes available

### `server.py`
- **Purpose**: Main FastAPI application implementing the managed InMemory API
- **Important functions**:
  - `InMemoryAPI.__init__()`: Initialize API with configuration and storage, load existing API keys
  - `InMemoryAPI._validate_api_key(api_key: str)`: Validate API key and return user info, update usage stats
  - `InMemoryAPI.generate_api_key(user_id: str, name: str)`: Generate secure API key with im_ prefix
  - `InMemoryAPI.revoke_api_key(api_key: str)`: Revoke API key from memory and storage
  - `get_current_user(credentials)`: FastAPI dependency for authentication, validates Bearer token
  - `create_app()`: Create and configure FastAPI application with all endpoints
  - `run_server(host, port, debug)`: Utility function to run the API server
- **Key Features**:
  - Bearer token authentication using API keys
  - RESTful endpoints for all memory operations
  - Pydantic models for request/response validation
  - CORS middleware for cross-origin requests
  - Comprehensive error handling with HTTP status codes
  - Integration with existing Memory class for core functionality

### `README.md`
- **Purpose**: Documentation for the API server
- **Contains**: Setup instructions, endpoint documentation, authentication details, deployment guide

## API Architecture

### Authentication Flow
1. Client requests API key from `/v1/auth/generate-key/`
2. Server generates secure key with `im_` prefix
3. Client includes key in Authorization header: `Bearer <api-key>`
4. Server validates key on each request and tracks usage

### Storage Integration
- Uses existing InMemory storage backends (file-based, MongoDB)
- API keys stored in memory with optional persistence
- User creation automatic on first memory addition

### Key Endpoints
- **Authentication**: `/v1/auth/generate-key/`, `/v1/auth/revoke-key/`
- **Core Memory**: `/v1/memories/` (GET, POST, DELETE)
- **Search**: `/v1/memories/search/`, temporal, tag, and people search variants
- **User Management**: `/v1/users/{id}/stats`, `/v1/users/current`
- **Health**: `/v1/ping/`, `/v1/health/`

## Important Changes Made
- Created complete REST API wrapper around existing Memory class
- Implemented secure API key generation and validation system
- Added comprehensive error handling and HTTP status codes
- Created Pydantic models for request/response validation
- Added CORS support for web dashboard integration
- Maintained identical interface to self-hosted solution

## Notes
- API keys are hashed using SHA256 before storage
- User info includes usage tracking (last_used, usage_count)
- FastAPI provides automatic OpenAPI documentation at `/docs`
- Production deployment should include rate limiting and HTTPS
- Authentication system designed to integrate with dashboard UI
