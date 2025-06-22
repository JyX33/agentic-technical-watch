# API Error Codes & Troubleshooting

Complete reference for all error codes returned by Reddit Technical Watcher agents, including causes and resolution steps.

## Error Response Format

All API errors follow a consistent JSON format:

```json
{
  "error": "Error type",
  "code": 400,
  "message": "Detailed error description",
  "details": {
    "field": "additional_context",
    "timestamp": "2025-06-22T10:30:00Z",
    "request_id": "req_123456789"
  }
}
```

## HTTP Status Codes

### 2xx Success

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `202 Accepted` - Request accepted for processing

### 4xx Client Errors

#### 400 Bad Request

**Cause:** Invalid request format or parameters

**Common Examples:**

```json
{
  "error": "Invalid request format",
  "code": 400,
  "message": "Request body must be valid JSON"
}
```

**Resolution:**

- Validate JSON syntax
- Check required parameters
- Verify parameter types

#### 401 Unauthorized

**Cause:** Missing or invalid authentication

**Common Examples:**

```json
{
  "error": "Authentication required",
  "code": 401,
  "message": "No valid authentication credentials provided"
}
```

**Resolution:**

- Add `X-API-Key` or `Authorization` header
- Verify API key/token validity
- Check authentication configuration

#### 403 Forbidden

**Cause:** Valid authentication but insufficient permissions

**Common Examples:**

```json
{
  "error": "Insufficient permissions",
  "code": 403,
  "message": "This operation requires administrator privileges"
}
```

**Resolution:**

- Check user permissions
- Verify API key scope
- Contact administrator

#### 404 Not Found

**Cause:** Endpoint or resource not found

**Common Examples:**

```json
{
  "error": "Skill not found",
  "code": 404,
  "message": "The skill 'invalid_skill' is not available on this agent"
}
```

**Resolution:**

- Check endpoint URL spelling
- Verify skill names using `/skills` endpoint
- Check agent type and capabilities

#### 422 Unprocessable Entity

**Cause:** Valid request format but invalid data

**Common Examples:**

```json
{
  "error": "Validation error",
  "code": 422,
  "message": "Parameter 'limit' must be between 1 and 100",
  "details": {
    "field": "limit",
    "value": 500,
    "constraint": "max:100"
  }
}
```

**Resolution:**

- Check parameter constraints
- Validate data types and ranges
- Review API documentation

#### 429 Too Many Requests

**Cause:** Rate limit exceeded

**Common Examples:**

```json
{
  "error": "Rate limit exceeded",
  "code": 429,
  "message": "Too many requests. Please try again later.",
  "details": {
    "retry_after": 60,
    "limit": 60,
    "remaining": 0,
    "reset": 1640995200
  }
}
```

**Resolution:**

- Wait for rate limit reset
- Implement exponential backoff
- Check rate limit headers
- Consider request optimization

### 5xx Server Errors

#### 500 Internal Server Error

**Cause:** Unexpected server error

**Common Examples:**

```json
{
  "error": "Internal server error",
  "code": 500,
  "message": "An unexpected error occurred while processing your request"
}
```

**Resolution:**

- Check server logs
- Retry request after delay
- Contact support if persistent

#### 502 Bad Gateway

**Cause:** Agent communication failure

**Common Examples:**

```json
{
  "error": "Agent communication failed",
  "code": 502,
  "message": "Unable to communicate with retrieval agent"
}
```

**Resolution:**

- Check agent service status
- Verify network connectivity
- Check service discovery

#### 503 Service Unavailable

**Cause:** Agent temporarily unavailable

**Common Examples:**

```json
{
  "error": "Service unavailable",
  "code": 503,
  "message": "Agent is temporarily unavailable",
  "details": {
    "retry_after": 30
  }
}
```

**Resolution:**

- Wait and retry request
- Check agent health status
- Verify resource availability

#### 504 Gateway Timeout

**Cause:** Agent response timeout

**Common Examples:**

```json
{
  "error": "Request timeout",
  "code": 504,
  "message": "Agent did not respond within the allowed time"
}
```

**Resolution:**

- Reduce request complexity
- Increase timeout configuration
- Check agent performance

## JSON-RPC 2.0 Error Codes

For A2A protocol endpoints (`/a2a`), JSON-RPC 2.0 error codes are used:

### Standard JSON-RPC Errors

#### -32700 Parse Error

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32700,
    "message": "Parse error",
    "data": "Invalid JSON format"
  },
  "id": null
}
```

#### -32600 Invalid Request

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": "Missing required field: method"
  },
  "id": null
}
```

#### -32601 Method Not Found

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": "Method 'invalid_method' is not supported"
  },
  "id": 1
}
```

#### -32602 Invalid Params

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Parameter 'message' is required"
  },
  "id": 1
}
```

#### -32603 Internal Error

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": "Database connection failed"
  },
  "id": 1
}
```

### Custom A2A Error Codes

#### -32001 Task Not Found

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Task not found",
    "data": "Task ID 'task_123' does not exist"
  },
  "id": 1
}
```

#### -32002 Task Already Cancelled

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32002,
    "message": "Task already cancelled",
    "data": "Task ID 'task_123' was previously cancelled"
  },
  "id": 1
}
```

#### -32003 Push Notification Not Supported

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32003,
    "message": "Push Notification is not supported"
  },
  "id": 1
}
```

#### -32004 Streaming Not Supported

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32004,
    "message": "Streaming not implemented yet"
  },
  "id": 1
}
```

## Agent-Specific Errors

### Retrieval Agent Errors

#### Reddit API Errors

```json
{
  "error": "Reddit API error",
  "code": 502,
  "message": "Reddit API rate limit exceeded",
  "details": {
    "reddit_error": "TOO_MANY_REQUESTS",
    "retry_after": 600
  }
}
```

#### Authentication Errors

```json
{
  "error": "Reddit authentication failed",
  "code": 401,
  "message": "Invalid Reddit API credentials"
}
```

### Filter Agent Errors

#### Relevance Calculation Errors

```json
{
  "error": "Relevance calculation failed",
  "code": 500,
  "message": "Unable to calculate content relevance score",
  "details": {
    "content_id": "post_123",
    "error_type": "semantic_analysis_failed"
  }
}
```

### Summarise Agent Errors

#### Gemini API Errors

```json
{
  "error": "Gemini API error",
  "code": 502,
  "message": "Gemini API request failed",
  "details": {
    "gemini_error": "RESOURCE_EXHAUSTED",
    "retry_after": 60
  }
}
```

#### Content Too Large

```json
{
  "error": "Content too large",
  "code": 413,
  "message": "Content exceeds maximum size for summarization",
  "details": {
    "max_size": 100000,
    "actual_size": 150000
  }
}
```

### Alert Agent Errors

#### Notification Delivery Errors

```json
{
  "error": "Notification delivery failed",
  "code": 502,
  "message": "Failed to deliver alert via Slack",
  "details": {
    "channel": "slack",
    "slack_error": "channel_not_found"
  }
}
```

#### Invalid Recipients

```json
{
  "error": "Invalid recipients",
  "code": 400,
  "message": "No valid recipients configured for email alerts"
}
```

### Coordinator Agent Errors

#### Workflow Errors

```json
{
  "error": "Workflow execution failed",
  "code": 500,
  "message": "Unable to complete workflow step",
  "details": {
    "workflow_id": "workflow_123",
    "failed_step": "filter_posts",
    "agent": "filter_agent"
  }
}
```

## Troubleshooting Guide

### General Troubleshooting Steps

1. **Check Request Format**

   ```bash
   # Validate JSON syntax
   echo '{"method":"test"}' | python -m json.tool
   ```

2. **Verify Authentication**

   ```bash
   # Test authentication
   curl -H "X-API-Key: your-key" http://localhost:8000/health
   ```

3. **Check Agent Status**

   ```bash
   # Check all agents
   curl http://localhost:8000/discover
   ```

4. **Review Logs**

   ```bash
   # Check agent logs
   docker-compose logs retrieval-agent
   ```

### Error-Specific Troubleshooting

#### Rate Limiting (429)

1. Check current rate limit status

   ```bash
   curl -I http://localhost:8000/health
   ```

2. Implement exponential backoff

   ```python
   import time
   import random

   def retry_with_backoff(func, max_retries=3):
       for attempt in range(max_retries):
           try:
               return func()
           except RateLimitError:
               wait_time = (2 ** attempt) + random.uniform(0, 1)
               time.sleep(wait_time)
       raise Exception("Max retries exceeded")
   ```

#### Service Unavailable (503)

1. Check agent health

   ```bash
   curl http://localhost:8001/health  # Retrieval agent
   curl http://localhost:8002/health  # Filter agent
   ```

2. Verify dependencies

   ```bash
   # Check Redis
   redis-cli ping

   # Check PostgreSQL
   pg_isready -h localhost -p 5432
   ```

#### Authentication Errors (401)

1. Verify environment variables

   ```bash
   echo $A2A_API_KEY
   echo $A2A_BEARER_TOKEN
   ```

2. Test authentication

   ```bash
   # API Key
   curl -H "X-API-Key: $A2A_API_KEY" http://localhost:8000/health

   # Bearer Token
   curl -H "Authorization: Bearer $A2A_BEARER_TOKEN" http://localhost:8000/health
   ```

## Monitoring & Alerting

### Error Rate Monitoring

Set up monitoring for error rates:

- 4xx errors > 5% of total requests
- 5xx errors > 1% of total requests
- Consecutive 503 errors > 3

### Log Analysis

Key error patterns to monitor:

- Authentication failures
- Rate limit violations
- Agent communication failures
- Database connection errors

### Alert Configuration

```yaml
# Example Prometheus alert rules
groups:
  - name: reddit_watcher_errors
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
```

---

*See also: [Authentication](./authentication.md), [Rate Limits](./rate-limits.md)*
