# Authentication & Security

The Reddit Technical Watcher API supports multiple authentication methods to ensure secure access to agent endpoints and protect sensitive operations.

## Authentication Methods

### 1. API Key Authentication (Recommended)

API Key authentication is the recommended method for service-to-service communication.

**Header Format:**

```http
X-API-Key: your-api-key-here
```

**Example Request:**

```bash
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/skills/health_check
```

**Configuration:**

```env
A2A_API_KEY=your-secure-api-key-here
```

### 2. Bearer Token Authentication

Bearer token authentication is suitable for user-based access and temporary tokens.

**Header Format:**

```http
Authorization: Bearer your-token-here
```

**Example Request:**

```bash
curl -H "Authorization: Bearer your-token" \
     http://localhost:8000/skills/orchestrate_workflow
```

**Configuration:**

```env
A2A_BEARER_TOKEN=your-bearer-token-here
JWT_SECRET=your-jwt-secret-key
```

### 3. No Authentication (Development Only)

For development and testing, authentication can be disabled.

**⚠️ Warning:** Never use in production environments.

**Configuration:**

```env
A2A_API_KEY=
A2A_BEARER_TOKEN=
```

## Security Configuration

### Environment Variables

All authentication configuration is managed through environment variables:

```env
# API Key Authentication
A2A_API_KEY=your-secure-api-key-here

# Bearer Token Authentication
A2A_BEARER_TOKEN=your-bearer-token-here
JWT_SECRET=your-jwt-secret-key

# Security Settings
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
RATE_LIMIT_BURST_LIMIT=10
MAX_CONTENT_LENGTH=10485760  # 10MB
```

### Security Headers

When `SECURITY_HEADERS_ENABLED=true`, these headers are automatically added:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
```

### Rate Limiting

API rate limiting prevents abuse and ensures service availability:

- **Per-minute limit**: 60 requests per IP address
- **Per-hour limit**: 1000 requests per IP address
- **Burst limit**: 10 requests in 10 seconds per IP
- **Whitelist**: `127.0.0.1` and `::1` are exempt

**Rate limit headers:**

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

### CORS Configuration

Cross-Origin Resource Sharing (CORS) settings:

**Development:**

```env
CORS_ALLOWED_ORIGINS=["*"]  # Allows all origins
```

**Production:**

```env
CORS_ALLOWED_ORIGINS=["https://yourdomain.com", "https://api.yourdomain.com"]
```

## Authentication Errors

### Common Error Responses

**Missing Authentication:**

```json
{
  "error": "Authentication required",
  "code": 401,
  "message": "No valid authentication credentials provided"
}
```

**Invalid API Key:**

```json
{
  "error": "Invalid API key",
  "code": 401,
  "message": "The provided API key is invalid or expired"
}
```

**Invalid Bearer Token:**

```json
{
  "error": "Invalid token",
  "code": 401,
  "message": "The bearer token is invalid or expired"
}
```

**Rate Limit Exceeded:**

```json
{
  "error": "Rate limit exceeded",
  "code": 429,
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

## Security Best Practices

### For API Keys

1. **Generate Strong Keys**

   ```bash
   # Generate a secure API key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Rotate Regularly**
   - Change API keys every 90 days
   - Use automated rotation systems
   - Monitor key usage patterns

3. **Secure Storage**
   - Never commit keys to version control
   - Use environment variables or secret management
   - Encrypt keys at rest

4. **Scope Limitations**
   - Use different keys for different services
   - Implement IP whitelisting when possible
   - Monitor and log key usage

### For Bearer Tokens

1. **JWT Token Validation**

   ```python
   # Example JWT validation
   import jwt

   def validate_token(token, secret):
       try:
           payload = jwt.decode(token, secret, algorithms=['HS256'])
           return payload
       except jwt.ExpiredSignatureError:
           raise AuthenticationError("Token expired")
       except jwt.InvalidTokenError:
           raise AuthenticationError("Invalid token")
   ```

2. **Token Expiration**
   - Set appropriate expiration times
   - Implement refresh token mechanics
   - Use short-lived tokens for sensitive operations

### For Production Deployment

1. **Enable All Security Features**

   ```env
   SECURITY_HEADERS_ENABLED=true
   RATE_LIMIT_REQUESTS_PER_MINUTE=60
   CORS_ALLOWED_ORIGINS=["https://yourdomain.com"]
   ```

2. **Use HTTPS Only**
   - Configure TLS certificates
   - Redirect HTTP to HTTPS
   - Use HSTS headers

3. **Monitor Security Events**
   - Log authentication failures
   - Monitor rate limit violations
   - Set up alerts for suspicious activity

## Testing Authentication

### Development Testing

```bash
# Test without authentication (development)
curl http://localhost:8000/health

# Test with API key
curl -H "X-API-Key: test-key" \
     http://localhost:8000/skills/health_check

# Test with bearer token
curl -H "Authorization: Bearer test-token" \
     http://localhost:8000/skills/health_check
```

### Production Testing

```bash
# Health check (usually public)
curl https://api.yourdomain.com/health

# Authenticated endpoint
curl -H "X-API-Key: your-production-key" \
     https://api.yourdomain.com/skills/orchestrate_workflow

# Test rate limiting
for i in {1..100}; do
  curl -H "X-API-Key: your-key" \
       https://api.yourdomain.com/health
done
```

## Troubleshooting

### Common Issues

1. **Authentication Not Working**
   - Check environment variable spelling
   - Verify key/token format
   - Check request headers

2. **Rate Limiting Issues**
   - Check current rate limit status
   - Verify IP whitelisting
   - Implement exponential backoff

3. **CORS Problems**
   - Check allowed origins configuration
   - Verify preflight requests
   - Check browser developer tools

### Debug Commands

```bash
# Check authentication configuration
curl -v http://localhost:8000/.well-known/agent.json

# Test rate limiting
curl -v -H "X-API-Key: test" \
     http://localhost:8000/health

# Check security headers
curl -I http://localhost:8000/health
```

---

*See also: [Error Codes](./error-codes.md), [Rate Limits](./rate-limits.md)*
