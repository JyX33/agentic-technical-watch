# Quick Start Guide

Get up and running with Reddit Technical Watcher operations in 15 minutes.

## Prerequisites

**System Access:**
- VPN connection to company network
- SSH access to production servers
- Access to monitoring dashboards
- Slack workspace membership

**Required Accounts:**
- Company email account
- Grafana dashboard access
- Status page admin access
- API key for system access

## Step 1: Access the System (2 minutes)

### Connect to Production Environment

```bash
# Connect via VPN
sudo openvpn /etc/openvpn/company-vpn.conf

# SSH to production server
ssh ops@prod-reddit-watcher.company.com

# Switch to application directory
cd /opt/reddit-watcher
```

### Verify System Access

```bash
# Check your permissions
whoami
groups

# Verify Docker access
docker ps

# Check application status
docker-compose ps
```

## Step 2: System Health Check (3 minutes)

### Quick Health Verification

```bash
# Run comprehensive health check
./scripts/health-check.sh

# Check individual agents
curl -s https://api.company.com/coordinator/health | jq '.status'
curl -s https://api.company.com/retrieval/health | jq '.status'
curl -s https://api.company.com/filter/health | jq '.status'
curl -s https://api.company.com/summarise/health | jq '.status'
curl -s https://api.company.com/alert/health | jq '.status'
```

**Expected Output:**
```json
{
  "status": "healthy",
  "agent_type": "coordinator",
  "version": "1.0.0",
  "uptime": "active"
}
```

### Infrastructure Health Check

```bash
# Check database
docker exec postgres-reddit-watcher pg_isready -U postgres

# Check Redis
docker exec redis-reddit-watcher redis-cli ping

# Check disk space
df -h | grep -E '(/$|/var|/opt)'
```

## Step 3: Access Monitoring Dashboards (2 minutes)

### Grafana Dashboard

1. **Open browser**: https://grafana.company.com/reddit-watcher
2. **Login** with your company credentials
3. **Navigate to** "Reddit Watcher Overview" dashboard
4. **Verify** all panels show green status

### Key Metrics to Check

- **System Health**: All agents should show "UP"
- **Response Times**: Should be < 1 second
- **Error Rates**: Should be < 1%
- **CPU/Memory**: Should be < 70%

### Prometheus Alerts

1. **Open**: https://prometheus.company.com/alerts
2. **Check**: No firing alerts
3. **Review**: Any warning-level alerts

## Step 4: Verify Recent Operations (3 minutes)

### Check Recent Workflows

```bash
# View recent workflow executions
curl -s -H "X-API-Key: $API_KEY" \
  "https://api.company.com/coordinator/workflows?limit=5" | jq '.'
```

### Review Recent Logs

```bash
# Check for any errors in last hour
docker-compose logs --since=1h | grep -i "error\|exception" | tail -10

# Check application logs
tail -f /var/log/reddit-watcher/application.log
```

### Verify Backups

```bash
# Check latest backup
ls -la /backup/postgres/ | head -5

# Verify backup timestamp (should be < 24 hours old)
stat /backup/postgres/reddit_watcher_$(date +%Y%m%d)*.sql.gz
```

## Step 5: Test Basic Operations (3 minutes)

### Test Service Discovery

```bash
# Check agent discovery
curl -s https://api.company.com/coordinator/discover | jq '.agents | keys[]'
```

**Expected Output:**
```
"alert"
"coordinator"
"filter"
"retrieval"
"summarise"
```

### Test Agent Communication

```bash
# Test direct skill invocation
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {}}' \
  "https://api.company.com/coordinator/skills/health_check"
```

### Test Alert System

```bash
# Send test notification
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"channels": ["slack"], "test": true}}' \
  "https://api.company.com/alert/skills/test_notifications"
```

## Step 6: Join Communication Channels (2 minutes)

### Slack Channels

1. **Join channels**:
   - #reddit-watcher-support
   - #reddit-watcher-alerts
   - #reddit-watcher-general

2. **Pin important messages**:
   - On-call rotation schedule
   - Emergency contact list
   - Key documentation links

3. **Introduce yourself** in #reddit-watcher-general

### Email Lists

- **Subscribe to**: operations@company.com
- **Set up filters** for reddit-watcher alerts
- **Add contacts**: Key team members

## Common First-Day Tasks

### Morning Health Check Routine

```bash
# Create a morning health check script
cat > ~/morning-check.sh << 'EOF'
#!/bin/bash
echo "=== Reddit Watcher Morning Health Check ==="
echo "Date: $(date)"
echo

echo "1. System Health:"
./scripts/health-check.sh

echo -e "\n2. Overnight Alerts:"
curl -s http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

echo -e "\n3. Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo -e "\n4. Recent Errors:"
docker-compose logs --since=12h | grep -i "error" | wc -l

echo "=== Health Check Complete ==="
EOF

chmod +x ~/morning-check.sh
```

### Set Up Personal Monitoring

```bash
# Create personal dashboard bookmark
echo "https://grafana.company.com/d/reddit-watcher-overview?refresh=30s" > ~/dashboard.url

# Set up log monitoring alias
echo "alias logs='docker-compose logs --tail=100 --follow'" >> ~/.bashrc

# Create quick commands
echo "alias health='./scripts/health-check.sh'" >> ~/.bashrc
echo "alias status='docker-compose ps'" >> ~/.bashrc
```

## Verification Checklist

**System Access:**
- [ ] Can SSH to production server
- [ ] Can execute Docker commands
- [ ] Can access application directory
- [ ] Can view logs

**Monitoring Access:**
- [ ] Can access Grafana dashboard
- [ ] Can view system metrics
- [ ] Can see alert status
- [ ] Can access log management

**Communication:**
- [ ] Joined Slack channels
- [ ] Subscribed to email lists
- [ ] Have emergency contact info
- [ ] Know escalation procedures

**Basic Operations:**
- [ ] Can check system health
- [ ] Can view recent workflows
- [ ] Can test agent communication
- [ ] Can send test alerts

## Next Steps

### Complete Training Program

1. **Week 1**: [New User Training](./training/new-user-training.md)
2. **Week 2**: [Operations Procedures](./operations-dashboard.md)
3. **Week 3**: [Alert Management](./alert-management.md)
4. **Week 4**: [Troubleshooting](./troubleshooting-guide.md)

### Read Essential Documentation

- [System Overview](./system-overview.md)
- [Health Monitoring](./health-monitoring.md)
- [Daily Operations](../runbooks/daily-operations.md)
- [Incident Response](../runbooks/incident-response.md)

### Shadow Experienced Operator

- Observe daily operations routine
- Practice alert response procedures
- Learn troubleshooting techniques
- Understand escalation processes

## Getting Help

### Immediate Questions
- **Slack**: #reddit-watcher-support
- **Email**: support@company.com
- **Phone**: +1-555-SUPPORT

### Documentation Issues
- **Missing info**: Contact docs team
- **Outdated procedures**: Report in Slack
- **Access problems**: Contact IT support

### Training Questions
- **Training schedule**: training@company.com
- **Skill development**: Discuss with manager
- **Certification**: HR department

## Common Beginner Mistakes

### ❌ Don't Do This
- Don't restart services without checking logs first
- Don't ignore warning alerts
- Don't make configuration changes without approval
- Don't skip the health check routine

### ✅ Do This Instead
- Always check logs before taking action
- Investigate all alerts, even warnings
- Follow change management procedures
- Maintain consistent monitoring routine

---

**Congratulations!** You're now ready to begin operations support for Reddit Technical Watcher.

*Next: [System Overview](./system-overview.md)*
