# System Health Monitoring Runbook

## Overview

This runbook provides comprehensive procedures for monitoring and maintaining the health of the Reddit Technical Watcher production system.

## Table of Contents

- [Health Check Procedures](#health-check-procedures)
- [Service Monitoring](#service-monitoring)
- [Performance Monitoring](#performance-monitoring)
- [Alert Response](#alert-response)
- [Troubleshooting Procedures](#troubleshooting-procedures)
- [Escalation Procedures](#escalation-procedures)

## Health Check Procedures

### Quick Health Assessment

**Immediate System Check (< 2 minutes):**

```bash
# 1. Check all services are running
docker-compose -f docker-compose.prod.yml ps

# 2. Test critical endpoints
curl -f http://localhost:8000/health && echo "✅ Coordinator OK"
curl -f http://localhost:8001/health && echo "✅ Retrieval OK"
curl -f http://localhost:8002/health && echo "✅ Filter OK"
curl -f http://localhost:8003/health && echo "✅ Summarise OK"
curl -f http://localhost:8004/health && echo "✅ Alert OK"

# 3. Check infrastructure
curl -f http://localhost:9090/-/healthy && echo "✅ Prometheus OK"
curl -f http://localhost:3000/api/health && echo "✅ Grafana OK"

# 4. Test database connectivity
docker-compose -f docker-compose.prod.yml exec db pg_isready -U reddit_watcher_user
```

### Comprehensive Health Assessment

**Full System Audit (5-10 minutes):**

```bash
#!/bin/bash
# comprehensive_health_check.sh

echo "=== Reddit Technical Watcher Health Check ==="
echo "Timestamp: $(date)"
echo

# Service status
echo "=== Service Status ==="
docker-compose -f docker-compose.prod.yml ps

# Resource usage
echo -e "\n=== Resource Usage ==="
echo "Memory Usage:"
free -h
echo -e "\nDisk Usage:"
df -h
echo -e "\nCPU Usage:"
top -bn1 | grep "Cpu(s)"

# Container resource consumption
echo -e "\n=== Container Resources ==="
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Database health
echo -e "\n=== Database Health ==="
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    count(*) as active_connections,
    (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections
FROM pg_stat_activity WHERE state = 'active';"

# Redis health
echo -e "\n=== Redis Health ==="
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info memory | head -10

# A2A Protocol health
echo -e "\n=== A2A Protocol Health ==="
curl -s http://localhost:8000/discover | jq '.agents | length' && echo " agents registered"

# Recent errors
echo -e "\n=== Recent Errors (last 1 hour) ==="
docker-compose -f docker-compose.prod.yml logs --since 1h | grep -i error | tail -5

echo -e "\n=== Health Check Complete ==="
```

### Automated Health Monitoring

**Create monitoring script:**

```bash
#!/bin/bash
# automated_health_monitor.sh

ALERT_EMAIL="alerts@yourdomain.com"
LOG_FILE="/var/log/reddit-watcher-health.log"

# Health check function
check_service_health() {
    local service_url="$1"
    local service_name="$2"

    if curl -f -s --max-time 10 "$service_url" > /dev/null; then
        echo "$(date): ✅ $service_name is healthy" >> "$LOG_FILE"
        return 0
    else
        echo "$(date): ❌ $service_name is unhealthy" >> "$LOG_FILE"
        # Send alert
        echo "ALERT: $service_name is down at $(date)" | mail -s "Reddit Watcher Alert: $service_name Down" "$ALERT_EMAIL"
        return 1
    fi
}

# Run health checks
check_service_health "http://localhost:8000/health" "Coordinator Agent"
check_service_health "http://localhost:8001/health" "Retrieval Agent"
check_service_health "http://localhost:8002/health" "Filter Agent"
check_service_health "http://localhost:8003/health" "Summarise Agent"
check_service_health "http://localhost:8004/health" "Alert Agent"
check_service_health "http://localhost:9090/-/healthy" "Prometheus"
check_service_health "http://localhost:3000/api/health" "Grafana"

# Check database
if docker-compose -f docker-compose.prod.yml exec db pg_isready -U reddit_watcher_user > /dev/null 2>&1; then
    echo "$(date): ✅ Database is healthy" >> "$LOG_FILE"
else
    echo "$(date): ❌ Database is unhealthy" >> "$LOG_FILE"
    echo "ALERT: Database is down at $(date)" | mail -s "Reddit Watcher Alert: Database Down" "$ALERT_EMAIL"
fi
```

**Schedule with cron:**

```bash
# Add to crontab
# Check every 5 minutes
*/5 * * * * /path/to/automated_health_monitor.sh

# Daily comprehensive check
0 6 * * * /path/to/comprehensive_health_check.sh > /var/log/reddit-watcher-daily-health.log
```

## Service Monitoring

### Individual Service Health

**Coordinator Agent:**

```bash
# Health endpoint
curl -s http://localhost:8000/health | jq .

# Service discovery
curl -s http://localhost:8000/discover | jq .

# Agent card
curl -s http://localhost:8000/.well-known/agent.json | jq .

# Recent workflow executions
docker-compose -f docker-compose.prod.yml logs coordinator-agent | grep -i "workflow" | tail -10
```

**Retrieval Agent:**

```bash
# Health and last Reddit fetch
curl -s http://localhost:8001/health | jq .

# Check Reddit API connectivity
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
import praw
from reddit_watcher.config import get_settings
config = get_settings()
reddit = praw.Reddit(
    client_id=config.reddit_client_id,
    client_secret=config.reddit_client_secret,
    user_agent=config.reddit_user_agent
)
print('Reddit API Status:', reddit.auth.limits)
"
```

**Filter Agent:**

```bash
# Health and filtering metrics
curl -s http://localhost:8002/health | jq .

# Check Gemini API connectivity
docker-compose -f docker-compose.prod.yml exec filter-agent python -c "
import google.generativeai as genai
from reddit_watcher.config import get_settings
config = get_settings()
genai.configure(api_key=config.gemini_api_key)
models = list(genai.list_models())
print(f'Gemini API Status: {len(models)} models available')
"
```

**Summarise Agent:**

```bash
# Health and summarization metrics
curl -s http://localhost:8003/health | jq .

# Recent summarization jobs
docker-compose -f docker-compose.prod.yml logs summarise-agent | grep -i "summary" | tail -5
```

**Alert Agent:**

```bash
# Health and alert delivery status
curl -s http://localhost:8004/health | jq .

# Test Slack webhook (if configured)
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"Health check test from Reddit Watcher"}' \
        "$SLACK_WEBHOOK_URL"
fi

# Test SMTP connectivity
docker-compose -f docker-compose.prod.yml exec alert-agent python -c "
import smtplib
from reddit_watcher.config import get_settings
config = get_settings()
if config.has_smtp_config():
    server = smtplib.SMTP(config.smtp_server, config.smtp_port)
    server.starttls()
    server.login(config.smtp_username, config.smtp_password)
    print('SMTP Status: Connected successfully')
    server.quit()
else:
    print('SMTP Status: Not configured')
"
```

### Infrastructure Monitoring

**Database Monitoring:**

```bash
# Connection status
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    count(*) as total_connections,
    count(*) FILTER (WHERE state = 'active') as active_connections,
    count(*) FILTER (WHERE state = 'idle') as idle_connections
FROM pg_stat_activity;"

# Database size
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    pg_size_pretty(pg_database_size('reddit_watcher')) as database_size;"

# Slow queries
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements
WHERE mean_time > 1000  -- queries taking more than 1 second
ORDER BY total_time DESC LIMIT 5;"
```

**Redis Monitoring:**

```bash
# Redis info
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info

# Memory usage
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info memory

# Connected clients
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info clients

# A2A service discovery keys
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" keys "agent:*"
```

## Performance Monitoring

### System Performance

**Resource Utilization:**

```bash
# Real-time system monitoring
htop

# Memory usage breakdown
cat /proc/meminfo

# Disk I/O
iostat -x 1 5

# Network traffic
iftop

# Load average
uptime
```

**Container Performance:**

```bash
# Container resource usage
docker stats

# Specific container inspection
docker inspect reddit_watcher_coordinator_prod | jq '.State.Health'

# Container logs with timestamps
docker-compose -f docker-compose.prod.yml logs -t --since 1h coordinator-agent
```

### Application Performance

**Response Time Monitoring:**

```bash
# Test endpoint response times
time curl -s http://localhost:8000/health > /dev/null
time curl -s http://localhost:8000/.well-known/agent.json > /dev/null

# Measure A2A communication latency
time curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"ping"}]}},"id":"ping"}' \
  http://localhost:8000/a2a
```

**Database Performance:**

```bash
# Connection pool usage
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    count(*) as active_connections,
    max_val as max_connections,
    round(100.0 * count(*) / max_val, 2) as connection_usage_percent
FROM pg_stat_activity
CROSS JOIN (SELECT setting::int as max_val FROM pg_settings WHERE name = 'max_connections') s;"

# Index usage
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY tablename, attname;"
```

## Alert Response

### Critical Alerts

**Agent Down Alert:**

```bash
# 1. Identify which agent is down
docker-compose -f docker-compose.prod.yml ps | grep -v "Up"

# 2. Check logs for the down agent
docker-compose -f docker-compose.prod.yml logs --since 30m [agent-name]

# 3. Attempt restart
docker-compose -f docker-compose.prod.yml restart [agent-name]

# 4. If restart fails, check resources
df -h && free -h

# 5. If resources are ok, check configuration
docker-compose -f docker-compose.prod.yml config

# 6. Full restart if needed
docker-compose -f docker-compose.prod.yml down [agent-name]
docker-compose -f docker-compose.prod.yml up -d [agent-name]
```

**Database Down Alert:**

```bash
# 1. Check database container status
docker-compose -f docker-compose.prod.yml ps db

# 2. Check database logs
docker-compose -f docker-compose.prod.yml logs db

# 3. Check disk space
df -h

# 4. Attempt restart
docker-compose -f docker-compose.prod.yml restart db

# 5. If restart fails, restore from backup
./deploy_production.sh backup
./deploy_production.sh rollback
```

**High Error Rate Alert:**

```bash
# 1. Identify error sources
docker-compose -f docker-compose.prod.yml logs --since 1h | grep -i error | sort | uniq -c | sort -nr

# 2. Check specific agent logs
docker-compose -f docker-compose.prod.yml logs --since 1h [agent-with-errors]

# 3. Check external service connectivity
# Reddit API
curl -I https://reddit.com
# Gemini API
curl -H "Authorization: Bearer $GEMINI_API_KEY" https://generativelanguage.googleapis.com/v1/models

# 4. Check circuit breaker status
docker-compose -f docker-compose.prod.yml logs coordinator-agent | grep -i "circuit"

# 5. Restart affected services if needed
docker-compose -f docker-compose.prod.yml restart [affected-services]
```

### Warning Alerts

**High Response Time:**

```bash
# 1. Check system load
top -bn1 | head -5

# 2. Check container resource usage
docker stats --no-stream

# 3. Check database performance
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"

# 4. Check for memory pressure
free -h && cat /proc/meminfo | grep -E "(MemAvailable|SwapFree)"

# 5. Scale services if needed
docker-compose -f docker-compose.prod.yml up -d --scale retrieval-agent=2
```

**High Memory Usage:**

```bash
# 1. Identify memory consumers
ps aux --sort=-%mem | head -10

# 2. Check container memory usage
docker stats --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 3. Check for memory leaks
docker-compose -f docker-compose.prod.yml logs --since 24h | grep -i "memory\|oom"

# 4. Restart high-memory containers if needed
docker-compose -f docker-compose.prod.yml restart summarise-agent

# 5. Clean up Docker resources
docker system prune -f
```

## Troubleshooting Procedures

### Service Discovery Issues

**Symptoms:**

- Agents can't find each other
- A2A communication failures
- Empty `/discover` endpoint response

**Resolution:**

```bash
# 1. Check Redis connectivity
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ping

# 2. Check service registration
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" keys "agent:*"

# 3. Verify agent registration
for port in 8000 8001 8002 8003 8004; do
    echo "Port $port:"
    curl -s http://localhost:$port/.well-known/agent.json | jq .name
done

# 4. Restart Redis and agents
docker-compose -f docker-compose.prod.yml restart redis
sleep 10
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent
```

### Network Connectivity Issues

**Symptoms:**

- External API failures
- Inter-agent communication failures
- Health checks failing

**Resolution:**

```bash
# 1. Check network connectivity
ping 8.8.8.8
curl -I https://reddit.com
curl -I https://generativelanguage.googleapis.com

# 2. Check Docker networks
docker network ls
docker network inspect reddit_watcher_internal
docker network inspect reddit_watcher_external

# 3. Check firewall rules
sudo ufw status
sudo iptables -L

# 4. Test internal connectivity
docker-compose -f docker-compose.prod.yml exec coordinator-agent ping -c 3 db
docker-compose -f docker-compose.prod.yml exec coordinator-agent ping -c 3 redis

# 5. Recreate networks if needed
docker-compose -f docker-compose.prod.yml down
docker network prune -f
docker-compose -f docker-compose.prod.yml up -d
```

### Performance Degradation

**Symptoms:**

- Slow response times
- High CPU/memory usage
- Workflow delays

**Resolution:**

```bash
# 1. Identify bottlenecks
docker stats --no-stream
top -bn1

# 2. Check database performance
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT * FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '30 seconds';"

# 3. Check slow queries
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT query, total_time, calls, mean_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# 4. Optimize resources
# Restart memory-intensive services
docker-compose -f docker-compose.prod.yml restart summarise-agent

# Clear caches
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" flushdb

# 5. Scale horizontally if needed
docker-compose -f docker-compose.prod.yml up -d --scale filter-agent=2 --scale summarise-agent=2
```

## Escalation Procedures

### Level 1: Automated Response

**Automated actions:**

- Service restarts via health check scripts
- Circuit breaker activation
- Resource cleanup
- Basic alerting

### Level 2: On-Call Engineer

**Escalation triggers:**

- Multiple service failures
- Database connectivity issues
- External API failures lasting > 15 minutes
- Data corruption

**Actions:**

1. Assess system state using health check procedures
2. Attempt service restarts and basic troubleshooting
3. Check monitoring dashboards for patterns
4. Document findings and actions taken
5. Escalate to Level 3 if issues persist > 30 minutes

### Level 3: Senior Engineer/Architect

**Escalation triggers:**

- System-wide outages
- Data loss incidents
- Security breaches
- Complex architectural issues

**Actions:**

1. Full system assessment
2. Coordinate with external services (Reddit, Google)
3. Decide on rollback vs. forward fix
4. Coordinate disaster recovery if needed
5. Post-incident review and documentation

### Emergency Contacts

```yaml
Level 1: automated-alerts@yourdomain.com
Level 2: oncall-engineer@yourdomain.com
Level 3: senior-engineer@yourdomain.com
Emergency: emergency-contact@yourdomain.com

External Support:
- Hosting Provider: support@hostinger.com
- DNS Provider: support@your-dns-provider.com
```

### Emergency Procedures

**Complete System Failure:**

```bash
# 1. Immediate assessment
./deploy_production.sh status

# 2. Stop all services
docker-compose -f docker-compose.prod.yml down

# 3. Check system resources
df -h && free -h && uptime

# 4. Restore from backup if needed
./deploy_production.sh rollback

# 5. If rollback fails, redeploy from scratch
docker system prune -a --volumes
./deploy_production.sh deploy

# 6. Notify stakeholders
echo "System restoration in progress" | mail -s "Reddit Watcher System Alert" emergency-contact@yourdomain.com
```

## Maintenance Windows

### Scheduled Maintenance

**Weekly Maintenance (Sunday 2 AM):**

```bash
# 1. Create backup
./deploy_production.sh backup

# 2. Update system packages
sudo apt update && sudo apt upgrade -y

# 3. Restart services for memory cleanup
docker-compose -f docker-compose.prod.yml restart

# 4. Clean up old resources
docker system prune -f
docker volume prune -f --filter "label!=keep"

# 5. Verify system health
./deploy_production.sh validate
```

**Monthly Maintenance:**

```bash
# 1. Security updates
sudo apt update && sudo apt upgrade -y

# 2. Docker image updates
docker-compose -f docker-compose.prod.yml pull

# 3. Database maintenance
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "VACUUM ANALYZE;"

# 4. Log rotation
sudo logrotate -f /etc/logrotate.conf

# 5. Security audit
sudo chkrootkit
sudo rkhunter --check
```

This runbook should be reviewed and updated regularly based on operational experience and system changes.
