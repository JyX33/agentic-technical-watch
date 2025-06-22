# Daily Operations Runbook

This runbook covers daily operational tasks for maintaining the Reddit Technical Watcher system.

## Pre-Shift Checklist (Start of Day)

### 1. System Health Check (5 minutes)

**Check Overall System Status:**

```bash
# Check all agent health endpoints
curl -s https://api.company.com/coordinator/health | jq '.status'
curl -s https://api.company.com/retrieval/health | jq '.status'
curl -s https://api.company.com/filter/health | jq '.status'
curl -s https://api.company.com/summarise/health | jq '.status'
curl -s https://api.company.com/alert/health | jq '.status'
```

**Expected Response:**

```json
{
  "status": "healthy",
  "agent_type": "coordinator",
  "version": "1.0.0",
  "uptime": "active"
}
```

**If Unhealthy:**

- Proceed to [Incident Response](./incident-response.md)
- Check agent logs for error details

### 2. Infrastructure Health Check (3 minutes)

**Check Database Connectivity:**

```bash
# PostgreSQL health check
docker exec postgres-reddit-watcher pg_isready -U postgres
```

**Check Redis Connectivity:**

```bash
# Redis health check
docker exec redis-reddit-watcher redis-cli ping
```

**Check Disk Space:**

```bash
# Check disk usage
df -h | grep -E '(docker|postgres|redis)'
```

**Alert if:**

- Database connection fails
- Redis connection fails
- Disk usage > 80%

### 3. Review Overnight Alerts (10 minutes)

**Check Grafana Dashboard:**

1. Visit <https://grafana.company.com/reddit-watcher>
2. Review "System Overview" dashboard
3. Check for any red alerts or anomalies

**Review Prometheus Alerts:**

```bash
# Check active alerts
curl -s http://prometheus:9090/api/v1/alerts | jq '.data.alerts[]'
```

**Review Application Logs:**

```bash
# Check for ERROR level logs from last 24 hours
docker-compose logs --since=24h | grep -i "error\|exception\|fail"
```

### 4. Backup Verification (5 minutes)

**Check Database Backup Status:**

```bash
# Verify last backup timestamp
ls -la /backup/postgres/ | head -5
```

**Check Backup File Size:**

```bash
# Compare with previous backups
du -h /backup/postgres/reddit_watcher_*.sql.gz | tail -5
```

**Alert if:**

- No backup from last 24 hours
- Backup size significantly different from previous
- Backup files missing

## Hourly Monitoring Tasks

### Performance Metrics Review (2 minutes)

**Check Key Metrics:**

```bash
# API response times
curl -s http://prometheus:9090/api/v1/query?query=http_request_duration_seconds | jq '.data'

# Error rates
curl -s http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[5m]) | jq '.data'

# System resources
curl -s http://prometheus:9090/api/v1/query?query=node_memory_MemAvailable_bytes | jq '.data'
```

**Alert Thresholds:**

- API response time > 2 seconds
- Error rate > 1%
- Memory usage > 80%
- CPU usage > 70%

### Agent Service Discovery (1 minute)

**Verify Agent Registration:**

```bash
# Check agent discovery
curl -s https://api.company.com/coordinator/discover | jq '.agents'
```

**Expected Response:**

```json
{
  "agents": {
    "retrieval": {
      "name": "Reddit Retrieval Agent",
      "status": "healthy",
      "last_seen": "2025-06-22T10:30:00Z"
    },
    "filter": {
      "name": "Reddit Filter Agent",
      "status": "healthy",
      "last_seen": "2025-06-22T10:30:00Z"
    }
  }
}
```

## Mid-Day Review (15 minutes)

### 1. Workflow Execution Review (5 minutes)

**Check Recent Workflow Runs:**

```bash
# Query recent workflows
curl -s -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/workflows?limit=10" | jq '.'
```

**Review Metrics:**

- Workflow success rate
- Average execution time
- Failed workflows and reasons

### 2. Reddit API Usage Review (5 minutes)

**Check API Rate Limits:**

```bash
# Check Reddit API usage
curl -s -H "X-API-Key: $API_KEY" \
  "https://api.company.com/retrieval/metrics" | jq '.reddit_api'
```

**Monitor:**

- Requests per minute
- Rate limit violations
- Authentication errors

### 3. Notification Delivery Review (5 minutes)

**Check Alert Delivery:**

```bash
# Check recent alerts
curl -s -H "X-API-Key: $API_KEY" \
  "https://api.company.com/alert/history?hours=24" | jq '.'
```

**Verify:**

- Slack notifications delivered
- Email notifications sent
- No delivery failures

## End-of-Day Tasks (10 minutes)

### 1. Daily Metrics Summary (5 minutes)

**Generate Daily Report:**

```bash
# Script to generate daily metrics
./scripts/generate-daily-report.sh
```

**Review Key Metrics:**

- Total workflows executed
- Success/failure rates
- Average response times
- Reddit posts processed
- Alerts sent

### 2. Log Rotation and Cleanup (3 minutes)

**Check Log File Sizes:**

```bash
# Check log disk usage
du -sh /var/log/reddit-watcher/*
```

**Rotate Large Logs:**

```bash
# Rotate logs if needed
sudo logrotate /etc/logrotate.d/reddit-watcher
```

### 3. Security Events Review (2 minutes)

**Check Authentication Logs:**

```bash
# Review authentication events
grep -i "auth\|login\|fail" /var/log/reddit-watcher/security.log | tail -50
```

**Monitor for:**

- Failed authentication attempts
- Unusual API usage patterns
- Rate limiting violations

## Weekly Preparation Tasks (Friday)

### 1. Weekend Monitoring Setup (5 minutes)

**Verify On-Call Setup:**

- Confirm weekend on-call rotation
- Test emergency contact methods
- Review escalation procedures

**Check Automated Monitoring:**

```bash
# Verify alerting rules
curl -s http://prometheus:9090/api/v1/rules | jq '.data.groups[].rules[]'
```

### 2. Backup Validation (10 minutes)

**Test Backup Restore:**

```bash
# Test database backup restore (staging)
./scripts/test-backup-restore.sh latest
```

**Verify Backup Integrity:**

```bash
# Check backup checksums
md5sum /backup/postgres/reddit_watcher_$(date +%Y%m%d)*.sql.gz
```

## Common Issues and Quick Fixes

### Agent Not Responding

**Symptoms:**

- Health check returns 503 or timeout
- Agent missing from service discovery

**Quick Fix:**

```bash
# Restart specific agent
docker-compose restart retrieval-agent

# Check logs
docker-compose logs retrieval-agent --tail=50
```

### High Memory Usage

**Symptoms:**

- Memory usage > 80%
- Slow response times

**Quick Fix:**

```bash
# Clear application caches
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/cache/clear"

# Restart if necessary
docker-compose restart reddit-watcher
```

### Database Connection Issues

**Symptoms:**

- Database connection errors
- Timeout errors

**Quick Fix:**

```bash
# Check database status
docker exec postgres-reddit-watcher pg_isready

# Check connections
docker exec postgres-reddit-watcher psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Restart if necessary
docker-compose restart postgres
```

## Escalation Criteria

### Immediate Escalation (P1)

- System completely down
- Data corruption detected
- Security breach suspected
- Multiple agent failures

### Escalation within 1 hour (P2)

- Single agent failure
- Performance degradation > 50%
- Backup failures
- External API failures

### Standard Escalation (P3)

- Minor performance issues
- Non-critical feature failures
- Monitoring alerts

## Daily Checklist Template

```
[ ] System health check completed
[ ] Infrastructure health verified
[ ] Overnight alerts reviewed
[ ] Backup verification completed
[ ] Hourly monitoring tasks on schedule
[ ] Mid-day review completed
[ ] End-of-day tasks completed
[ ] Issues escalated as needed
[ ] Daily metrics documented
```

---

*Next: [Weekly Maintenance](./weekly-maintenance.md)*
