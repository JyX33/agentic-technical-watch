# Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide covers common issues, diagnostic procedures, and resolution steps for the Reddit Technical Watcher production system.

## Table of Contents

- [Quick Diagnostic Checklist](#quick-diagnostic-checklist)
- [Service-Specific Issues](#service-specific-issues)
- [Infrastructure Issues](#infrastructure-issues)
- [A2A Protocol Issues](#a2a-protocol-issues)
- [Performance Issues](#performance-issues)
- [External Dependencies](#external-dependencies)
- [Data Issues](#data-issues)
- [Security Issues](#security-issues)

## Quick Diagnostic Checklist

### 30-Second Health Check

```bash
# Run this first for any issue
echo "=== Quick System Status ==="
docker-compose -f docker-compose.prod.yml ps
echo -e "\n=== Service Health ==="
for port in 8000 8001 8002 8003 8004; do
    echo -n "Port $port: "
    curl -f -s --max-time 5 http://localhost:$port/health > /dev/null && echo "✅ OK" || echo "❌ FAIL"
done
echo -e "\n=== Infrastructure ==="
echo -n "Database: "
docker-compose -f docker-compose.prod.yml exec db pg_isready > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL"
echo -n "Redis: "
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ping > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL"
echo -e "\n=== Resources ==="
echo "Memory: $(free -h | grep Mem | awk '{print $3"/"$2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3"/"$2" ("$5" used)"}')"
echo "Load: $(uptime | awk -F'load average:' '{print $2}')"
```

### Log Analysis Quick Commands

```bash
# Recent errors across all services
docker-compose -f docker-compose.prod.yml logs --since 1h | grep -i error | tail -10

# Service status summary
docker-compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}"

# Resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

## Service-Specific Issues

### Coordinator Agent Issues

**Problem: Coordinator Agent Won't Start**

*Symptoms:*
- Container exits immediately
- Health check fails
- Service discovery empty

*Diagnosis:*
```bash
# Check container logs
docker-compose -f docker-compose.prod.yml logs coordinator-agent

# Check configuration
docker-compose -f docker-compose.prod.yml config | grep -A 20 coordinator-agent

# Test dependencies
curl -f http://localhost:5432 || echo "Database unreachable"
curl -f http://localhost:6379 || echo "Redis unreachable"
```

*Resolution:*
```bash
# 1. Verify environment variables
grep -E "(DATABASE_URL|REDIS_URL|A2A_API_KEY)" .env.prod

# 2. Check database connectivity
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "SELECT 1;"

# 3. Check Redis connectivity
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ping

# 4. Restart with fresh state
docker-compose -f docker-compose.prod.yml stop coordinator-agent
docker-compose -f docker-compose.prod.yml rm -f coordinator-agent
docker-compose -f docker-compose.prod.yml up -d coordinator-agent

# 5. Monitor startup
docker-compose -f docker-compose.prod.yml logs -f coordinator-agent
```

**Problem: Workflow Execution Failures**

*Symptoms:*
- No recent workflow completions
- Agent communication timeouts
- Circuit breaker opening frequently

*Diagnosis:*
```bash
# Check workflow status
docker-compose -f docker-compose.prod.yml exec coordinator-agent python -c "
from reddit_watcher.config import get_settings
from reddit_watcher.models import WorkflowExecution
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

config = get_settings()
engine = create_engine(config.database_url)
Session = sessionmaker(bind=engine)
session = Session()

recent_workflows = session.query(WorkflowExecution).order_by(WorkflowExecution.created_at.desc()).limit(5).all()
for wf in recent_workflows:
    print(f'{wf.created_at}: {wf.status} - {wf.error_message or \"OK\"}')
"

# Check circuit breaker status
docker-compose -f docker-compose.prod.yml logs coordinator-agent | grep -i circuit

# Check agent discovery
curl -s http://localhost:8000/discover | jq '.agents | keys'
```

*Resolution:*
```bash
# 1. Reset circuit breakers
docker-compose -f docker-compose.prod.yml restart coordinator-agent

# 2. Check agent health
for port in 8001 8002 8003 8004; do
    curl -f http://localhost:$port/health || echo "Agent on port $port is unhealthy"
done

# 3. Restart unhealthy agents
docker-compose -f docker-compose.prod.yml restart retrieval-agent filter-agent summarise-agent alert-agent

# 4. Trigger manual workflow
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"manual trigger"}]}},"id":"manual"}' \
  http://localhost:8000/a2a
```

### Retrieval Agent Issues

**Problem: Reddit API Failures**

*Symptoms:*
- No new posts being retrieved
- Authentication errors
- Rate limit exceeded errors

*Diagnosis:*
```bash
# Check Reddit API credentials
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
from reddit_watcher.config import get_settings
config = get_settings()
print('Reddit Client ID:', config.reddit_client_id[:8] + '...' if config.reddit_client_id else 'Missing')
print('Reddit Secret:', 'Set' if config.reddit_client_secret else 'Missing')
print('User Agent:', config.reddit_user_agent)
"

# Test Reddit connectivity
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
import praw
from reddit_watcher.config import get_settings
config = get_settings()
try:
    reddit = praw.Reddit(
        client_id=config.reddit_client_id,
        client_secret=config.reddit_client_secret,
        user_agent=config.reddit_user_agent
    )
    print('Rate limit info:', reddit.auth.limits)
    print('API Status: OK')
except Exception as e:
    print('API Error:', str(e))
"

# Check for rate limiting
docker-compose -f docker-compose.prod.yml logs retrieval-agent | grep -i "rate"
```

*Resolution:*
```bash
# 1. Verify credentials are correct
# Check Reddit app configuration at https://www.reddit.com/prefs/apps

# 2. Wait for rate limit reset (if rate limited)
# Reddit rate limits reset every hour

# 3. Update user agent string (if blocked)
# Edit .env.prod to include version and contact info
REDDIT_USER_AGENT="Reddit Technical Watcher v1.0 by /u/YourUsername"

# 4. Restart with new configuration
docker-compose -f docker-compose.prod.yml restart retrieval-agent

# 5. Test manual retrieval
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.config import get_settings
import asyncio

async def test():
    config = get_settings()
    agent = RetrievalAgent(config)
    result = await agent.execute_skill('fetch_reddit_posts', {'topics': ['test']})
    print('Test result:', result)

asyncio.run(test())
"
```

### Filter Agent Issues

**Problem: Gemini API Failures**

*Symptoms:*
- All posts being marked as irrelevant
- API authentication errors
- Quota exceeded errors

*Diagnosis:*
```bash
# Check Gemini API key
docker-compose -f docker-compose.prod.yml exec filter-agent python -c "
from reddit_watcher.config import get_settings
config = get_settings()
print('Gemini API Key:', config.gemini_api_key[:8] + '...' if config.gemini_api_key else 'Missing')
"

# Test Gemini connectivity
docker-compose -f docker-compose.prod.yml exec filter-agent python -c "
import google.generativeai as genai
from reddit_watcher.config import get_settings
config = get_settings()
try:
    genai.configure(api_key=config.gemini_api_key)
    models = list(genai.list_models())
    print(f'Available models: {len(models)}')
    print('API Status: OK')
except Exception as e:
    print('API Error:', str(e))
"

# Check filtering results
docker-compose -f docker-compose.prod.yml logs filter-agent | grep -E "(relevance|score)" | tail -5
```

*Resolution:*
```bash
# 1. Verify API key is valid
# Check Google AI Studio: https://makersuite.google.com/app/apikey

# 2. Check quota usage
# Monitor usage in Google Cloud Console

# 3. Switch to fallback model if needed
# Edit .env.prod:
GEMINI_MODEL_PRIMARY=gemini-2.5-flash
GEMINI_MODEL_FALLBACK=gemini-pro

# 4. Restart with new configuration
docker-compose -f docker-compose.prod.yml restart filter-agent

# 5. Test manual filtering
docker-compose -f docker-compose.prod.yml exec filter-agent python -c "
from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.config import get_settings
import asyncio

async def test():
    config = get_settings()
    agent = FilterAgent(config)
    result = await agent.execute_skill('filter_content', {
        'posts': [{'title': 'Test Claude Code post', 'content': 'This is about Claude Code AI assistant'}],
        'topics': ['Claude Code']
    })
    print('Filter result:', result)

asyncio.run(test())
"
```

### Summarise Agent Issues

**Problem: Summarization Failures**

*Symptoms:*
- Empty summaries
- High memory usage
- Timeout errors

*Diagnosis:*
```bash
# Check memory usage
docker stats reddit_watcher_summarise_prod --no-stream

# Check recent summarization attempts
docker-compose -f docker-compose.prod.yml logs summarise-agent | grep -E "(summary|error)" | tail -10

# Check Gemini API status (shared with filter agent)
docker-compose -f docker-compose.prod.yml exec summarise-agent python -c "
import google.generativeai as genai
from reddit_watcher.config import get_settings
config = get_settings()
genai.configure(api_key=config.gemini_api_key)
models = list(genai.list_models())
print(f'Models available: {len(models)}')
"
```

*Resolution:*
```bash
# 1. Increase memory limits if needed
# Edit docker-compose.prod.yml:
# memory: 4G (increase from 2G)

# 2. Restart with more resources
docker-compose -f docker-compose.prod.yml up -d --force-recreate summarise-agent

# 3. Test with smaller batch size
docker-compose -f docker-compose.prod.yml exec summarise-agent python -c "
from reddit_watcher.agents.summarise_agent import SummariseAgent
from reddit_watcher.config import get_settings
import asyncio

async def test():
    config = get_settings()
    agent = SummariseAgent(config)
    result = await agent.execute_skill('generate_summary', {
        'posts': [{'title': 'Test', 'content': 'Short test content'}]
    })
    print('Summary result:', result)

asyncio.run(test())
"

# 4. Clear any stuck processes
docker-compose -f docker-compose.prod.yml restart summarise-agent
```

### Alert Agent Issues

**Problem: Notifications Not Sending**

*Symptoms:*
- No Slack messages received
- No emails received
- Alert delivery failures in logs

*Diagnosis:*
```bash
# Check notification configuration
docker-compose -f docker-compose.prod.yml exec alert-agent python -c "
from reddit_watcher.config import get_settings
config = get_settings()
print('Slack webhook configured:', bool(config.slack_webhook_url))
print('SMTP configured:', config.has_smtp_config())
print('Email recipients:', config.email_recipients)
"

# Test Slack webhook
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"Test message from Reddit Watcher troubleshooting"}' \
        "$SLACK_WEBHOOK_URL"
fi

# Check email configuration
docker-compose -f docker-compose.prod.yml logs alert-agent | grep -E "(smtp|email|slack)" | tail -5
```

*Resolution:*
```bash
# 1. Test SMTP connectivity
docker-compose -f docker-compose.prod.yml exec alert-agent python -c "
import smtplib
from reddit_watcher.config import get_settings
config = get_settings()
try:
    server = smtplib.SMTP(config.smtp_server, config.smtp_port)
    server.starttls()
    server.login(config.smtp_username, config.smtp_password)
    print('SMTP connection: OK')
    server.quit()
except Exception as e:
    print('SMTP error:', str(e))
"

# 2. Test Slack webhook manually
curl -X POST -H 'Content-type: application/json' \
    --data '{"text":"Manual test from troubleshooting"}' \
    "$SLACK_WEBHOOK_URL"

# 3. Check firewall/network restrictions
# SMTP typically uses port 587 or 465
# Slack webhooks use HTTPS (port 443)

# 4. Verify credentials and endpoints
# Check .env.prod for correct values

# 5. Restart alert agent
docker-compose -f docker-compose.prod.yml restart alert-agent

# 6. Test alert delivery
docker-compose -f docker-compose.prod.yml exec alert-agent python -c "
from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import get_settings
import asyncio

async def test():
    config = get_settings()
    agent = AlertAgent(config)
    result = await agent.execute_skill('send_alert', {
        'summary': 'Test alert from troubleshooting',
        'posts': [{'title': 'Test', 'url': 'http://test.com'}]
    })
    print('Alert result:', result)

asyncio.run(test())
"
```

## Infrastructure Issues

### Database Issues

**Problem: Database Connection Failures**

*Symptoms:*
- "Connection refused" errors
- Timeout errors
- Max connections exceeded

*Diagnosis:*
```bash
# Check database container status
docker-compose -f docker-compose.prod.yml ps db

# Check database logs
docker-compose -f docker-compose.prod.yml logs db | tail -20

# Check connection count
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT count(*) as active_connections,
       (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections
FROM pg_stat_activity WHERE state = 'active';"

# Check for locks
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
WHERE NOT blocked_locks.granted;"
```

*Resolution:*
```bash
# 1. Restart database if completely unresponsive
docker-compose -f docker-compose.prod.yml restart db

# 2. Kill long-running queries
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'active' AND query_start < now() - interval '5 minutes' AND query NOT LIKE '%pg_stat_activity%';"

# 3. Increase connection limit if needed (temporary)
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -c "ALTER SYSTEM SET max_connections = 200;"
docker-compose -f docker-compose.prod.yml restart db

# 4. Check for connection leaks in applications
docker-compose -f docker-compose.prod.yml logs | grep -i "connection" | tail -10

# 5. Monitor connection pool usage
watch 'docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"'
```

**Problem: Database Performance Issues**

*Symptoms:*
- Slow query responses
- High CPU usage on database
- Timeouts

*Diagnosis:*
```bash
# Check slow queries
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY total_time DESC LIMIT 10;"

# Check database size
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Check index usage
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_tup_read DESC;"
```

*Resolution:*
```bash
# 1. Run VACUUM and ANALYZE
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "VACUUM ANALYZE;"

# 2. Update statistics
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "ANALYZE;"

# 3. Check for missing indexes
# Run database migration to ensure all indexes are present
docker-compose -f docker-compose.prod.yml run --rm coordinator-agent uv run alembic upgrade head

# 4. Restart database for configuration changes
docker-compose -f docker-compose.prod.yml restart db

# 5. Monitor performance improvement
docker stats reddit_watcher_db_prod --no-stream
```

### Redis Issues

**Problem: Redis Connection or Memory Issues**

*Symptoms:*
- Service discovery failures
- "Out of memory" errors
- Connection timeouts

*Diagnosis:*
```bash
# Check Redis status
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info server

# Check memory usage
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info memory

# Check connected clients
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info clients

# Check keyspace
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info keyspace

# List agent registration keys
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" keys "agent:*"
```

*Resolution:*
```bash
# 1. Clear Redis cache if memory full
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" flushdb

# 2. Restart Redis
docker-compose -f docker-compose.prod.yml restart redis

# 3. Wait for agents to re-register
sleep 30
curl -s http://localhost:8000/discover | jq '.agents | length'

# 4. If agents don't re-register, restart them
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# 5. Monitor memory usage
watch 'docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info memory | grep used_memory_human'
```

### Network Issues

**Problem: Container Communication Failures**

*Symptoms:*
- Agents can't reach each other
- Database/Redis unreachable
- External API failures

*Diagnosis:*
```bash
# Check Docker networks
docker network ls
docker network inspect reddit_watcher_internal
docker network inspect reddit_watcher_external

# Test internal connectivity
docker-compose -f docker-compose.prod.yml exec coordinator-agent ping -c 3 db
docker-compose -f docker-compose.prod.yml exec coordinator-agent ping -c 3 redis
docker-compose -f docker-compose.prod.yml exec coordinator-agent ping -c 3 retrieval-agent

# Test external connectivity
docker-compose -f docker-compose.prod.yml exec retrieval-agent ping -c 3 8.8.8.8
docker-compose -f docker-compose.prod.yml exec retrieval-agent curl -I https://reddit.com

# Check port bindings
docker-compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Ports}}"
```

*Resolution:*
```bash
# 1. Recreate networks
docker-compose -f docker-compose.prod.yml down
docker network prune -f
docker-compose -f docker-compose.prod.yml up -d

# 2. Check firewall rules
sudo ufw status
sudo iptables -L

# 3. Verify DNS resolution
docker-compose -f docker-compose.prod.yml exec coordinator-agent nslookup db
docker-compose -f docker-compose.prod.yml exec coordinator-agent nslookup redis

# 4. Check for IP conflicts
docker network inspect reddit_watcher_internal | jq '.[0].IPAM.Config'

# 5. Restart networking stack if needed
sudo systemctl restart docker
docker-compose -f docker-compose.prod.yml up -d
```

## A2A Protocol Issues

### Service Discovery Problems

**Problem: Agents Not Registering**

*Symptoms:*
- Empty `/discover` endpoint
- Agents can't find each other
- Service discovery timeouts

*Diagnosis:*
```bash
# Check service discovery endpoint
curl -s http://localhost:8000/discover | jq .

# Check Redis for registrations
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" keys "agent:*"

# Check individual agent cards
for port in 8000 8001 8002 8003 8004; do
    echo "Port $port:"
    curl -s http://localhost:$port/.well-known/agent.json | jq '.name // "Error"'
done

# Check agent logs for registration errors
docker-compose -f docker-compose.prod.yml logs | grep -i "register\|discovery"
```

*Resolution:*
```bash
# 1. Clear Redis service discovery data
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" del agent:*

# 2. Restart Redis
docker-compose -f docker-compose.prod.yml restart redis

# 3. Restart all agents to re-register
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# 4. Wait for registration
sleep 30

# 5. Verify registration
curl -s http://localhost:8000/discover | jq '.agents | keys'

# 6. If still failing, check network connectivity
docker-compose -f docker-compose.prod.yml exec coordinator-agent ping -c 3 redis
```

### A2A Communication Failures

**Problem: JSON-RPC Errors**

*Symptoms:*
- "Method not found" errors
- Invalid request errors
- Timeout errors

*Diagnosis:*
```bash
# Test basic A2A communication
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"test"}]}},"id":"test"}' \
  http://localhost:8000/a2a

# Check A2A logs
docker-compose -f docker-compose.prod.yml logs | grep -E "(a2a|jsonrpc|A2A)"

# Test each agent's A2A endpoint
for port in 8000 8001 8002 8003 8004; do
    echo "Testing port $port:"
    curl -X POST -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"ping"}]}},"id":"ping"}' \
      http://localhost:$port/a2a
done
```

*Resolution:*
```bash
# 1. Verify A2A protocol implementation
# Check that all agents implement required methods

# 2. Restart agents with fresh state
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# 3. Test simple communication
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tasks/get","params":{"id":"test"},"id":"get-test"}' \
  http://localhost:8000/a2a

# 4. Check for authentication issues
# Verify A2A_API_KEY is consistent across all services

# 5. Monitor A2A traffic
docker-compose -f docker-compose.prod.yml logs -f | grep -i a2a
```

## Performance Issues

### High CPU Usage

**Symptoms:**
- System load > 4.0
- Container CPU usage > 80%
- Slow response times

*Diagnosis:*
```bash
# Check system load
uptime
top -bn1 | head -10

# Check container CPU usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemPerc}}"

# Check processes within containers
docker-compose -f docker-compose.prod.yml exec coordinator-agent ps aux
docker-compose -f docker-compose.prod.yml exec db ps aux
```

*Resolution:*
```bash
# 1. Identify CPU-intensive processes
top -p $(docker inspect reddit_watcher_db_prod --format '{{.State.Pid}}')

# 2. Restart high-CPU containers
docker-compose -f docker-compose.prod.yml restart summarise-agent  # Usually most CPU intensive

# 3. Scale horizontally if needed
docker-compose -f docker-compose.prod.yml up -d --scale summarise-agent=2

# 4. Optimize database queries
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT query, calls, total_time, mean_time FROM pg_stat_statements
WHERE mean_time > 500 ORDER BY total_time DESC LIMIT 5;"

# 5. Adjust CPU limits if needed
# Edit docker-compose.prod.yml to increase CPU limits
```

### High Memory Usage

**Symptoms:**
- Available memory < 1GB
- Container memory usage > 90%
- OOM killer events

*Diagnosis:*
```bash
# Check system memory
free -h
cat /proc/meminfo | grep -E "(MemAvailable|SwapFree)"

# Check container memory usage
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Check for memory leaks
docker-compose -f docker-compose.prod.yml logs | grep -i "memory\|oom"

# Check swap usage
swapon -s
cat /proc/swaps
```

*Resolution:*
```bash
# 1. Restart memory-intensive services
docker-compose -f docker-compose.prod.yml restart summarise-agent coordinator-agent

# 2. Clear caches
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" flushall
sync && echo 3 > /proc/sys/vm/drop_caches  # System cache

# 3. Clean up Docker resources
docker system prune -f
docker volume prune -f

# 4. Increase memory limits if needed
# Edit docker-compose.prod.yml

# 5. Scale to distribute load
docker-compose -f docker-compose.prod.yml up -d --scale filter-agent=2 --scale summarise-agent=2
```

### Disk Space Issues

**Symptoms:**
- Disk usage > 90%
- "No space left on device" errors
- Log rotation failures

*Diagnosis:*
```bash
# Check disk usage
df -h
du -sh /var/lib/docker
du -sh data/
du -sh /var/log/

# Check large files
find / -size +1G -type f 2>/dev/null | head -10

# Check Docker space usage
docker system df
```

*Resolution:*
```bash
# 1. Clean up Docker resources
docker system prune -a --volumes -f

# 2. Clean up old logs
docker-compose -f docker-compose.prod.yml logs --since 24h > recent_logs.txt
# Then truncate log files

# 3. Clean up old backups
find database_backups/ -name "*.gz" -mtime +7 -delete

# 4. Rotate logs
sudo logrotate -f /etc/logrotate.conf

# 5. Move data to larger volume if needed
# Consider expanding disk or moving to external storage
```

## External Dependencies

### Reddit API Issues

**Problem: Reddit API Rate Limiting or Failures**

*Symptoms:*
- 429 "Too Many Requests" errors
- 403 "Forbidden" errors
- Connection timeouts

*Diagnosis:*
```bash
# Check Reddit API status
curl -I https://www.reddit.com/api/v1/me

# Check rate limit headers in logs
docker-compose -f docker-compose.prod.yml logs retrieval-agent | grep -i "rate\|limit"

# Test API credentials
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
import praw
from reddit_watcher.config import get_settings
config = get_settings()
reddit = praw.Reddit(
    client_id=config.reddit_client_id,
    client_secret=config.reddit_client_secret,
    user_agent=config.reddit_user_agent
)
print('Rate limit info:', reddit.auth.limits)
"
```

*Resolution:*
```bash
# 1. Wait for rate limit reset (if rate limited)
# Reddit rate limits typically reset every hour

# 2. Reduce polling frequency temporarily
# Edit monitoring interval in .env.prod
MONITORING_INTERVAL_HOURS=6  # Increase from 4

# 3. Improve user agent string
REDDIT_USER_AGENT="Reddit Technical Watcher v1.0 by /u/YourUsername (Contact: your-email@domain.com)"

# 4. Implement exponential backoff
# This should be handled in the retrieval agent code

# 5. Consider Reddit Premium API if available
# For higher rate limits
```

### Google Gemini API Issues

**Problem: Gemini API Quota or Performance Issues**

*Symptoms:*
- 429 "Quota exceeded" errors
- Slow response times
- Authentication failures

*Diagnosis:*
```bash
# Check Gemini API status
curl -H "Authorization: Bearer $GEMINI_API_KEY" \
  "https://generativelanguage.googleapis.com/v1/models"

# Check quota usage in logs
docker-compose -f docker-compose.prod.yml logs filter-agent summarise-agent | grep -i "quota\|limit"

# Test API key
docker-compose -f docker-compose.prod.yml exec filter-agent python -c "
import google.generativeai as genai
from reddit_watcher.config import get_settings
config = get_settings()
genai.configure(api_key=config.gemini_api_key)
models = list(genai.list_models())
print(f'Available models: {len(models)}')
"
```

*Resolution:*
```bash
# 1. Switch to fallback model
# Edit .env.prod:
GEMINI_MODEL_PRIMARY=gemini-2.5-flash

# 2. Reduce request frequency
# Implement batching or caching

# 3. Check Google Cloud Console for quota
# Increase quotas if possible

# 4. Implement request queuing
# To stay within rate limits

# 5. Consider alternative models
# Fallback to different model if needed
```

## Data Issues

### Database Corruption

**Problem: Data Integrity Issues**

*Symptoms:*
- Query errors
- Constraint violations
- Inconsistent data

*Diagnosis:*
```bash
# Check database integrity
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';" | while read schema table; do
    echo "Checking $table..."
    docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "SELECT count(*) FROM $table;" || echo "❌ $table has issues"
done

# Check for constraint violations
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE NOT validated;"

# Check for orphaned records
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT count(*) FROM reddit_posts WHERE subreddit_id NOT IN (SELECT id FROM subreddits);"
```

*Resolution:*
```bash
# 1. Run database consistency checks
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
VACUUM ANALYZE;
REINDEX DATABASE reddit_watcher;
"

# 2. Fix constraint violations
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
-- Example: Clean up orphaned records
DELETE FROM reddit_posts WHERE subreddit_id NOT IN (SELECT id FROM subreddits);
"

# 3. Restore from backup if corruption is severe
./deploy_production.sh backup  # Create current backup first
./deploy_production.sh rollback  # Restore from previous backup

# 4. Re-run migrations to ensure schema consistency
docker-compose -f docker-compose.prod.yml run --rm coordinator-agent uv run alembic upgrade head

# 5. Verify data integrity after fixes
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    count(*) as total_posts,
    count(DISTINCT subreddit_id) as unique_subreddits,
    max(created_at) as latest_post
FROM reddit_posts;"
```

### Missing or Outdated Data

**Problem: No Recent Data or Stale Information**

*Symptoms:*
- No posts newer than several hours
- Empty workflow results
- Stale monitoring data

*Diagnosis:*
```bash
# Check data freshness
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    max(created_at) as latest_post,
    count(*) as total_posts,
    count(*) FILTER (WHERE created_at > now() - interval '1 hour') as recent_posts
FROM reddit_posts;"

# Check workflow execution history
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    max(created_at) as latest_workflow,
    count(*) as total_workflows,
    count(*) FILTER (WHERE status = 'completed') as successful_workflows
FROM workflow_executions;"

# Check agent activity
docker-compose -f docker-compose.prod.yml logs --since 2h retrieval-agent | grep -i "fetch\|reddit"
```

*Resolution:*
```bash
# 1. Trigger manual data collection
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"trigger data collection"}]}},"id":"manual"}' \
  http://localhost:8000/a2a

# 2. Check if retrieval agent is working
docker-compose -f docker-compose.prod.yml logs retrieval-agent | tail -20

# 3. Verify Reddit API connectivity
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
import praw
from reddit_watcher.config import get_settings
config = get_settings()
reddit = praw.Reddit(
    client_id=config.reddit_client_id,
    client_secret=config.reddit_client_secret,
    user_agent=config.reddit_user_agent
)
subreddit = reddit.subreddit('test')
for post in subreddit.new(limit=1):
    print(f'Latest post: {post.title} at {post.created_utc}')
"

# 4. Check monitoring schedule
docker-compose -f docker-compose.prod.yml exec coordinator-agent python -c "
from reddit_watcher.config import get_settings
config = get_settings()
print(f'Monitoring interval: {config.monitoring_interval_hours} hours')
print(f'Topics: {config.reddit_topics}')
"

# 5. Restart data collection workflow
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent
```

## Security Issues

### Unauthorized Access Attempts

**Problem: Suspicious Access Patterns**

*Symptoms:*
- Multiple 401/403 errors
- Unusual traffic patterns
- Failed authentication attempts

*Diagnosis:*
```bash
# Check for authentication failures
docker-compose -f docker-compose.prod.yml logs | grep -E "(401|403|unauthorized|authentication)" | tail -20

# Check access patterns
docker-compose -f docker-compose.prod.yml logs | grep -E "GET|POST" | awk '{print $1, $7}' | sort | uniq -c | sort -nr | head -10

# Check for unusual IP addresses
# (If behind reverse proxy, check X-Forwarded-For headers)
docker-compose -f docker-compose.prod.yml logs traefik | grep -E "GET|POST" | head -20

# Check system authentication logs
sudo grep -i "failed\|invalid" /var/log/auth.log | tail -10
```

*Resolution:*
```bash
# 1. Block suspicious IPs (if identified)
sudo ufw deny from [suspicious-ip]

# 2. Rotate API keys if compromised
# Generate new keys in .env.prod
# Restart services with new keys

# 3. Enable additional logging
# Add more detailed access logging to reverse proxy

# 4. Implement rate limiting
# Configure Traefik or add application-level rate limiting

# 5. Monitor and alert on security events
# Enhance monitoring rules for security incidents
```

### Configuration Exposure

**Problem: Sensitive Configuration Exposed**

*Symptoms:*
- API keys in logs
- Configuration files accessible
- Environment variables exposed

*Diagnosis:*
```bash
# Check for exposed secrets in logs
docker-compose -f docker-compose.prod.yml logs | grep -E "(password|key|secret|token)" | head -10

# Check file permissions
ls -la .env.prod
ls -la docker-compose.prod.yml

# Check for secrets in container environment
docker-compose -f docker-compose.prod.yml exec coordinator-agent env | grep -E "(PASSWORD|KEY|SECRET|TOKEN)"

# Check web endpoints for configuration exposure
curl -s http://localhost:8000/config 2>/dev/null || echo "Config endpoint not exposed"
```

*Resolution:*
```bash
# 1. Secure file permissions
chmod 600 .env.prod
chmod 644 docker-compose.prod.yml

# 2. Rotate exposed credentials immediately
# Generate new passwords/keys for any exposed credentials
# Update .env.prod with new values

# 3. Review and clean logs
# Remove sensitive information from log files
# Configure log filtering to prevent future exposure

# 4. Restart services with new credentials
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 5. Audit configuration management
# Ensure no secrets are committed to version control
# Review access controls for configuration files
```

---

## Emergency Contacts and Escalation

### Quick Reference

**System Commands:**
```bash
# Emergency stop all services
docker-compose -f docker-compose.prod.yml down

# Emergency restart
./deploy_production.sh deploy

# Check system status
./deploy_production.sh status

# Create emergency backup
./deploy_production.sh backup

# View all logs
docker-compose -f docker-compose.prod.yml logs --since 1h
```

**Key Ports:**
- 8000: Coordinator Agent
- 8001: Retrieval Agent
- 8002: Filter Agent
- 8003: Summarise Agent
- 8004: Alert Agent
- 3000: Grafana
- 9090: Prometheus

**Critical Files:**
- `.env.prod`: Production configuration
- `docker-compose.prod.yml`: Service definitions
- `deploy_production.sh`: Deployment automation
- `data/`: Persistent data volumes

For issues not covered in this guide, escalate according to the procedures in the Disaster Recovery runbook.
