# MCP (Model Context Protocol) Setup Guide

This guide explains how to use the MCP authentication implementation with Ory Hydra.

## What Was Implemented

✅ **Protected Resource Metadata Endpoint** - RFC 9728 compliant
✅ **Bearer Token Authentication** - Using Ory Hydra token introspection  
✅ **OAuth 2.1 Integration** - Full support for MCP authorization flow
✅ **Configuration Management** - Environment-based MCP settings

## Architecture

```
MCP Client (VS Code/Claude) 
    ↓
    ↓ 1. Request /.well-known/oauth-protected-resource
    ↓
SelfMemory Backend (Port 8081)
    ↓ 2. Client discovers Ory Hydra
    ↓
Ory Hydra (Port 4444/4445)
    ↓ 3. OAuth flow (login via dashboard)
    ↓
Dashboard (Port 3000) - Kratos login
    ↓ 4. Token issued
    ↓
MCP Client → Backend with Bearer token
    ↓ 5. Token validated via Hydra introspection
    ↓
Access granted to memory operations
```

## Configuration

### Required Environment Variables

Add these to your `selfmemory-core/.env` file:

```bash
# MCP Configuration
MCP_ENABLED=true
MCP_SERVER_URL=http://localhost:8081
HYDRA_PUBLIC_URL=http://127.0.0.1:4444
HYDRA_ADMIN_URL=http://127.0.0.1:4445
MCP_RESOURCE_DOCUMENTATION_URL=https://github.com/yourusername/selfmemory
```

### Hydra Configuration

Your Ory Hydra must have:
1. **Dynamic Client Registration** enabled (already configured in `ory-infrastructure/configs/hydra.yml`)
2. **Consent/Login URLs** pointing to your dashboard (`http://127.0.0.1:3000/auth/...`)
3. **CORS enabled** for MCP clients

## How It Works

### 1. Discovery Phase

When an MCP client connects to `http://localhost:8081`, it:

```http
GET /.well-known/oauth-protected-resource HTTP/1.1
Host: localhost:8081
```

Response:
```json
{
  "resource": "http://localhost:8081",
  "authorization_servers": ["http://127.0.0.1:4444"],
  "scopes_supported": ["mcp:tools", "mcp:resources"],
  "bearer_methods_supported": ["header"],
  "resource_signing_alg_values_supported": ["RS256"],
  "resource_documentation": "https://github.com/yourusername/selfmemory"
}
```

### 2. Authorization Phase

The MCP client:
1. Discovers Hydra's OAuth endpoints
2. Dynamically registers itself (or uses pre-registration)
3. Initiates OAuth authorization code flow with PKCE
4. User logs in via your dashboard (Kratos)
5. Hydra issues access token

### 3. API Access Phase

The MCP client includes the token in requests:

```http
POST /api/memories/search HTTP/1.1
Host: localhost:8081
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{
  "query": "find my notes about project X"
}
```

The backend:
1. Extracts bearer token
2. Calls Hydra introspection endpoint
3. Validates token is active
4. Checks audience matches server URL
5. Extracts user_id from token
6. Processes request with user context

## Testing

### Method 1: Manual Test with curl

1. Get an access token from Hydra (you'll need to complete OAuth flow manually)

2. Test the Protected Resource Metadata:
```bash
curl http://localhost:8081/.well-known/oauth-protected-resource
```

3. Test with bearer token:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8081/api/memories
```

### Method 2: VS Code MCP Client

1. Install VS Code MCP extension
2. Add MCP server configuration:
```json
{
  "mcpServers": {
    "selfmemory": {
      "url": "http://localhost:8081",
      "type": "http"
    }
  }
}
```

3. VS Code will handle the OAuth flow automatically

### Method 3: Claude Desktop

Add to Claude Desktop's MCP configuration:
```json
{
  "mcpServers": {
    "selfmemory": {
      "command": "mcp-client",
      "args": ["http://localhost:8081"]
    }
  }
}
```

## Next Steps

The current implementation provides the **authentication foundation**. To make this a complete MCP server, you'll need to:

### Phase 2: MCP Protocol Handler (Not Yet Implemented)

1. **Add JSON-RPC 2.0 Handler**
   - Create `/mcp` endpoint
   - Handle `initialize`, `tools/list`, `tools/call` requests
   
2. **Wrap Memory Operations as MCP Tools**
   - `search_memories` tool
   - `add_memory` tool
   - `list_memories` tool
   - `delete_memory` tool

3. **Example MCP Tool Definition**:
```python
{
  "name": "search_memories",
  "description": "Search through your personal memories",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum results"
      }
    },
    "required": ["query"]
  }
}
```

Would you like me to implement Phase 2 (MCP Protocol Handler)?

## Security Notes

⚠️ **Important Security Considerations**:

1. **Token Validation**: Always validates tokens via Hydra introspection
2. **Audience Checking**: Verifies token is intended for this server
3. **Scope Validation**: Checks required scopes (implement per-tool)
4. **Project Isolation**: User can only access their projects
5. **HTTPS Required**: Use HTTPS in production

## Troubleshooting

### "Token is not active"
- Token expired (check `expires_at`)
- Token was revoked
- Hydra not running

### "Audience mismatch"
- Token was issued for different resource
- Check `MCP_SERVER_URL` matches Hydra configuration

### "Authentication service unavailable"
- Hydra not running on port 4444/4445
- Network connectivity issues
- Check `HYDRA_ADMIN_URL` configuration

### "No Authorization header"
- MCP client not sending token
- OAuth flow not completed
- Check MCP client logs

## Current Limitations

1. **No MCP Protocol Handler**: Only OAuth authentication is implemented
2. **No Tool Definitions**: Memory operations not wrapped as MCP tools yet
3. **No Resource Endpoints**: MCP resources not implemented
4. **Testing Required**: No automated tests for MCP flow

## References

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [RFC 9728 - Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728)
- [OAuth 2.1](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13)
- [Ory Hydra Documentation](https://www.ory.sh/docs/hydra/)
