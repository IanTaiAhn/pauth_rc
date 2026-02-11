# Authentication & Security Layer

This document describes the authentication, CORS, and rate limiting implementation for P-Auth RC.

## Overview

The authentication layer addresses three critical HIPAA compliance issues:
- **CRITICAL-3**: No authentication on any endpoint
- **CRITICAL-2**: CORS not environment-driven
- **HIGH-5**: No rate limiting

## Authentication Methods

P-Auth RC supports **two authentication modes** that can be used interchangeably:

### 1. JWT Bearer Tokens (User Sessions)

Best for: Web applications, mobile apps, user-facing interfaces

**How to use:**
```bash
# Include JWT token in Authorization header
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/extract_patient_chart
```

**Token format:**
- Algorithm: HS256 (HMAC with SHA-256)
- Default expiration: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- Claims: `sub` (username), `user_id`, `scopes`, `exp` (expiration)

**Generating tokens:**
```python
from app.middleware.auth import create_access_token
from datetime import timedelta

token = create_access_token(
    data={"sub": "username", "user_id": "123", "scopes": ["read", "write"]},
    expires_delta=timedelta(minutes=30)
)
```

### 2. API Key Authentication (Service-to-Service)

Best for: Backend services, automated scripts, integrations

**How to use:**
```bash
# Include API key in X-API-Key header
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/api/extract_patient_chart
```

**Configuration:**
- API keys are stored in the `API_KEYS` environment variable
- Format: comma-separated list (e.g., `API_KEYS=key1,key2,key3`)
- Keys are validated against this list on every request

**Generating API keys:**
```python
import secrets
api_key = secrets.token_urlsafe(32)
print(f"Generated API key: {api_key}")
```

## Protected Endpoints

All endpoints that handle PHI (Protected Health Information) or sensitive operations require authentication. The following endpoints are protected:

### Prior Authorization Router (`/api`)
- `POST /api/extract_patient_chart` - Extract patient chart data (PHI)
  - Rate limit: 50/hour
  - Auth required: YES

### Documents Router (`/api`)
- `POST /api/upload_document` - Upload policy documents
  - Rate limit: 100/hour
  - Auth required: YES
- `GET /api/list_uploaded_docs` - List uploaded documents
  - Rate limit: 200/hour
  - Auth required: YES
- `DELETE /api/delete_uploaded_doc/{filename}` - Delete document
  - Rate limit: 100/hour
  - Auth required: YES

### Authorization Router (`/api`)
- `POST /api/compare_json_objects` - Evaluate PA request
  - Rate limit: 100/hour
  - Auth required: YES
- `POST /api/compare_json_objects/report` - Generate PA report
  - Rate limit: 100/hour
  - Auth required: YES

### RAG Router (`/api`)
- `POST /api/extract_policy_rules` - Extract policy rules
  - Rate limit: 200/hour
  - Auth required: YES
- `DELETE /api/delete_index/{name}` - Delete FAISS index
  - Rate limit: 50/hour
  - Auth required: YES
- `GET /api/list_indexes` - List available indexes
  - Rate limit: 200/hour
  - Auth required: YES

### Normalization Router (`/api/normalize`)
- `POST /api/normalize/patient` - Normalize patient data (PHI)
  - Rate limit: 200/hour
  - Auth required: YES
- `POST /api/normalize/policy` - Normalize policy data
  - Rate limit: 200/hour
  - Auth required: YES
- `POST /api/normalize/both` - Normalize both datasets
  - Rate limit: 200/hour
  - Auth required: YES

### Public Endpoints (No Auth Required)
- `GET /` - Root endpoint with basic info
  - Rate limit: 10/minute
- `GET /health` - Health check (no rate limit, for monitoring)

## CORS Configuration

CORS (Cross-Origin Resource Sharing) is now **environment-driven** and configured via environment variables.

### Environment Variables

```bash
# Allowed origins (comma-separated)
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://app.example.com

# Allow credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS=true
```

### Default Values

- Development: `http://localhost:5173` (Vite dev server)
- Production: Must be explicitly configured
- Credentials: Enabled by default (required for Bearer token auth)

### Production Setup

For production, set strict CORS origins:

```bash
# Production .env
CORS_ALLOWED_ORIGINS=https://app.yourcompany.com
CORS_ALLOW_CREDENTIALS=true
```

**Security note:** Never use `*` (wildcard) for production origins when handling PHI.

## Rate Limiting

Rate limiting protects against abuse and DoS attacks using token bucket algorithm.

### Configuration

```bash
# Default rate limit (unauthenticated users)
RATE_LIMIT_DEFAULT=100/hour

# Authenticated rate limit (higher)
RATE_LIMIT_AUTHENTICATED=1000/hour

# Storage backend
RATE_LIMIT_STORAGE_URI=memory://  # Use redis:// for distributed systems
```

### How It Works

1. **Identifier Selection:**
   - Authenticated users: Uses `user_id` or `api_key`
   - Unauthenticated users: Uses IP address

2. **Per-Endpoint Limits:**
   - Each endpoint has its own rate limit decorator
   - PHI endpoints have stricter limits (50-100/hour)
   - Read-only endpoints are more permissive (200/hour)

3. **Response on Limit Exceeded:**
   ```json
   {
     "detail": "Rate limit exceeded: 100 per 1 hour"
   }
   ```
   HTTP Status: 429 (Too Many Requests)

### Distributed Rate Limiting (Production)

For multi-instance deployments, use Redis:

```bash
# Install Redis
pip install redis

# Configure Redis storage
RATE_LIMIT_STORAGE_URI=redis://localhost:6379
```

## Implementation Details

### Adding Authentication to New Endpoints

When creating a new endpoint that handles PHI:

```python
from fastapi import APIRouter, Depends, Request
from app.middleware.auth import require_authentication, TokenData
from app.middleware.rate_limit import limiter
from typing import Optional

router = APIRouter()

@router.post("/my_endpoint")
@limiter.limit("100/hour")  # Add rate limiting
async def my_endpoint(
    request: Request,  # Required for rate limiting
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
    jwt_user, api_key = auth

    # Your endpoint logic here
    return {"message": "success"}
```

### Optional Authentication

For endpoints that work with or without auth (different behavior/limits):

```python
from app.middleware.auth import optional_authentication

@router.get("/my_public_endpoint")
async def my_endpoint(
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(optional_authentication)
):
    jwt_user, api_key = auth

    if jwt_user or api_key:
        # Authenticated behavior
        return {"data": "full_details"}
    else:
        # Unauthenticated behavior
        return {"data": "limited_details"}
```

## Testing Authentication

### Testing with JWT

```python
from app.middleware.auth import create_access_token

# Generate a test token
token = create_access_token(data={"sub": "testuser", "user_id": "123"})

# Use in requests
import requests
response = requests.post(
    "http://localhost:8000/api/extract_patient_chart",
    headers={"Authorization": f"Bearer {token}"},
    files={"file": open("test_chart.pdf", "rb")}
)
```

### Testing with API Key

```bash
# Set API key in .env
API_KEYS=test_key_abc123

# Use in curl
curl -H "X-API-Key: test_key_abc123" \
  http://localhost:8000/api/list_uploaded_docs
```

## Security Best Practices

### JWT Secret Key

**CRITICAL:** Never use default secret in production!

```bash
# Generate secure secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in .env
JWT_SECRET_KEY=your_generated_secret_here
```

### API Key Management

1. **Generation:** Use cryptographically secure random generators
   ```python
   import secrets
   api_key = secrets.token_urlsafe(32)
   ```

2. **Storage:** Store in environment variables, not in code
3. **Rotation:** Regularly rotate API keys (recommended: every 90 days)
4. **Revocation:** Remove compromised keys from `API_KEYS` list immediately

### CORS Configuration

1. **Never use wildcard (`*`) origins in production**
2. **Only allow specific, trusted domains**
3. **Keep `allow_credentials=true` only if needed**
4. **Document all allowed origins**

### Rate Limiting

1. **Adjust limits based on usage patterns**
2. **Use Redis for distributed systems**
3. **Monitor rate limit violations (add logging)**
4. **Consider IP whitelisting for trusted services**

## Migration from Unauthenticated

If you have existing clients using the API without authentication:

1. **Phase 1:** Deploy authentication but don't enforce
   - Add `optional_authentication` to endpoints
   - Monitor which clients are authenticating

2. **Phase 2:** Warn unauthenticated clients
   - Return deprecation warnings in responses
   - Set enforcement deadline

3. **Phase 3:** Enforce authentication
   - Switch to `require_authentication`
   - Return 401 for unauthenticated requests

## Troubleshooting

### 401 Unauthorized

**Cause:** Invalid or missing authentication credentials

**Solutions:**
- Check that `Authorization` header or `X-API-Key` is present
- Verify JWT token is not expired
- Confirm API key is in `API_KEYS` environment variable
- Check that `JWT_SECRET_KEY` matches across all instances

### 429 Rate Limit Exceeded

**Cause:** Too many requests in time window

**Solutions:**
- Implement exponential backoff in client
- Request higher rate limits for production use
- Use authenticated requests (higher limits)
- Switch to Redis storage for accurate distributed counting

### CORS Errors

**Cause:** Origin not allowed or credentials not configured

**Solutions:**
- Add your frontend origin to `CORS_ALLOWED_ORIGINS`
- Ensure `CORS_ALLOW_CREDENTIALS=true` if using auth headers
- Check browser console for specific CORS error message
- Verify environment variables are loaded (`print(os.getenv('CORS_ALLOWED_ORIGINS'))`)

## Next Steps

This authentication layer addresses the immediate HIPAA compliance issues, but additional security work is required:

- **CRITICAL-1**: Implement encryption at rest for PHI files
- **CRITICAL-4**: Migrate from Groq to HIPAA-eligible LLM provider (AWS Bedrock)
- **CRITICAL-5**: Add audit logging for all PHI access
- **HIGH-2**: Configure HTTPS/TLS
- **HIGH-3**: Implement data retention policies

See the main `CLAUDE.md` for the complete HIPAA compliance roadmap.
