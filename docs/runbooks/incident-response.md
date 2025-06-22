# Incident Response Runbook

Complete incident response procedures for the Reddit Technical Watcher system.

## Incident Classification

### Severity Levels

**Critical (P1) - System Down**

- Complete system failure
- Data loss or corruption
- Security breach
- **Response Time: 15 minutes**
- **Resolution Target: 1 hour**

**High (P2) - Severe Degradation**

- Significant service degradation
- Multiple agent failures
- External API failures
- **Response Time: 1 hour**
- **Resolution Target: 4 hours**

**Medium (P3) - Partial Degradation**

- Single agent failure
- Performance issues
- Non-critical feature failures
- **Response Time: 4 hours**
- **Resolution Target: 24 hours**

**Low (P4) - Minor Issues**

- Minor bugs
- Documentation issues
- Enhancement requests
- **Response Time: 24 hours**
- **Resolution Target: 5 days**

## Incident Response Process

### 1. Detection and Alert (0-5 minutes)

**Incident Sources:**

- Automated monitoring alerts
- User reports
- Internal team detection
- External monitoring services

**Immediate Actions:**

1. Acknowledge the alert
2. Assess incident severity
3. Create incident ticket
4. Notify on-call team

**Tools:**

- Slack: #reddit-watcher-incidents
- Incident tracking: JIRA/ServiceNow
- Communication: Status page

### 2. Initial Response (5-15 minutes)

**P1 Critical Response:**

```bash
# Immediate system check
./scripts/emergency-health-check.sh

# Check all agents
curl -s https://api.company.com/coordinator/health | jq '.'
curl -s https://api.company.com/retrieval/health | jq '.'
curl -s https://api.company.com/filter/health | jq '.'
curl -s https://api.company.com/summarise/health | jq '.'
curl -s https://api.company.com/alert/health | jq '.'
```

**P2 High Response:**

```bash
# Detailed system assessment
./scripts/system-assessment.sh

# Check performance metrics
curl -s http://prometheus:9090/api/v1/query?query=up | jq '.'
```

**Communication:**

- Post in #reddit-watcher-incidents
- Update status page
- Notify stakeholders (P1 only)

### 3. Investigation and Diagnosis (15-60 minutes)

**Log Analysis:**

```bash
# Check recent errors
docker-compose logs --since=1h | grep -i "error\|exception\|fail"

# Check system logs
journalctl -u reddit-watcher --since="1 hour ago"

# Check application logs
tail -f /var/log/reddit-watcher/application.log
```

**System Metrics:**

```bash
# Check resource usage
docker stats

# Check database performance
docker exec postgres-reddit-watcher psql -U postgres -c "
  SELECT pid, state, wait_event_type, wait_event, query
  FROM pg_stat_activity
  WHERE state != 'idle';"

# Check Redis performance
docker exec redis-reddit-watcher redis-cli info stats
```

**Network Connectivity:**

```bash
# Check external dependencies
curl -I https://www.reddit.com/api/v1/me
curl -I https://generativelanguage.googleapis.com/v1beta/models

# Check internal connectivity
docker network ls
docker network inspect reddit-watcher_default
```

### 4. Containment and Workaround (Immediate)

**Service Isolation:**

```bash
# Isolate failing agent
docker-compose stop failing-agent

# Redirect traffic if needed
# Update load balancer configuration
```

**Circuit Breaker Activation:**

```bash
# Manually trigger circuit breakers
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/circuit-breaker/open"
```

**Fallback Procedures:**

- Enable maintenance mode
- Switch to backup systems
- Activate manual processes

### 5. Resolution and Recovery

**Common Resolution Steps:**

**Agent Restart:**

```bash
# Restart specific agent
docker-compose restart agent-name

# Verify restart
curl -s https://api.company.com/agent-name/health | jq '.status'
```

**System Restart:**

```bash
# Full system restart
docker-compose down
docker-compose up -d

# Verify all services
./scripts/verify-all-services.sh
```

**Database Recovery:**

```bash
# Check database integrity
docker exec postgres-reddit-watcher pg_dump -U postgres reddit_watcher > /tmp/integrity_check.sql

# Restore from backup if needed
./scripts/restore-database.sh /backup/postgres/latest.sql.gz
```

**Configuration Rollback:**

```bash
# Rollback to previous configuration
git checkout HEAD~1 -- config/
docker-compose up -d
```

### 6. Verification and Testing

**Health Verification:**

```bash
# Comprehensive health check
./scripts/comprehensive-health-check.sh

# End-to-end testing
./scripts/e2e-test.sh
```

**Performance Validation:**

```bash
# Load testing
./scripts/load-test.sh --duration=5m

# Monitoring verification
curl -s http://prometheus:9090/api/v1/query?query=up | jq '.data.result[].value[1]'
```

## Incident Response Playbooks

### Playbook 1: Complete System Failure

**Symptoms:**

- All agents return 503 or timeout
- No response from load balancer
- Multiple monitoring alerts

**Response:**

```bash
# 1. Check infrastructure
docker ps | grep reddit-watcher
docker-compose ps

# 2. Check system resources
df -h
free -h
top

# 3. Check logs
docker-compose logs --tail=100

# 4. Restart system
docker-compose down
docker-compose up -d

# 5. Verify recovery
./scripts/verify-system-recovery.sh
```

### Playbook 2: Database Connection Failure

**Symptoms:**

- Database connection errors
- Agents report database unavailable
- PostgreSQL connection alerts

**Response:**

```bash
# 1. Check database status
docker exec postgres-reddit-watcher pg_isready -U postgres

# 2. Check database logs
docker-compose logs postgres

# 3. Check connections
docker exec postgres-reddit-watcher psql -U postgres -c "
  SELECT count(*) FROM pg_stat_activity;"

# 4. Restart database if needed
docker-compose restart postgres

# 5. Verify agent connectivity
curl -s https://api.company.com/coordinator/health | jq '.database_status'
```

### Playbook 3: Redis Service Discovery Failure

**Symptoms:**

- Agents can't discover each other
- Service registration failures
- Redis connection errors

**Response:**

```bash
# 1. Check Redis status
docker exec redis-reddit-watcher redis-cli ping

# 2. Check Redis logs
docker-compose logs redis

# 3. Check service registration
docker exec redis-reddit-watcher redis-cli keys "agent:*"

# 4. Restart Redis
docker-compose restart redis

# 5. Re-register agents
./scripts/register-all-agents.sh
```

### Playbook 4: External API Failure

**Symptoms:**

- Reddit API failures
- Gemini API failures
- Rate limiting errors

**Response:**

```bash
# 1. Check API status
curl -I https://www.reddit.com/api/v1/me
curl -I https://generativelanguage.googleapis.com/v1beta/models

# 2. Check API credentials
./scripts/validate-api-credentials.sh

# 3. Check rate limiting
curl -s -H "X-API-Key: $API_KEY" \
  https://api.company.com/retrieval/metrics | jq '.rate_limits'

# 4. Implement backoff strategy
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/retrieval/backoff/enable"
```

### Playbook 5: High Resource Usage

**Symptoms:**

- High CPU/memory usage
- Slow response times
- Resource exhaustion alerts

**Response:**

```bash
# 1. Identify resource usage
docker stats --no-stream
top -p $(pgrep -f reddit-watcher)

# 2. Check for memory leaks
docker exec coordinator-agent ps aux | grep -v grep

# 3. Clear caches
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/cache/clear"

# 4. Restart high-usage services
docker-compose restart high-usage-service

# 5. Scale if needed
docker-compose scale service-name=2
```

## Communication Templates

### Incident Alert Template

```
🚨 INCIDENT ALERT - P1 Critical
System: Reddit Technical Watcher
Issue: [Brief description]
Impact: [Customer/business impact]
Time: [Incident start time]
Status: Investigating
ETA: [Estimated resolution time]
Lead: [Incident commander]
```

### Status Update Template

```
📊 INCIDENT UPDATE - P1 Critical
System: Reddit Technical Watcher
Issue: [Brief description]
Progress: [Current status and actions taken]
Next Steps: [What's being done next]
ETA: [Updated resolution time]
Lead: [Incident commander]
```

### Resolution Notification Template

```
✅ INCIDENT RESOLVED - P1 Critical
System: Reddit Technical Watcher
Issue: [Brief description]
Resolution: [How it was fixed]
Duration: [Total downtime]
Follow-up: [Post-incident actions]
Lead: [Incident commander]
```

## Post-Incident Activities

### 1. Incident Documentation (Within 24 hours)

**Required Documentation:**

- Incident timeline
- Root cause analysis
- Impact assessment
- Resolution steps
- Lessons learned

**Template:**

```markdown
# Incident Report - [Date] - [Brief Title]

## Summary
- Start Time: [Time]
- End Time: [Time]
- Duration: [Duration]
- Severity: [P1/P2/P3/P4]
- Services Affected: [List]

## Timeline
[Detailed timeline of events]

## Root Cause
[Technical root cause analysis]

## Resolution
[Steps taken to resolve]

## Impact
[Business and customer impact]

## Lessons Learned
[What went well, what didn't]

## Action Items
[Follow-up tasks with owners and dates]
```

### 2. Post-Incident Review (Within 48 hours)

**Review Meeting:**

- Incident commander
- Engineering team
- Operations team
- Stakeholders

**Review Agenda:**

1. Incident walkthrough
2. Root cause analysis
3. Response evaluation
4. Process improvements
5. Action item assignment

### 3. Follow-up Actions (Within 1 week)

**Common Follow-ups:**

- Update monitoring and alerting
- Improve documentation
- Infrastructure improvements
- Process refinements
- Training updates

## Incident Response Tools

### Monitoring and Alerting

- **Prometheus**: <http://prometheus:9090>
- **Grafana**: <https://grafana.company.com>
- **AlertManager**: <http://alertmanager:9093>

### Communication

- **Slack**: #reddit-watcher-incidents
- **Status Page**: <https://status.company.com>
- **Email**: <incidents@company.com>

### Logging and Metrics

- **Application Logs**: `/var/log/reddit-watcher/`
- **System Logs**: `journalctl`
- **Docker Logs**: `docker-compose logs`

### Incident Management

- **Ticketing**: JIRA/ServiceNow
- **Runbooks**: This documentation
- **Escalation**: See [README](./README.md)

---

*Next: [Service Degradation](./service-degradation.md)*
