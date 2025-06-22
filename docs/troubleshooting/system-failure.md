# System Failure Troubleshooting

Complete troubleshooting guide for system-wide failures in the Reddit Technical Watcher.

## Symptoms

**Complete System Down:**
- No response from any agent endpoint
- Load balancer returning 503 Service Unavailable
- All health checks failing
- Monitoring alerts for all services

**Partial System Down:**
- Some agents responding, others not
- Database connectivity issues
- Service discovery failures
- Intermittent 500/503 errors

## Initial Diagnosis (First 5 minutes)

### 1. Quick System Assessment

```bash
# Check if any services are running
docker-compose ps

# Quick health check all agents
curl -s --max-time 5 https://api.company.com/coordinator/health || echo "Coordinator DOWN"
curl -s --max-time 5 https://api.company.com/retrieval/health || echo "Retrieval DOWN"
curl -s --max-time 5 https://api.company.com/filter/health || echo "Filter DOWN"
curl -s --max-time 5 https://api.company.com/summarise/health || echo "Summarise DOWN"
curl -s --max-time 5 https://api.company.com/alert/health || echo "Alert DOWN"
```

### 2. Infrastructure Check

```bash
# Check system resources
df -h | grep -E '(/$|/var|/tmp)'  # Disk space
free -h                          # Memory
uptime                          # Load average

# Check Docker status
systemctl status docker
docker version
```

### 3. Network Connectivity

```bash
# Check if load balancer is accessible
curl -I https://api.company.com/ || echo "Load balancer DOWN"

# Check internal network
docker network ls
docker network inspect reddit-watcher_default
```

## Detailed Diagnosis

### Infrastructure-Level Issues

#### Docker Daemon Problems

**Check Docker Status:**
```bash
# Docker daemon status
systemctl status docker

# Docker logs
journalctl -u docker.service --since="1 hour ago" --no-pager
```

**Common Docker Issues:**
```bash
# Disk space exhaustion
docker system df
docker system prune -f

# Docker daemon restart
sudo systemctl restart docker
```

#### System Resource Exhaustion

**Memory Issues:**
```bash
# Check memory usage
free -h
cat /proc/meminfo | grep -E "(MemTotal|MemFree|MemAvailable)"

# Check for OOM kills
dmesg | grep -i "killed process\|out of memory"
journalctl --since="1 hour ago" | grep -i "oom"
```

**Disk Space Issues:**
```bash
# Check disk usage
df -h
du -sh /var/lib/docker/
du -sh /var/log/

# Clean up disk space
docker system prune -af
sudo logrotate -f /etc/logrotate.conf
```

**CPU Issues:**
```bash
# Check CPU usage
top -bn1 | head -20
iostat -x 1 5

# Check for high load
uptime
cat /proc/loadavg
```

#### Network Issues

**Port Conflicts:**
```bash
# Check if ports are in use
netstat -tulpn | grep -E ':(8000|8001|8002|8003|8004|5432|6379)'
ss -tulpn | grep -E ':(8000|8001|8002|8003|8004|5432|6379)'
```

**Firewall Issues:**
```bash
# Check firewall rules
sudo iptables -L -n
sudo ufw status
```

### Application-Level Issues

#### Database Connection Failures

**PostgreSQL Status:**
```bash
# Check PostgreSQL container
docker exec postgres-reddit-watcher pg_isready -U postgres

# Check database logs
docker-compose logs postgres --tail=50

# Check database connections
docker exec postgres-reddit-watcher psql -U postgres -c "
  SELECT count(*) as total_connections,
         count(*) FILTER (WHERE state = 'active') as active_connections,
         count(*) FILTER (WHERE state = 'idle') as idle_connections
  FROM pg_stat_activity;"
```

**Database Recovery:**
```bash
# Stop all agents first
docker-compose stop coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# Restart PostgreSQL
docker-compose restart postgres

# Wait for database to be ready
while ! docker exec postgres-reddit-watcher pg_isready -U postgres; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

# Start agents
docker-compose start coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent
```

#### Redis Service Discovery Failures

**Redis Status:**
```bash
# Check Redis container
docker exec redis-reddit-watcher redis-cli ping

# Check Redis logs
docker-compose logs redis --tail=50

# Check Redis memory usage
docker exec redis-reddit-watcher redis-cli info memory
```

**Redis Recovery:**
```bash
# Restart Redis
docker-compose restart redis

# Clear stale service discovery data
docker exec redis-reddit-watcher redis-cli FLUSHALL

# Re-register all agents
./scripts/register-all-agents.sh
```

#### Agent Process Failures

**Check Agent Logs:**
```bash
# Check all agent logs for errors
docker-compose logs --since=1h | grep -i "error\|exception\|fatal"

# Check specific agent
docker-compose logs coordinator-agent --tail=100
```

**Check Agent Resources:**
```bash
# Check container resource usage
docker stats --no-stream

# Check container health
docker inspect coordinator-agent | jq '.[0].State.Health'
```

### Configuration Issues

#### Environment Variable Problems

**Check Configuration:**
```bash
# Verify environment files exist
ls -la .env* config/

# Check for missing variables
docker-compose config | grep -E "(DATABASE_URL|REDIS_URL|API_KEY)"

# Validate configuration
./scripts/validate-config.sh
```

#### SSL/TLS Certificate Issues

**Check Certificates:**
```bash
# Check certificate expiration
openssl x509 -in /etc/ssl/certs/reddit-watcher.pem -noout -dates

# Check certificate chain
openssl s_client -connect api.company.com:443 -servername api.company.com
```

## Step-by-Step Recovery Procedures

### Procedure 1: Complete System Restart

**Use when:** All services are down or unresponsive

```bash
# 1. Stop all services gracefully
docker-compose down --timeout 30

# 2. Clean up containers and networks
docker container prune -f
docker network prune -f

# 3. Check system resources
df -h
free -h

# 4. Start infrastructure services first
docker-compose up -d postgres redis

# 5. Wait for infrastructure to be ready
sleep 30
docker exec postgres-reddit-watcher pg_isready -U postgres
docker exec redis-reddit-watcher redis-cli ping

# 6. Start application services
docker-compose up -d coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# 7. Verify all services are healthy
./scripts/verify-system-health.sh
```

### Procedure 2: Rolling Restart

**Use when:** Some services are working, selective restart needed

```bash
# 1. Identify failing services
failed_services=($(docker-compose ps --services --filter "status=exited"))

# 2. Restart each failed service
for service in "${failed_services[@]}"; do
  echo "Restarting $service..."
  docker-compose restart "$service"
  sleep 10

  # Verify service health
  if [[ "$service" == *"agent"* ]]; then
    curl -s "http://localhost:${port}/health" | jq '.status'
  fi
done

# 3. Verify system health
./scripts/verify-system-health.sh
```

### Procedure 3: Database Recovery

**Use when:** Database corruption or connection issues

```bash
# 1. Stop all agents
docker-compose stop coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# 2. Backup current database
docker exec postgres-reddit-watcher pg_dump -U postgres reddit_watcher > /backup/emergency_$(date +%Y%m%d_%H%M%S).sql

# 3. Check database integrity
docker exec postgres-reddit-watcher psql -U postgres -d reddit_watcher -c "
  SELECT datname, stats_reset, checksum_failures
  FROM pg_stat_database
  WHERE datname = 'reddit_watcher';"

# 4. If corruption detected, restore from backup
if [ "$checksum_failures" -gt 0 ]; then
  # Restore from latest backup
  ./scripts/restore-database.sh /backup/postgres/latest.sql.gz
fi

# 5. Restart agents
docker-compose start coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent
```

### Procedure 4: Emergency Rollback

**Use when:** Recent deployment caused system failure

```bash
# 1. Stop current system
docker-compose down

# 2. Rollback to previous version
git log --oneline -10  # Find previous stable commit
git checkout <previous-stable-commit>

# 3. Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# 4. Verify rollback success
./scripts/verify-system-health.sh

# 5. If successful, create hotfix branch
git checkout -b hotfix/emergency-rollback-$(date +%Y%m%d)
```

## Recovery Verification

### Health Check Verification

```bash
# Comprehensive health check
./scripts/comprehensive-health-check.sh

# Manual verification
curl -s https://api.company.com/coordinator/health | jq '.status'
curl -s https://api.company.com/retrieval/health | jq '.status'
curl -s https://api.company.com/filter/health | jq '.status'
curl -s https://api.company.com/summarise/health | jq '.status'
curl -s https://api.company.com/alert/health | jq '.status'
```

### Functional Testing

```bash
# Test A2A communication
./scripts/test-a2a-communication.sh

# Test complete workflow
./scripts/test-complete-workflow.sh

# Test external API connectivity
curl -s -H "X-API-Key: $API_KEY" \
  "https://api.company.com/retrieval/test-reddit-api"
```

### Performance Validation

```bash
# Load testing
./scripts/load-test.sh --duration=5m --requests=100

# Response time testing
./scripts/response-time-test.sh

# Resource usage monitoring
./scripts/monitor-resources.sh --duration=10m
```

## Prevention Measures

### Monitoring Enhancements

```bash
# Add additional health checks
# Edit docker-compose.yml to add health checks for all services

# Enhance monitoring
# Add custom metrics for business logic
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/metrics/enable-custom"
```

### System Hardening

```bash
# Increase resource limits
# Edit docker-compose.yml memory and CPU limits

# Add backup verification
./scripts/setup-backup-verification.sh

# Implement circuit breakers
curl -X POST -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/circuit-breaker/configure"
```

### Documentation Updates

```bash
# Update runbooks based on incident
vim docs/runbooks/incident-response.md

# Add new troubleshooting steps
vim docs/troubleshooting/system-failure.md

# Update monitoring procedures
vim docs/runbooks/system-health-monitoring.md
```

## Emergency Contacts

### Critical Escalation
- **On-Call Engineer**: +1-555-ONCALL
- **System Administrator**: +1-555-SYSADMIN
- **Database Administrator**: +1-555-DBA

### Communication Channels
- **Slack**: #reddit-watcher-incidents
- **Email**: incidents@company.com
- **Status Page**: https://status.company.com

### External Support
- **Cloud Provider**: Support ticket system
- **CDN Provider**: Emergency support line
- **Monitoring Service**: Support chat

---

*Next: [Performance Issues](./performance-issues.md)*
