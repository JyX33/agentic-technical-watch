# Reddit Technical Watcher - API Documentation

This directory contains comprehensive API documentation for all Reddit Technical Watcher agents and their endpoints.

## API Documentation Structure

- **[Agent Cards](./agent-cards.md)** - A2A Agent Card specifications for service discovery
- **[Authentication](./authentication.md)** - API authentication methods and security schemes
- **[Endpoints Reference](./endpoints/)** - Detailed endpoint documentation for each agent
- **[Error Codes](./error-codes.md)** - Complete error code reference and troubleshooting
- **[OpenAPI Specifications](./openapi/)** - Machine-readable API specifications
- **[Rate Limits](./rate-limits.md)** - API rate limiting policies and best practices

## Quick Start

### Base URLs

Each agent runs on its own port in development:

```
Coordinator Agent:   http://localhost:8000
Retrieval Agent:     http://localhost:8001
Filter Agent:        http://localhost:8002
Summarise Agent:     http://localhost:8003
Alert Agent:         http://localhost:8004
```

### Authentication

All agents support multiple authentication methods:

1. **API Key Authentication** (Recommended for services)
2. **Bearer Token Authentication** (For user-based access)
3. **No Authentication** (Development/internal only)

### Common Endpoints

All agents provide these standard endpoints:

- `GET /.well-known/agent.json` - Agent Card for A2A service discovery
- `GET /health` - Health check endpoint
- `GET /discover` - Service discovery for other agents
- `POST /a2a` - Main A2A JSON-RPC 2.0 endpoint
- `GET /skills` - List available agent skills
- `POST /skills/{skill_name}` - Direct skill invocation

## A2A Protocol Compliance

All agents implement Google's Agent-to-Agent (A2A) protocol:

- **JSON-RPC 2.0** based communication
- **Agent Cards** for service discovery
- **Standardized error codes** and responses
- **Task management** with unique IDs and status tracking
- **Metadata propagation** for request tracing

## Development vs Production

### Development Environment
- No authentication required by default
- Detailed error messages and stack traces
- CORS allows all origins
- Enhanced logging and debugging

### Production Environment
- Authentication required for all endpoints
- Sanitized error messages
- Restricted CORS origins
- Security headers enabled
- Rate limiting enforced

## Getting Help

- **Issues**: Report API issues in the project repository
- **Support**: Contact the operations team for production support
- **Documentation**: This documentation is updated with each release

---

*Last Updated: 2025-06-22*
*API Version: 1.0.0*
