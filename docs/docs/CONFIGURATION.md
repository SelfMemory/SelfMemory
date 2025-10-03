# Configuration Guide

## Overview

SelfMemory follows Uncle Bob's Clean Code principles with a centralized configuration system. All configuration is managed through environment variables with sensible defaults.

**Core Principles:**
- ✅ **Single Source of Truth**: All config in one place (`server/config.py`)
- ✅ **No Hardcoded Values**: Everything configurable via environment variables
- ✅ **Type Safety**: Configuration classes with proper types
- ✅ **Validation**: Startup validation catches misconfigurations early
- ✅ **Zero Fallbacks**: Explicit errors instead of silent failures

## Quick Start

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your values:
```bash
# Minimum required for development
MONGODB_URI=mongodb://localhost:27017/selfmemory
VECTOR_STORE_PROVIDER=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
```

3. The server will validate configuration on startup and display errors if anything is misconfigured.

## Configuration Structure

Configuration is organized into logical sections:

```
config/
├── ErrorConfig          # Error handling and logging
├── DatabaseConfig       # MongoDB settings
├── SecurityConfig       # CSRF, rate limiting, tokens
├── PaginationConfig     # Pagination limits
├── EmailConfig          # SMTP settings
├── AppConfig           # Application settings
├── ServerConfig        # Server host/port
├── VectorStoreConfig   # Vector database settings
├── EmbeddingConfig     # Embedding model settings
├── ValidationConfig    # Input validation rules
├── RateLimitConfig     # Rate limit rules
├── HealthConfig        # Health check settings
├── MetricsConfig       # Monitoring settings
└── LoggingConfig       # Structured logging
```

## Configuration Sections

### Server Configuration

Controls where the FastAPI server runs:

```bash
# Host to bind to (0.0.0.0 = all interfaces)
SELFMEMORY_SERVER_HOST=0.0.0.0

# Port to listen on
SELFMEMORY_SERVER_PORT=8081
```

**Defaults:**
- Host: `0.0.0.0`
- Port: `8000`

---

### Application Configuration

General application settings:

```bash
# Environment: development, staging, or production
ENVIRONMENT=development

# Frontend URL (for CORS and invitation links)
FRONTEND_URL=http://localhost:3000

# Backend URL (for API references)
BACKEND_URL=http://localhost:8000

# Timezone settings
TIMEZONE=UTC
DEFAULT_DISPLAY_TIMEZONE=UTC
```

**Defaults:**
- Environment: `development`
- Frontend URL: `http://localhost:3000`
- Backend URL: `http://localhost:8000`
- Timezone: `UTC`

**Important:** Set `ENVIRONMENT=production` in production to enable security validations.

---

### Database Configuration (MongoDB)

MongoDB connection and pool settings:

```bash
# Connection URI
MONGODB_URI=mongodb://localhost:27017/selfmemory

# Connection timeout in seconds
MONGODB_TIMEOUT=30

# Maximum pool size
MONGODB_MAX_POOL_SIZE=100

# Transaction timeout in seconds
MONGODB_TRANSACTION_TIMEOUT=30

# Enable retry writes
MONGODB_RETRY_WRITES=true

# Write concern level
MONGODB_WRITE_CONCERN=majority
```

**Defaults:**
- URI: `mongodb://localhost:27017/selfmemory`
- Timeout: `30` seconds
- Max Pool Size: `100`
- Transaction Timeout: `30` seconds
- Retry Writes: `true`
- Write Concern: `majority`

**Production Notes:**
- Use authentication in production
- Consider replica sets for high availability
- Adjust pool size based on load

---

### Vector Store Configuration (Qdrant)

Vector database settings for memory storage:

```bash
# Provider name
VECTOR_STORE_PROVIDER=qdrant

# Qdrant host
QDRANT_HOST=localhost

# Qdrant port
QDRANT_PORT=6333

# Collection name
QDRANT_COLLECTION_NAME=selfmemory_memories
```

**Defaults:**
- Provider: Not set (required)
- Host: Not set (required)
- Port: Not set (required)
- Collection: `memories`

**Required:** You must configure these for the system to work.

---

### Embedding Configuration

Embedding model settings:

```bash
# Provider (e.g., "ollama", "openai")
EMBEDDING_PROVIDER=ollama

# Model name
EMBEDDING_MODEL=nomic-embed-text

# Ollama base URL (if using Ollama)
OLLAMA_BASE_URL=http://localhost:11434
```

**Defaults:**
- Provider: Not set (required)
- Model: Not set (required)
- Ollama Base URL: Not set (required if using Ollama)

---

### Security Configuration

CSRF protection, rate limiting, and token expiry:

```bash
# CSRF Secret Key - Generate with:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
CSRF_SECRET_KEY=your_secret_key_here

# CSRF Cookie Settings
CSRF_COOKIE_SECURE=true
CSRF_COOKIE_SAMESITE=strict

# Rate Limiting
RATE_LIMIT_ENABLED=false
RATE_LIMIT_STORAGE_URL=memory://

# Token Expiry
INVITATION_TOKEN_EXPIRY_HOURS=24
API_KEY_DEFAULT_EXPIRY_DAYS=90
```

**Defaults:**
- CSRF Cookie Secure: `true`
- CSRF Cookie SameSite: `Strict`
- Rate Limit Enabled: `false`
- Invitation Expiry: `24` hours
- API Key Expiry: No default (optional)

**Production Requirements:**
- MUST set `CSRF_SECRET_KEY`
- Enable rate limiting (`RATE_LIMIT_ENABLED=true`)
- Use Redis for rate limiting (`redis://localhost:6379`)

---

### Error Handling Configuration

Controls error visibility:

```bash
# Expose detailed errors to API responses
# MUST be false in production
ERROR_EXPOSE_DETAILS=false
```

**Defaults:**
- Expose Details: `false`

**Critical:** NEVER set to `true` in production. This would expose internal error details to users, creating a security vulnerability.

---

### Logging Configuration

Structured logging settings:

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log format: json or text
LOGGING_FORMAT=json

# Log sampling rate (0.0 to 1.0)
LOGGING_SAMPLE_RATE=1.0
```

**Defaults:**
- Level: `INFO`
- Format: `json`
- Sample Rate: `1.0` (log everything)

**Production Tips:**
- Use `INFO` or `WARNING` in production
- Use `json` format for easy parsing
- Consider sampling for high-volume logs

---

### Email/SMTP Configuration (Optional)

SMTP settings for sending invitation emails:

```bash
# SMTP Server
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Email Settings
SMTP_FROM_EMAIL=noreply@selfmemory.com
SMTP_FROM_NAME=SelfMemory
SMTP_USE_TLS=true
SMTP_TIMEOUT=10
```

**Defaults:**
- Port: `587`
- From Email: `noreply@selfmemory.com`
- From Name: `SelfMemory`
- Use TLS: `true`
- Timeout: `10` seconds

**Note:** If SMTP is not configured, invitation details are logged instead of emailed.

---

### Pagination Configuration

Default and maximum page sizes:

```bash
# Default items per page
PAGINATION_DEFAULT_LIMIT=10

# Maximum items per page
PAGINATION_MAX_LIMIT=100
```

**Defaults:**
- Default Limit: `10`
- Max Limit: `100`

---

### Health Check Configuration

Health check behavior:

```bash
# Enable detailed checks
HEALTH_ENABLE_DETAILED_CHECKS=true

# Timeout for health checks
HEALTH_TIMEOUT_SECONDS=5

# Memory threshold for warnings
HEALTH_MEMORY_THRESHOLD_MB=900
```

**Defaults:**
- Enable Detailed: `true`
- Timeout: `5` seconds
- Memory Threshold: `900` MB

---

### Metrics Configuration

Prometheus metrics endpoint:

```bash
# Enable metrics endpoint
METRICS_ENABLED=false
```

**Defaults:**
- Enabled: `false`

**Note:** Enable in production for monitoring. Metrics available at `/metrics`.

---

## Validation Rules

Input validation is configured in `ValidationConfig`:

### Organization Names
- Min Length: 2 characters
- Max Length: 100 characters
- Pattern: Letters, numbers, spaces, hyphens, underscores

### Project Names
- Min Length: 2 characters
- Max Length: 100 characters
- Pattern: Letters, numbers, spaces, hyphens, underscores

### Tags
- Min Length: 1 character
- Max Length: 50 characters
- Pattern: Letters, numbers, hyphens, underscores

### Memory Content
- Max Length: 10,000 characters

---

## Rate Limits

Rate limiting rules in `RateLimitConfig`:

| Endpoint | Limit | Description |
|----------|-------|-------------|
| Invitation Create | 5/minute | Prevent spam invitations |
| Invitation Accept | 3/minute | Prevent abuse |
| Memory Create | 20/minute | Reasonable creation rate |
| Memory Read | 60/minute | Higher limit for reads |
| Memory Search | 30/minute | Search operations |
| Project Create | 10/minute | Project creation |
| Organization Create | 10/minute | Org creation |
| Default | 120/minute | All other operations |

---

## Configuration Validation

The server validates configuration on startup:

### Required Checks
- ✅ MongoDB URI is set
- ✅ Rate limit storage URL (if rate limiting enabled)
- ✅ Valid environment name (development/staging/production)

### Production Checks
- ✅ ERROR_EXPOSE_DETAILS must be false
- ✅ CSRF_SECRET_KEY must be set

**On Validation Failure:**
The server will log all errors and refuse to start:

```
==========================================
CONFIGURATION VALIDATION FAILED
==========================================
  ❌ MONGODB_URI is required
  ❌ CSRF_SECRET_KEY is required in production
==========================================
Please fix the configuration errors before starting the server.
```

---

## Environment-Specific Configuration

### Development

```bash
ENVIRONMENT=development
ERROR_EXPOSE_DETAILS=true  # OK in dev
RATE_LIMIT_ENABLED=false   # Disabled in dev
LOG_LEVEL=DEBUG            # Verbose logging
CSRF_SECRET_KEY=dev_key    # Simple key OK
```

### Staging

```bash
ENVIRONMENT=staging
ERROR_EXPOSE_DETAILS=false
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URL=redis://staging-redis:6379
LOG_LEVEL=INFO
CSRF_SECRET_KEY=<secure_key>
```

### Production

```bash
ENVIRONMENT=production
ERROR_EXPOSE_DETAILS=false  # REQUIRED
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URL=redis://prod-redis:6379
LOG_LEVEL=WARNING
CSRF_SECRET_KEY=<secure_key>  # REQUIRED
MONGODB_URI=mongodb://prod-cluster/selfmemory
```

---

## Accessing Configuration in Code

Configuration is accessed through the singleton `config` object:

```python
from server.config import config

# Access configuration values
host = config.server.HOST
port = config.server.PORT
db_uri = config.database.URI

# Check environment
if config.app.ENVIRONMENT == "production":
    # Production-specific logic
    pass

# Use validation rules
max_name_length = config.validation.ORG_NAME_MAX_LENGTH

# Use rate limits
memory_create_limit = config.rate_limit.MEMORY_CREATE
```

**Never:**
- ❌ Use `os.getenv()` directly in application code
- ❌ Hardcode values in business logic
- ❌ Create fallback mechanisms

**Always:**
- ✅ Use `config` object
- ✅ Let configuration errors fail explicitly
- ✅ Add new config values to `config.py`

---

## Adding New Configuration

To add a new configuration option:

1. **Add to appropriate config class** in `server/config.py`:
```python
class SecurityConfig:
    NEW_OPTION: bool = os.getenv("NEW_OPTION", "false").lower() == "true"
```

2. **Add to `.env.example`** with documentation:
```bash
# Description of what this does
NEW_OPTION=false
```

3. **Add validation** (if required):
```python
@classmethod
def validate(cls) -> list[str]:
    errors = []
    if not cls.security.NEW_OPTION and cls.app.ENVIRONMENT == "production":
        errors.append("NEW_OPTION required in production")
    return errors
```

4. **Use in code**:
```python
from server.config import config

if config.security.NEW_OPTION:
    # Your logic here
    pass
```

---

## Troubleshooting

### Server Won't Start

**Check validation errors:**
```bash
python -m server.main
```

Look for `CONFIGURATION VALIDATION FAILED` message.

### Configuration Not Loading

**Check .env file location:**
- Must be in project root
- Named exactly `.env`
- Not `.env.example`

**Check environment variables:**
```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('MONGODB_URI'))"
```

### Rate Limiting Issues

**If rate limiting not working:**
- Check `RATE_LIMIT_ENABLED=true`
- Check `RATE_LIMIT_STORAGE_URL` is set
- For development, use `memory://`
- For production, use `redis://host:port`

### Email Not Sending

**Check SMTP configuration:**
- All SMTP_* variables set
- Correct port (587 for TLS, 465 for SSL)
- Valid credentials
- Check logs for detailed error messages

---

## Security Best Practices

### Production Checklist

- [ ] `ENVIRONMENT=production`
- [ ] `ERROR_EXPOSE_DETAILS=false`
- [ ] Strong `CSRF_SECRET_KEY` (use secure random generation)
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] Redis for rate limiting (not memory://)
- [ ] HTTPS enabled (`CSRF_COOKIE_SECURE=true`)
- [ ] MongoDB authentication enabled
- [ ] Strong MongoDB credentials
- [ ] Firewall rules in place
- [ ] Regular backups configured

### Secret Management

**NEVER commit:**
- ❌ `.env` file
- ❌ Credentials
- ❌ API keys
- ❌ CSRF secrets

**DO:**
- ✅ Use `.env.example` for templates
- ✅ Use secret management tools in production
- ✅ Rotate secrets regularly
- ✅ Use environment variables in CI/CD

---

## Support

For configuration issues:
1. Check this documentation
2. Review `.env.example` for all options
3. Check server logs for validation errors
4. Review `server/config.py` for defaults

Remember: **Configuration errors fail fast and explicitly** - this is intentional and helps catch problems early!
