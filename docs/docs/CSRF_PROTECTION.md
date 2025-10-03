# CSRF Protection Implementation

## Overview

Cross-Site Request Forgery (CSRF) protection has been implemented for the SelfMemory REST API to protect session-based authentication from malicious cross-site requests.

## What is CSRF?

CSRF is an attack that tricks a user's browser into making unwanted requests to a web application where the user is authenticated. For example, a malicious website could attempt to make requests to your API using the user's session cookies.

## Implementation Details

### Backend Setup

The backend uses `fastapi-csrf-protect` library with the following configuration:

**Configuration (in `server/config.py`):**
```python
CSRF_SECRET_KEY: str = os.getenv("CSRF_SECRET_KEY", "")
CSRF_COOKIE_SECURE: bool = True  # Use secure cookies (HTTPS only)
CSRF_COOKIE_SAMESITE: str = "Strict"  # Prevent cross-site cookie sending
CSRF_COOKIE_HTTPONLY: bool = True  # Prevent JavaScript access to cookie
CSRF_HEADER_NAME: str = "X-CSRF-Token"
```

**Environment Variables (.env):**
```bash
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
CSRF_SECRET_KEY=your_generated_secret_key_here
CSRF_COOKIE_SECURE=true
CSRF_COOKIE_SAMESITE=Strict
```

### CSRF Token Endpoint

**GET `/api/csrf-token`**

Generates and returns a CSRF token. The token is also set as a secure HttpOnly cookie.

**Response:**
```json
{
  "csrf_token": "generated_token_here",
  "message": "CSRF token generated successfully"
}
```

### Using CSRF Protection

For state-changing operations (POST, PUT, DELETE), include the CSRF token in the `X-CSRF-Token` header:

```javascript
fetch('/api/memories', {
  method: 'POST',
  headers: {
    'Authorization': 'Session user_id',
    'X-CSRF-Token': csrfToken,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
})
```

## Important Considerations for REST APIs

### Current Implementation Status

The CSRF infrastructure is set up but **NOT YET ENFORCED** on endpoints to avoid breaking existing functionality. This allows for:

1. **Gradual Rollout**: Endpoints can be protected incrementally
2. **Backward Compatibility**: Existing clients continue to work
3. **Testing**: CSRF protection can be tested without disrupting production

### When to Use CSRF Protection

**CSRF Protection is ESSENTIAL for:**
- ✅ Session-based authentication (using cookies)
- ✅ Dashboard web application
- ✅ Any browser-based client

**CSRF Protection is NOT NEEDED for:**
- ❌ API key authentication (not cookie-based)
- ❌ Mobile apps using API keys
- ❌ Server-to-server API calls
- ❌ OAuth 2.0 Bearer tokens

### Our Multi-Auth Architecture

SelfMemory supports two authentication methods:

1. **Session Authentication** (Dashboard)
   - Uses `Authorization: Session <user_id>` header
   - Browser-based
   - **Requires CSRF protection**

2. **API Key Authentication** (SDK)
   - Uses `Authorization: sk_im_...` header
   - Not cookie-based
   - **Does not need CSRF protection**

## Enabling CSRF Protection on Endpoints

To enable CSRF protection on an endpoint, add the `CsrfProtect` dependency:

```python
from fastapi_csrf_protect import CsrfProtect

@app.post("/api/memories")
async def add_memory(
    memory_create: MemoryCreate,
    auth: AuthContext = Depends(authenticate_api_key),
    csrf_protect: CsrfProtect = Depends()  # Add this
):
    # ONLY validate CSRF for session-based auth
    if auth.auth_type == "session":
        await csrf_protect.validate_csrf(request)

    # Rest of endpoint logic...
```

## Frontend Integration

### 1. Fetch CSRF Token on App Load

```typescript
async function initializeCsrfToken() {
  const response = await fetch('/api/csrf-token', {
    credentials: 'include'  // Important: include cookies
  });
  const data = await response.json();
  return data.csrf_token;
}
```

### 2. Include Token in Requests

```typescript
class ApiClient {
  private csrfToken: string | null = null;

  async initialize() {
    this.csrfToken = await initializeCsrfToken();
  }

  async makeRequest(url: string, options: RequestInit) {
    const headers = {
      ...options.headers,
      'X-CSRF-Token': this.csrfToken || ''
    };

    return fetch(url, { ...options, headers });
  }
}
```

### 3. Refresh Token on Expiry

If a request fails with 403 CSRF error, refresh the token and retry:

```typescript
async makeRequest(url: string, options: RequestInit) {
  let response = await fetch(url, options);

  if (response.status === 403) {
    const error = await response.json();
    if (error.error?.code === 'CSRF_TOKEN_INVALID') {
      // Refresh token and retry
      this.csrfToken = await initializeCsrfToken();
      response = await fetch(url, options);
    }
  }

  return response;
}
```

## Security Best Practices

### 1. HTTPS Only in Production
Always use HTTPS in production to protect tokens in transit:
```bash
CSRF_COOKIE_SECURE=true
```

### 2. Strict SameSite Policy
Use `Strict` or `Lax` to prevent cross-site attacks:
```bash
CSRF_COOKIE_SAMESITE=Strict
```

### 3. Rotate CSRF Secret
Periodically rotate the CSRF secret key and update in production.

### 4. Token Expiry
CSRF tokens should have reasonable expiry times (implemented by the library).

## Testing CSRF Protection

### Valid Request
```bash
# Get token
TOKEN=$(curl -s http://localhost:8081/api/csrf-token | jq -r .csrf_token)

# Make request with token
curl -X POST http://localhost:8081/api/memories \
  -H "Authorization: Session user_123" \
  -H "X-CSRF-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}]}'
```

### Invalid Request (Should Fail)
```bash
# Make request WITHOUT token
curl -X POST http://localhost:8081/api/memories \
  -H "Authorization: Session user_123" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}]}'

# Response: 403 Forbidden
# {"error": {"code": "CSRF_TOKEN_INVALID", ...}}
```

## Troubleshooting

### Token Validation Fails
1. Ensure cookies are being sent (`credentials: 'include'` in fetch)
2. Check CORS configuration allows credentials
3. Verify token is included in `X-CSRF-Token` header
4. Confirm CSRF_SECRET_KEY is set and consistent

### CORS Issues with Cookies
CORS must be configured to allow credentials:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Specific origin, not "*"
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Token Expires Too Quickly
Tokens are session-based and managed by the library. If issues persist, check:
- Server restarts (clears in-memory tokens)
- Secret key changes
- Cookie expiry settings

## Migration Path

### Phase 1: Setup (✅ Complete)
- Install library
- Add configuration
- Create token endpoint
- Add exception handler

### Phase 2: Frontend Integration (Current)
- Update API client to fetch tokens
- Include tokens in requests
- Handle token refresh

### Phase 3: Gradual Enforcement (Future)
- Enable protection on critical endpoints
- Monitor for issues
- Roll out to all endpoints

### Phase 4: Full Protection (Future)
- All state-changing endpoints protected
- Remove backward compatibility
- Document as required

## References

- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [fastapi-csrf-protect Documentation](https://github.com/aekasitt/fastapi-csrf-protect)
- [MDN: SameSite Cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)

## Status

**Current Status:** CSRF infrastructure ready, not yet enforced on endpoints

**Next Steps:**
1. Update frontend to fetch and include CSRF tokens
2. Test with dashboard application
3. Gradually enable protection on endpoints
4. Monitor and address any compatibility issues
