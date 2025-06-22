# Troubleshooting Guide

Comprehensive troubleshooting procedures for the Reddit Technical Watcher system.

## Quick Diagnosis

### System Health Check
```bash
# Quick system status
./scripts/health-check.sh

# All agent status
curl -s https://api.company.com/coordinator/discover | jq '.agents'

# Infrastructure status
docker-compose ps
```

### Common Issue Patterns

**🔴 System Completely Down**
- No response from any agent
- Load balancer returning 503
- Database connection failures
→ See: [System Failure](./system-failure.md)

**🟡 Partial Service Degradation**
- Some agents responding, others not
- Slow response times
- Intermittent failures
→ See: [Performance Issues](./performance-issues.md)

**🟠 External API Issues**
- Reddit API failures
- Gemini API errors
- Rate limiting problems
→ See: [External API Issues](./external-api-issues.md)

**🔵 Configuration Problems**
- Authentication failures
- Environment variable issues
- Database migration problems
→ See: [Configuration Issues](./configuration-issues.md)

## Troubleshooting Guides

### System-Level Issues
- **[System Failure](./system-failure.md)** - Complete system down scenarios
- **[Performance Issues](./performance-issues.md)** - Slow response times and resource problems
- **[Network Issues](./network-issues.md)** - Connectivity and communication problems

### Agent-Specific Issues
- **[Coordinator Agent](./coordinator-agent.md)** - Workflow orchestration problems
- **[Retrieval Agent](./retrieval-agent.md)** - Reddit API and data collection issues
- **[Filter Agent](./filter-agent.md)** - Content filtering and relevance problems
- **[Summarise Agent](./summarise-agent.md)** - AI summarization and Gemini API issues
- **[Alert Agent](./alert-agent.md)** - Notification delivery problems

### Infrastructure Issues
- **[Database Issues](./database-issues.md)** - PostgreSQL problems and solutions
- **[Redis Issues](./redis-issues.md)** - Service discovery and caching problems
- **[Docker Issues](./docker-issues.md)** - Container and orchestration problems

### External Dependencies
- **[External API Issues](./external-api-issues.md)** - Reddit, Gemini, and other API problems
- **[Configuration Issues](./configuration-issues.md)** - Environment and configuration problems
- **[Security Issues](./security-issues.md)** - Authentication and authorization problems

## Diagnostic Tools

### System Diagnostics
```bash
# Comprehensive system check
./scripts/system-diagnostics.sh

# Performance analysis
./scripts/performance-diagnostics.sh

# Network connectivity test
./scripts/network-diagnostics.sh
```

### Agent Diagnostics
```bash
# Agent health and metrics
./scripts/agent-diagnostics.sh [agent-name]

# A2A communication test
./scripts/a2a-diagnostics.sh

# Service discovery test
./scripts/discovery-diagnostics.sh
```

### Infrastructure Diagnostics
```bash
# Database health and performance
./scripts/database-diagnostics.sh

# Redis health and performance
./scripts/redis-diagnostics.sh

# Docker container analysis
./scripts/docker-diagnostics.sh
```

## Quick Fixes

### Restart Services
```bash
# Restart specific agent
docker-compose restart agent-name

# Restart all agents
docker-compose restart

# Full system restart
docker-compose down && docker-compose up -d
```

### Clear Caches
```bash
# Clear application caches
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/cache/clear"

# Clear Redis cache
docker exec redis-reddit-watcher redis-cli FLUSHALL

# Clear Docker cache
docker system prune -f
```

### Reset Connections
```bash
# Reset database connections
docker exec postgres-reddit-watcher psql -U postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'reddit_watcher' AND pid <> pg_backend_pid();"

# Reset agent service discovery
./scripts/reset-service-discovery.sh
```

## Escalation Criteria

### Immediate Escalation (P1)
- Complete system failure (no agents responding)
- Data corruption or loss
- Security breach indicators
- Critical business impact

### Standard Escalation (P2)
- Multiple agent failures
- Significant performance degradation
- External API complete failure
- Database connectivity issues

### Monitor and Fix (P3)
- Single agent intermittent issues
- Minor performance degradation
- Non-critical feature failures
- Warning-level alerts

## Log Analysis

### Application Logs
```bash
# Recent errors across all services
docker-compose logs --since=1h | grep -i "error\|exception\|fail"

# Specific agent logs
docker-compose logs agent-name --tail=100

# Filter by log level
docker-compose logs | grep "ERROR\|WARN"
```

### System Logs
```bash
# System journal
journalctl -u docker --since="1 hour ago"

# Docker daemon logs
journalctl -u docker.service --since="1 hour ago"

# System resource logs
dmesg | tail -50
```

### Performance Logs
```bash
# Check for out-of-memory events
dmesg | grep -i "killed process\|out of memory"

# Check for disk I/O issues
iostat -x 1 5

# Check network issues
netstat -i
```

## Monitoring and Metrics

### Key Metrics to Monitor
- **Response Times**: API endpoint response times
- **Error Rates**: 4xx and 5xx error percentages
- **Throughput**: Requests per second
- **Resource Usage**: CPU, memory, disk usage
- **External API Health**: Reddit/Gemini API status

### Grafana Dashboards
- **System Overview**: https://grafana.company.com/d/reddit-watcher-overview
- **Agent Performance**: https://grafana.company.com/d/reddit-watcher-agents
- **Infrastructure**: https://grafana.company.com/d/reddit-watcher-infra

### Prometheus Queries
```bash
# High error rate
rate(http_requests_total{status=~"5.."}[5m]) > 0.01

# High response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2

# High memory usage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.8
```

## Common Problems and Solutions

### Problem: Agents Not Registering in Service Discovery

**Symptoms:**
```bash
curl -s https://api.company.com/coordinator/discover | jq '.agents'
# Returns empty or missing agents
```

**Diagnosis:**
```bash
# Check Redis connectivity
docker exec redis-reddit-watcher redis-cli ping

# Check agent logs for registration errors
docker-compose logs agent-name | grep -i "register\|discovery"

# Check Redis keys
docker exec redis-reddit-watcher redis-cli keys "agent:*"
```

**Solution:**
```bash
# Restart Redis
docker-compose restart redis

# Re-register agents
./scripts/register-all-agents.sh

# Verify registration
curl -s https://api.company.com/coordinator/discover | jq '.agents'
```

### Problem: High Memory Usage

**Symptoms:**
- System becoming slow
- Out of memory errors
- High swap usage

**Diagnosis:**
```bash
# Check memory usage by container
docker stats --no-stream

# Check for memory leaks
ps aux --sort=-%mem | head -10

# Check system memory
free -h
```

**Solution:**
```bash
# Clear application caches
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/cache/clear"

# Restart memory-intensive services
docker-compose restart summarise-agent

# Add memory limits if needed
# Edit docker-compose.yml to add memory limits
```

### Problem: Database Connection Pool Exhaustion

**Symptoms:**
- "Too many connections" errors
- Database timeout errors
- Long response times

**Diagnosis:**
```bash
# Check active connections
docker exec postgres-reddit-watcher psql -U postgres -c "
  SELECT count(*) FROM pg_stat_activity
  WHERE state = 'active';"

# Check connection pool configuration
grep -r "pool_size\|max_overflow" config/
```

**Solution:**
```bash
# Kill idle connections
docker exec postgres-reddit-watcher psql -U postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle' AND state_change < now() - interval '5 minutes';"

# Restart services to reset pools
docker-compose restart
```

## Getting Help

### Internal Resources
- **Documentation**: This troubleshooting guide
- **Runbooks**: [Operational runbooks](../runbooks/)
- **Team Chat**: #reddit-watcher-support
- **On-Call**: +1-555-ONCALL

### External Resources
- **Docker Issues**: https://docs.docker.com/troubleshoot/
- **PostgreSQL Issues**: https://www.postgresql.org/docs/troubleshooting/
- **Redis Issues**: https://redis.io/docs/management/admin/
- **FastAPI Issues**: https://fastapi.tiangolo.com/tutorial/debugging/

### Escalation Process
1. **Try quick fixes** from this guide
2. **Check relevant troubleshooting guide** for specific issue
3. **Escalate to on-call** if unresolved in 30 minutes
4. **Follow incident response** procedures for critical issues

---

*For immediate assistance, contact the on-call engineer at +1-555-ONCALL*
