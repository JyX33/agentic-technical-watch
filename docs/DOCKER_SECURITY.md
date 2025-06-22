# Docker Security Configuration

This document explains the secure Docker Compose configuration implemented for the Reddit Technical Watcher project.

## Overview

The Docker Compose configuration has been completely redesigned with security as the primary concern, following industry best practices for production containerized deployments.

## Security Improvements Implemented

### 1. **Database Security**
- ✅ **No default passwords**: Requires strong passwords via environment variables
- ✅ **SCRAM-SHA-256 authentication**: PostgreSQL uses secure authentication method
- ✅ **Dedicated database user**: `reddit_watcher_user` instead of default `postgres`
- ✅ **Connection limits**: Database user limited to 20 connections max
- ✅ **Read-only monitoring user**: Separate user for monitoring tools

### 2. **Redis Security**
- ✅ **Password authentication**: Redis requires password for all connections
- ✅ **Persistence configuration**: Secure data persistence with AOF
- ✅ **No external exposure**: Redis only accessible via internal network

### 3. **Network Security**
- ✅ **Custom networks**: Two isolated networks (internal/external)
- ✅ **Network segmentation**: Database and Redis on internal-only network
- ✅ **Subnet isolation**: Custom IP ranges for network isolation
- ✅ **Minimal exposure**: Only necessary services exposed externally

### 4. **Container Security**
- ✅ **Non-root users**: All services run as non-privileged users
- ✅ **Security options**: `no-new-privileges` prevents privilege escalation
- ✅ **Resource limits**: Memory and CPU limits prevent resource exhaustion
- ✅ **Alpine images**: Minimal attack surface with Alpine Linux
- ✅ **Multi-stage builds**: Production images without build dependencies

### 5. **Secret Management**
- ✅ **Environment variables**: All sensitive data via environment variables
- ✅ **Required variables**: Docker Compose fails without required secrets
- ✅ **No hardcoded secrets**: All credentials externalized
- ✅ **Development separation**: Separate credentials for dev/prod

## Configuration Files

### Production Configuration
- `docker-compose.yml` - Secure production configuration
- `.env.example` - Template with security placeholders
- `scripts/generate-secure-env.py` - Secure credential generation

### Development Configuration
- `docker-compose.dev.yml` - Development overrides
- `.env.dev` - Development-safe credentials

## Usage

### Production Deployment

1. **Generate secure credentials**:
   ```bash
   python scripts/generate-secure-env.py
   ```

2. **Add your API keys** to the generated `.env` file:
   ```bash
   # Edit .env and add your real API keys
   REDDIT_CLIENT_ID=your_actual_reddit_client_id
   REDDIT_CLIENT_SECRET=your_actual_reddit_client_secret
   GEMINI_API_KEY=your_actual_gemini_api_key
   ```

3. **Deploy securely**:
   ```bash
   docker-compose up --build -d
   ```

### Development Setup

1. **Use development configuration**:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up
   ```

2. **Development includes**:
   - Known development passwords (insecure but convenient)
   - Exposed database/Redis ports for debugging
   - Source code mounting for hot reloading
   - Placeholder API keys

## Network Architecture

```
┌─────────────────────────────────────────────────┐
│                 External Network                │
│            (172.21.0.0/16)                     │
│                                                 │
│  ┌─────────────┐  ┌─────────────┐             │
│  │ Coordinator │  │   Agents    │             │
│  │   :8000     │  │ :8001-8004  │             │
│  └─────────────┘  └─────────────┘             │
└─────────────┬───────────────────────────────────┘
              │
┌─────────────┼───────────────────────────────────┐
│             │     Internal Network              │
│             │    (172.20.0.0/16)               │
│             │                                   │
│  ┌─────────────┐            ┌─────────────┐    │
│  │ PostgreSQL  │            │    Redis    │    │
│  │  (no ports) │            │ (no ports)  │    │
│  └─────────────┘            └─────────────┘    │
└─────────────────────────────────────────────────┘
```

## Security Features

### Database Layer
- **Encryption**: SCRAM-SHA-256 authentication
- **Access Control**: User-specific connection limits
- **Audit Logging**: Statement logging enabled
- **Monitoring**: Read-only user for metrics collection

### Application Layer
- **Authentication**: A2A API key authentication
- **Authorization**: Service-specific environment variables
- **Resource Limits**: Per-service memory/CPU limits
- **Health Checks**: Comprehensive service health monitoring

### Infrastructure Layer
- **Network Isolation**: Internal-only database network
- **Container Security**: Non-root users, privilege restrictions
- **Data Persistence**: Secure volume mounting
- **Service Discovery**: Redis-based internal service registry

## Validation

The configuration includes automatic validation:

```bash
# Validate production configuration (should fail without .env)
docker-compose config

# Validate development configuration
docker-compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev config
```

## Monitoring

Health checks are configured for all services:
- **Database**: `pg_isready` with user validation
- **Redis**: Authenticated ping with password
- **Agents**: HTTP health endpoints
- **Startup**: Proper service dependency ordering

## Best Practices Implemented

1. **Fail-fast**: Missing environment variables cause immediate failure
2. **Least privilege**: Services run with minimal required permissions
3. **Defense in depth**: Multiple security layers (network, auth, resources)
4. **Separation of concerns**: Dev/prod credential separation
5. **Audit trail**: Comprehensive logging and monitoring
6. **Recovery**: Restart policies for service resilience

## Security Checklist

Before production deployment, verify:

- [ ] Strong passwords generated (32+ characters)
- [ ] API keys properly configured
- [ ] Database user not using default credentials
- [ ] Redis password authentication enabled
- [ ] Network isolation configured
- [ ] Resource limits appropriate for workload
- [ ] Health checks responding correctly
- [ ] Data directories have proper permissions
- [ ] No secrets in version control
- [ ] Environment files properly secured

## Emergency Procedures

### Credential Rotation
1. Generate new credentials: `python scripts/generate-secure-env.py`
2. Update `.env` file with new values
3. Restart services: `docker-compose restart`
4. Verify health: `docker-compose ps`

### Security Incident Response
1. Stop all services: `docker-compose down`
2. Review logs: `docker-compose logs`
3. Rotate all credentials
4. Update security configuration
5. Restart with monitoring

## Support

For security questions or issues:
1. Review this documentation
2. Check Docker Compose validation
3. Verify environment variable configuration
4. Consult application logs for authentication failures
