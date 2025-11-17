# Troubleshooting Guide - SelfMemory MCP Unified Server

## Common Issues and Solutions

### 1. HTTPS/HTTP Connection Error

**Error:**
```
Connection error: TypeError: fetch failed
[cause]: [Error: SSL routines:ssl3_get_record:wrong version number]
code: 'ERR_SSL_WRONG_VERSION_NUMBER'
```

**Cause:** Client is trying to connect via HTTPS but server is running on HTTP.

**Solutions:**

#### Solution A: Use HTTP URL (Recommended for Local Development)

Update your MCP client configuration to use `http://` instead of `https://`:

```json
{
  "mcpServers": {
    "selfmemory": {
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

For SSE/API key clients:
```bash
npx install-mcp http://127.0.0.1:8080/mcp \
  --client claude \
  --oauth no \
  --header "Authorization: Bearer YOUR_API_KEY"
```

#### Solution B: Enable HTTPS with Reverse Proxy (Production)

Use nginx or Caddy to provide HTTPS termination:

**Nginx configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name selfmemory.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /.well-known/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
    }
}
```

**Caddy configuration (automatic HTTPS):**
```
selfmemory.example.com {
    reverse_proxy /mcp/* 127.0.0.1:8080
    reverse_proxy /.well-known/* 127.0.0.1:8080
}
```

Then update client configuration:
```json
{
  "mcpServers": {
    "selfmemory": {
      "url": "https://selfmemory.example.com/mcp"
    }
  }
}
```

#### Solution C: Use Tailscale HTTPS (Easiest Production Setup)

Tailscale provides automatic HTTPS for your tailnet:

1. Install Tailscale
2. Enable HTTPS: `tailscale serve https /mcp http://127.0.0.1:8080/mcp`
3. Use your Tailscale hostname:
```json
{
  "mcpServers": {
    "selfmemory": {
      "url": "https://your-machine.tailnet.ts.net/mcp"
    }
  }
}
```

---

### 2. API Key Validation Error

**Error:**
```
❌ Authentication failed: Invalid API key: 'SelfMemoryClient' object has no attribute 'user_info'
```

**Cause:** This was a bug in the unified auth implementation (now fixed).

**Solution:** Update to latest version of `auth/unified_auth.py` which uses the `/api/v1/auth/validate` endpoint.

**Verification:**
```bash
# Test API key validation manually
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://127.0.0.1:8081/api/v1/auth/validate

# Should return:
# {
#   "user_id": "...",
#   "project_id": "...",
#   "organization_id": "..."
# }
```

---

### 3. OAuth Discovery Not Working

**Error:**
```
failed to initialize client: no valid token available, authorization required
```

**Cause:** OAuth clients cannot reach discovery endpoints.

**Diagnosis:**
```bash
# Test OAuth discovery
curl http://127.0.0.1:8080/.well-known/oauth-protected-resource
curl http://127.0.0.1:8080/.well-known/oauth-authorization-server
```

**Solutions:**

1. **Check server is running:**
```bash
curl http://127.0.0.1:8080/mcp
# Should return 401 with OAuth challenge
```

2. **Verify Hydra is accessible:**
```bash
curl http://127.0.0.1:4444/.well-known/openid-configuration
# Should return Hydra's OAuth configuration
```

3. **Check firewall/network:**
   - Ensure port 8080 is accessible
   - Check no VPN/firewall blocking localhost

---

### 4. Token Missing Project Context

**Error:**
```
❌ Token missing project context: user=xxx
```

**Cause:** OAuth token doesn't include `project_id` claim.

**Solution:** Ensure consent flow includes project selection:

1. **Check consent endpoint** passes `project_id` to Hydra
2. **Verify Hydra session** includes `ext.project_id`
3. **Test token introspection:**
```bash
curl -X POST http://127.0.0.1:4445/admin/oauth2/introspect \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "token=YOUR_TOKEN"

# Should include:
# {
#   "active": true,
#   "ext": {
#     "project_id": "..."
#   }
# }
```

---

### 5. MCP Protocol Version Error

**Error:**
```
Unsupported MCP protocol version: 2024-XX-XX
```

**Cause:** Client using unsupported protocol version.

**Solution:** Update `SUPPORTED_VERSIONS` in middleware:

```python
# middleware/unified_auth.py
SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05", "2024-XX-XX"]
```

Or update client to use supported version.

---

### 6. Scope Missing Error

**Error:**
```
Token missing required scope: memories:read
```

**Cause:** Client didn't request required scopes during OAuth flow.

**Solution:**

1. **For API keys:** Automatically get all scopes - no action needed

2. **For OAuth clients:** Ensure Dynamic Client Registration includes scopes:
```bash
# Check registered client scopes
curl http://127.0.0.1:4445/admin/clients/YOUR_CLIENT_ID
```

Should include: `memories:read memories:write`

3. **Re-register client if needed:**
```bash
# Delete old registration
curl -X DELETE http://127.0.0.1:4445/admin/clients/YOUR_CLIENT_ID

# Restart OAuth flow - will re-register with correct scopes
```

---

## Debugging Tips

### Enable Detailed Logging

```bash
# Set environment variable
export LOG_LEVEL=DEBUG
export MCP_DEV_MODE=true

# Run server
python main_unified.py
```

### Test Authentication Manually

**OAuth Token:**
```bash
# Get token via browser OAuth flow, then test:
curl -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
     http://127.0.0.1:8080/mcp

# Should return 200 (after MCP handshake)
```

**API Key:**
```bash
curl -H "Authorization: Bearer sk_im_YOUR_API_KEY" \
     http://127.0.0.1:8080/mcp

# Should return 200 (after MCP handshake)
```

### Check Token Format

```bash
# OAuth tokens are JWTs (3 parts):
echo "eyJhbGc...xyz" | cut -d. -f1,2,3 | wc -w
# Should output: 3

# API keys are simpler:
echo "sk_im_xyz..." | cut -d. -f1,2,3 | wc -w
# Should output: 1
```

### Verify Core Server

```bash
# Test Core server health
curl http://127.0.0.1:8081/api/v1/ping

# Test API key validation
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://127.0.0.1:8081/api/v1/auth/validate
```

### Test Token Detection

```python
# Python script to test token detection
from auth.unified_auth import looks_like_jwt

oauth_token = "eyJhbGc...xyz.abc...def.ghi..."
api_key = "sk_im_xyz123"

print(f"OAuth token is JWT: {looks_like_jwt(oauth_token)}")  # True
print(f"API key is JWT: {looks_like_jwt(api_key)}")  # False
```

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs:** Look for detailed error messages in server output
2. **Test components:** Verify Hydra, Core server, and MCP server separately
3. **Isolate auth method:** Test with API key first (simpler), then OAuth
4. **Review configuration:** Double-check all URLs and environment variables

### Useful Log Messages

**Successful OAuth Authentication:**
```
✅ Authenticated via oauth: user=xxx, project=yyy, scopes=[...]
```

**Successful API Key Authentication:**
```
✅ Authenticated via api_key: user=xxx, project=yyy, scopes=[...]
```

**Authentication Detection:**
```
✅ OAuth token validated: user=xxx, project=yyy
```
or
```
✅ API key validated: user=xxx, project=yyy