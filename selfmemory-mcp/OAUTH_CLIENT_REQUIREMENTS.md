# OAuth Client Requirements - RFC 8707 Resource Parameter

## Overview

This MCP server requires OAuth clients to include the **resource parameter** (RFC 8707) in all authorization and token requests. This is a **REQUIRED** feature per MCP Specification 2025-06-18, Section 4.5.

## What is the Resource Parameter?

The `resource` parameter identifies the target MCP server that the client wants to access. It prevents token misuse and confused deputy attacks by binding tokens to specific services.

## Client Implementation Requirements

### 1. Discover Resource URL

First, discover the protected resource metadata endpoint:

```bash
GET http://127.0.0.1:8080/.well-known/oauth-protected-resource
```

Response:
```json
{
  "resource": "http://127.0.0.1:8080",
  "authorization_servers": ["http://127.0.0.1:4444"],
  "scopes_supported": ["memories:read", "memories:write"],
  "bearer_methods_supported": ["header"]
}
```

### 2. Include Resource in Authorization Request

When initiating the OAuth flow, include the `resource` parameter:

```http
GET /oauth2/auth?response_type=code
  &client_id={your_client_id}
  &redirect_uri={your_redirect_uri}
  &scope=memories:read memories:write offline_access
  &code_challenge={pkce_challenge}
  &code_challenge_method=S256
  &resource=http://127.0.0.1:8080
  &state={random_state}
HTTP/1.1
Host: 127.0.0.1:4444
```

**Important**: The resource URL must match exactly (including no trailing slash).

### 3. Include Resource in Token Request

When exchanging the authorization code for tokens, include the `resource` parameter:

```http
POST /oauth2/token HTTP/1.1
Host: 127.0.0.1:4444
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code={authorization_code}
&redirect_uri={your_redirect_uri}
&client_id={your_client_id}
&code_verifier={pkce_verifier}
&resource=http://127.0.0.1:8080
```

### 4. Token Audience Validation

The resulting access token will contain an `aud` (audience) claim:

```json
{
  "aud": "http://127.0.0.1:8080",
  "sub": "user_id",
  "scope": "memories:read memories:write",
  "ext": {
    "project_id": "507f1f77bcf86cd799439011"
  }
}
```

The MCP server will **reject** tokens that:
- Don't have an `aud` claim
- Have an `aud` claim that doesn't match this server's resource URL

## Example: Python Client Implementation

```python
import httpx
from urllib.parse import urlencode

# Step 1: Discover resource metadata
metadata_response = httpx.get("http://127.0.0.1:8080/.well-known/oauth-protected-resource")
metadata = metadata_response.json()

resource_url = metadata["resource"]  # "http://127.0.0.1:8080"
auth_server = metadata["authorization_servers"][0]  # "http://127.0.0.1:4444"

# Step 2: Build authorization URL with resource parameter
auth_params = {
    "response_type": "code",
    "client_id": client_id,
    "redirect_uri": redirect_uri,
    "scope": "memories:read memories:write offline_access",
    "code_challenge": pkce_challenge,
    "code_challenge_method": "S256",
    "resource": resource_url,  # ← REQUIRED
    "state": generate_random_state(),
}

auth_url = f"{auth_server}/oauth2/auth?{urlencode(auth_params)}"
print(f"Navigate to: {auth_url}")

# Step 3: Exchange code for token with resource parameter
token_response = httpx.post(
    f"{auth_server}/oauth2/token",
    data={
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": pkce_verifier,
        "resource": resource_url,  # ← REQUIRED
    },
)

tokens = token_response.json()
access_token = tokens["access_token"]

# Step 4: Use token to call MCP server
mcp_response = httpx.post(
    f"{resource_url}/mcp",
    headers={
        "Authorization": f"Bearer {access_token}",
        "MCP-Protocol-Version": "2025-06-18",
    },
    json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1,
    },
)

print(mcp_response.json())
```

## VS Code MCP Extension

If you're using the VS Code MCP extension, ensure you're using a version that supports RFC 8707. The resource parameter should be included automatically based on the server's metadata endpoint.

## Troubleshooting

### Error: "Token audience mismatch"

**Cause**: The token was issued for a different service, or the resource parameter wasn't included.

**Solution**: 
1. Verify you're including `resource=http://127.0.0.1:8080` in both authorization and token requests
2. Check that the resource URL matches exactly (no trailing slash)
3. Decode the JWT token and verify the `aud` claim matches

### Error: "Token missing required claim: aud"

**Cause**: Hydra didn't include the audience claim in the token, likely because the resource parameter wasn't provided.

**Solution**: 
1. Ensure Hydra config has `resource_indicators.enabled: true`
2. Include the `resource` parameter in your OAuth requests
3. Restart Hydra after configuration changes

## Security Benefits

Including the resource parameter provides:

✅ **Token Binding**: Tokens are cryptographically bound to this specific MCP server  
✅ **Confused Deputy Protection**: Prevents attackers from reusing tokens on other services  
✅ **Audit Trail**: Clear visibility into which service a token was issued for  
✅ **MCP Spec Compliance**: Meets security requirements of MCP 2025-06-18  

## References

- **MCP Specification**: https://spec.modelcontextprotocol.io/specification/2025-06-18/
- **RFC 8707**: Resource Indicators for OAuth 2.0 - https://www.rfc-editor.org/rfc/rfc8707.html
- **RFC 9728**: OAuth 2.0 Protected Resource Metadata - https://datatracker.ietf.org/doc/html/rfc9728

## Configuration Files Changed

As part of implementing RFC 8707 support, the following files were updated:

1. **`ory-infrastructure/configs/hydra.yml`** - Added `resource_indicators.enabled: true`
2. **`selfmemory-core/selfmemory-mcp/config.py`** - Added `resource_url` property to HydraConfig
3. **`selfmemory-core/selfmemory-mcp/oauth/metadata.py`** - Updated to use canonical resource URL

## Support

For issues or questions, refer to:
- MCP_OAUTH_FIXES.md - Complete implementation guide
- Ory Hydra docs: https://www.ory.sh/docs/hydra
