# SelfMemory MCP Server - Unified Authentication

The unified MCP server (`main_unified.py`) supports **both OAuth 2.1 and API key authentication** on the same endpoint, providing a seamless experience for all clients.

## Features

- ✅ **OAuth 2.1** - Modern authentication for VS Code, Cursor, Windsurf, ChatGPT
- ✅ **API Key** - Legacy authentication for backward compatibility
- ✅ **Single Endpoint** - Both methods use the same URL
- ✅ **Automatic Detection** - Server detects authentication type
- ✅ **Same Tools** - All tools work with both auth methods

## Installation

### OAuth 2.1 (Recommended)

Clients automatically discover and use OAuth:

```bash
npx install-mcp https://selfmemory.example.com/mcp --client claude
```

**What happens:**
1. Client fetches `/.well-known/oauth-authorization-server`
2. Client initiates OAuth flow
3. User authenticates via browser
4. Client receives OAuth token
5. Client uses token automatically

### API Key (Legacy)

For clients that don't support OAuth or need manual configuration:

```bash
npx install-mcp https://selfmemory.example.com/mcp \
  --client claude \
  --oauth no \
  --header "Authorization: Bearer sk_im_YOUR_API_KEY"
```

**What happens:**
1. `--oauth no` disables OAuth discovery
2. Client sends API key with every request
3. Server validates API key via Core server

## How It Works

### Authentication Detection

The server automatically detects authentication type:

1. **JWT Token** (3 parts with dots) → OAuth validation via Hydra
2. **Other format** → API key validation via Core server

```python
# Example token formats:
oauth_token = "eyJhbGc...XYZ.abc123...def.ghi789..."  # JWT format
api_key = "sk_im_liaeOAgw0N4pP8r70Vo68N4tcvBpjcxogIphhCOJ"  # API key
```

### Unified Middleware Flow

```
┌─────────────────────────────────────────────────────┐
│          Client Request to /mcp                      │
│     Authorization: Bearer <token>                    │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│      UnifiedAuthMiddleware                           │
│  1. Extract Bearer token                             │
│  2. Detect token type (JWT vs API key)               │
│  3. Validate accordingly:                            │
│     - JWT → Hydra introspection                      │
│     - API key → Core server validation               │
│  4. Create unified token context                     │
│  5. Store in ContextVar for tools                    │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│              MCP Tools                               │
│  - search(query)                                     │
│  - add(content)                                      │
│  - fetch(id)                                         │
│                                                       │
│  All tools work with both auth methods!              │
└─────────────────────────────────────────────────────┘
```

### Token Context Structure

Both authentication methods result in the same context:

```python
{
    "auth_type": "oauth" | "api_key",
    "user_id": "user_abc123",
    "project_id": "proj_xyz789",
    "organization_id": "org_def456",
    "scopes": ["memories:read", "memories:write"],
    "raw_token": "<original_token>"
}
```

## Configuration

### Environment Variables

```bash
# MCP Server
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8080
MCP_SERVER_URL=https://selfmemory.example.com

# Core Server (for API key validation)
SELFMEMORY_API_HOST=http://localhost:8081

# Hydra OAuth 2.1 (for OAuth validation)
HYDRA_ADMIN_URL=http://localhost:4445
HYDRA_PUBLIC_URL=http://localhost:4444

# Optional
MCP_DEV_MODE=false  # Enable auto-reload for development
```

## Running the Server

### Development Mode

```bash
cd selfmemory-core/selfmemory-mcp
export MCP_DEV_MODE=true
python main_unified.py
```

### Production Mode

```bash
cd selfmemory-core/selfmemory-mcp
python main_unified.py
```

### Using Make (if available)

```bash
cd selfmemory-core
make runmcp-unified  # Add this target to Makefile
```

## Endpoints

### MCP Endpoint
- `POST /mcp` - Main MCP endpoint (requires authentication)

### OAuth Discovery (for OAuth clients)
- `GET /.well-known/oauth-protected-resource` - Resource metadata
- `GET /.well-known/oauth-authorization-server` - Authorization server metadata
- `GET /.well-known/openid-configuration` - OIDC discovery
- `POST /register` - Dynamic client registration

### Tools (both auth methods)
- `search(query: str)` - Search memories
- `add(content: str)` - Add new memory
- `fetch(id: str)` - Fetch memory by ID

## Migration Guide

### From OAuth-only (`main_oauth.py`)

The unified server is a **drop-in replacement**:

1. Update your run script to use `main_unified.py`
2. Keep all environment variables the same
3. Existing OAuth clients continue working

### From API-key-only (`main.py`)

API key clients work without changes:

1. Deploy `main_unified.py` on the same URL
2. Existing API key clients continue working
3. New clients can use OAuth automatically

### Side-by-Side Deployment

Run both servers during migration:

```bash
# OAuth server (existing)
python main_oauth.py  # Port 8080

# API key server (existing)
python main.py  # Port 8081

# Unified server (new)
python main_unified.py  # Port 8082
```

Then gradually migrate clients to the unified server.

## Troubleshooting

### OAuth clients not discovering server

**Problem:** Client says "OAuth discovery failed"

**Solution:** Ensure `/.well-known/oauth-authorization-server` returns 200 OK

```bash
curl https://your-server/mcp/.well-known/oauth-authorization-server
```

### API key clients getting 401

**Problem:** API key clients receive "Invalid API key"

**Solution:** 
1. Verify API key format: `sk_im_...` or `im_...`
2. Check Core server is running: `SELFMEMORY_API_HOST`
3. Test API key directly:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        https://core-server/api/memories
   ```

### Token context not available in tools

**Problem:** Tools throw "No authentication context available"

**Solution:** Ensure middleware is registered before mounting MCP:

```python
# Correct order:
app.add_middleware(UnifiedAuthMiddleware, ...)  # First
app.mount("/mcp", mcp.streamable_http_app())    # Second
```

## Security Considerations

### OAuth 2.1
- ✅ Short-lived access tokens
- ✅ Refresh token rotation
- ✅ PKCE required
- ✅ Scope-based authorization
- ✅ Centralized revocation

### API Keys
- ⚠️ Long-lived credentials
- ⚠️ No automatic expiration
- ⚠️ Manual revocation required
- ✅ User-controlled generation
- ✅ Per-project isolation

**Recommendation:** Migrate to OAuth 2.1 for better security.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           MCP Clients                                │
│  - VS Code (OAuth)                                   │
│  - Cursor (OAuth)                                    │
│  - Legacy tools (API key)                            │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│      Unified MCP Server (main_unified.py)            │
│  ┌──────────────────────────────────────────────┐   │
│  │  UnifiedAuthMiddleware                        │   │
│  │  - Detects OAuth vs API key                   │   │
│  │  - Validates via appropriate method           │   │
│  └──────────────────────────────────────────────┘   │
│                                                       │
│  ┌──────────────────────────────────────────────┐   │
│  │  MCP Tools                                    │   │
│  │  - search, add, fetch                         │   │
│  └──────────────────────────────────────────────┘   │
└─────────┬─────────────────────────┬─────────────────┘
          │                         │
          ▼                         ▼
┌─────────────────┐    ┌──────────────────────────┐
│  Hydra OAuth    │    │  Core Server             │
│  - JWT tokens   │    │  - API key validation    │
│  - Scopes       │    │  - User/project info     │
└─────────────────┘    └──────────────────────────┘
```

## Testing

### Test OAuth Authentication

```bash
# 1. Get OAuth token via browser flow
# 2. Test with token
curl -H "Authorization: Bearer <oauth_token>" \
     https://your-server/mcp
```

### Test API Key Authentication

```bash
# 1. Generate API key in dashboard
# 2. Test with API key
curl -H "Authorization: Bearer sk_im_YOUR_API_KEY" \
     https://your-server/mcp
```

### Test with MCP Inspector

```bash
# OAuth mode
npx @modelcontextprotocol/inspector \
  https://your-server/mcp

# API key mode  
npx @modelcontextprotocol/inspector \
  https://your-server/mcp \
  --header "Authorization: Bearer sk_im_YOUR_API_KEY"
```

## Benefits

### For Users
- ✅ Choose authentication method that works best
- ✅ Smooth migration path from API keys to OAuth
- ✅ No changes needed to existing clients
- ✅ Same tools regardless of auth method

### For Developers
- ✅ Single codebase to maintain
- ✅ Unified tool implementations
- ✅ Easier deployment and monitoring
- ✅ Better logging and debugging

### For Operations
- ✅ One server to deploy
- ✅ One endpoint to monitor
- ✅ Simplified infrastructure
- ✅ Easier scaling and load balancing

## Support

For issues or questions:
1. Check logs: `journalctl -u selfmemory-mcp -f`
2. Test authentication methods separately
3. Verify environment variables
4. Review token context in logs

## Future Enhancements

Potential improvements:
- [ ] Rate limiting per auth method
- [ ] Authentication method analytics
- [ ] Automatic API key to OAuth migration
- [ ] Token rotation for long-lived sessions
- [ ] Multi-factor authentication support