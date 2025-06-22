# Disaster Recovery Runbook

## Overview

This runbook provides comprehensive procedures for recovering the Reddit Technical Watcher system from various disaster scenarios, including complete system failures, data corruption, security breaches, and infrastructure outages.

## Table of Contents

- [Disaster Categories](#disaster-categories)
- [Recovery Time Objectives](#recovery-time-objectives)
- [Backup Strategy](#backup-strategy)
- [Recovery Procedures](#recovery-procedures)
- [Data Recovery](#data-recovery)
- [Security Incident Response](#security-incident-response)
- [Communication Procedures](#communication-procedures)
- [Post-Recovery Procedures](#post-recovery-procedures)

## Disaster Categories

### Level 1: Service Degradation
**Impact:** Single service failure, reduced functionality
**RTO:** 15 minutes
**RPO:** 1 hour

**Examples:**
- Single agent failure
- External API timeout
- Memory pressure

### Level 2: Partial System Failure
**Impact:** Multiple services affected, significant functionality loss
**RTO:** 1 hour
**RPO:** 4 hours

**Examples:**
- Database connectivity issues
- Redis failure
- Multiple agent failures

### Level 3: Complete System Failure
**Impact:** Total system unavailability
**RTO:** 4 hours
**RPO:** 24 hours

**Examples:**
- Server hardware failure
- Data center outage
- Complete data corruption

### Level 4: Security Incident
**Impact:** Data breach or system compromise
**RTO:** Variable (depends on investigation)
**RPO:** Point of compromise

**Examples:**
- Unauthorized access
- Data exfiltration
- Malware infection

### Level 5: Catastrophic Loss
**Impact:** Complete infrastructure loss
**RTO:** 24 hours
**RPO:** 24 hours

**Examples:**
- Natural disasters
- Complete data center loss
- Hosting provider failure

## Recovery Time Objectives

| Component | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 |
|-----------|---------|---------|---------|---------|---------|
| Agent Services | 5 min | 30 min | 2 hours | 8 hours | 24 hours |
| Database | 10 min | 1 hour | 4 hours | 24 hours | 48 hours |
| Monitoring | 15 min | 1 hour | 2 hours | 4 hours | 24 hours |
| Complete System | 15 min | 1 hour | 4 hours | 24 hours | 48 hours |

## Backup Strategy

### Automated Backups

**Database Backups:**
```bash
#!/bin/bash
# automated_backup.sh

BACKUP_DIR="/var/backups/reddit-watcher"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
docker-compose -f docker-compose.prod.yml exec -T db pg_dump \
    -U reddit_watcher_user \
    -d reddit_watcher \
    --clean --if-exists --create --verbose \
    | gzip > "$BACKUP_DIR/reddit_watcher_db_$TIMESTAMP.sql.gz"

# Configuration backup
tar -czf "$BACKUP_DIR/config_$TIMESTAMP.tar.gz" \
    .env.prod \
    docker-compose.prod.yml \
    docker/ \
    docs/

# Data directory backup
tar -czf "$BACKUP_DIR/data_$TIMESTAMP.tar.gz" \
    data/

# Remove old backups
find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $TIMESTAMP"
```

**Schedule with cron:**
```bash
# Daily backup at 2 AM
0 2 * * * /path/to/automated_backup.sh

# Weekly full backup on Sunday at 1 AM
0 1 * * 0 /path/to/full_system_backup.sh
```

### Off-site Backup

**Cloud Storage Sync:**
```bash
#!/bin/bash
# cloud_backup_sync.sh

LOCAL_BACKUP_DIR="/var/backups/reddit-watcher"
CLOUD_BUCKET="s3://your-backup-bucket/reddit-watcher"

# Sync to cloud storage
aws s3 sync "$LOCAL_BACKUP_DIR" "$CLOUD_BUCKET" --delete

# Verify sync
aws s3 ls "$CLOUD_BUCKET" --recursive | tail -10

echo "Cloud backup sync completed"
```

### Backup Verification

**Daily Backup Verification:**
```bash
#!/bin/bash
# verify_backup.sh

BACKUP_DIR="/var/backups/reddit-watcher"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/reddit_watcher_db_*.sql.gz | head -1)

if [ -f "$LATEST_BACKUP" ]; then
    # Test backup integrity
    gunzip -t "$LATEST_BACKUP"
    if [ $? -eq 0 ]; then
        echo "✅ Backup integrity verified: $LATEST_BACKUP"

        # Test restore (to temporary database)
        docker run --rm --network reddit_watcher_internal \
            -v "$(dirname "$LATEST_BACKUP"):/backups" \
            postgres:15-alpine \
            sh -c "gunzip -c /backups/$(basename "$LATEST_BACKUP") | psql -h db -U reddit_watcher_user -d template1 -c 'CREATE DATABASE test_restore;'; psql -h db -U reddit_watcher_user -d test_restore"

        if [ $? -eq 0 ]; then
            echo "✅ Backup restore test successful"
            # Cleanup test database
            docker-compose -f docker-compose.prod.yml exec -T db psql -U reddit_watcher_user -d postgres -c "DROP DATABASE test_restore;"
        else
            echo "❌ Backup restore test failed"
            exit 1
        fi
    else
        echo "❌ Backup integrity check failed"
        exit 1
    fi
else
    echo "❌ No backup found"
    exit 1
fi
```

## Recovery Procedures

### Level 1: Service Degradation Recovery

**Single Agent Failure:**
```bash
# 1. Identify failed service
docker-compose -f docker-compose.prod.yml ps | grep -v "Up"

# 2. Check logs for failure reason
docker-compose -f docker-compose.prod.yml logs --since 30m [failed-service]

# 3. Restart service
docker-compose -f docker-compose.prod.yml restart [failed-service]

# 4. Verify recovery
curl -f http://localhost:[service-port]/health

# 5. Monitor for stability
watch -n 30 'docker-compose -f docker-compose.prod.yml ps [failed-service]'
```

**External API Issues:**
```bash
# 1. Verify external connectivity
curl -I https://reddit.com
curl -I https://generativelanguage.googleapis.com

# 2. Check API credentials
docker-compose -f docker-compose.prod.yml exec retrieval-agent python -c "
from reddit_watcher.config import get_settings
config = get_settings()
print('Reddit creds:', bool(config.reddit_client_id and config.reddit_client_secret))
print('Gemini creds:', bool(config.gemini_api_key))
"

# 3. Check rate limiting
docker-compose -f docker-compose.prod.yml logs | grep -i "rate limit"

# 4. Wait for rate limit reset or switch to fallback
# Reddit rate limits reset hourly
# Gemini has per-minute and per-day limits
```

### Level 2: Partial System Failure Recovery

**Database Connectivity Issues:**
```bash
# 1. Check database status
docker-compose -f docker-compose.prod.yml ps db
docker-compose -f docker-compose.prod.yml exec db pg_isready

# 2. Check database logs
docker-compose -f docker-compose.prod.yml logs db

# 3. Check connection pool
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT count(*) as connections, max_val as max_connections
FROM pg_stat_activity
CROSS JOIN (SELECT setting::int as max_val FROM pg_settings WHERE name = 'max_connections') s;"

# 4. Restart database if needed
docker-compose -f docker-compose.prod.yml restart db

# 5. Wait for database to be ready
timeout 60 bash -c 'until docker-compose -f docker-compose.prod.yml exec db pg_isready; do sleep 5; done'

# 6. Restart dependent services
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent
```

**Redis Service Discovery Failure:**
```bash
# 1. Check Redis status
docker-compose -f docker-compose.prod.yml ps redis
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ping

# 2. Check Redis memory usage
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info memory

# 3. Check registered agents
docker-compose -f docker-compose.prod.yml exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" keys "agent:*"

# 4. Restart Redis
docker-compose -f docker-compose.prod.yml restart redis

# 5. Re-register all agents
docker-compose -f docker-compose.prod.yml restart coordinator-agent retrieval-agent filter-agent summarise-agent alert-agent

# 6. Verify service discovery
curl -s http://localhost:8000/discover | jq '.agents | length'
```

### Level 3: Complete System Failure Recovery

**Server Hardware/OS Failure:**
```bash
# 1. Provision new server
# - Same or better specifications
# - Ubuntu 20.04 LTS or similar
# - Docker and Docker Compose installed

# 2. Restore from backup
scp backup-server:/var/backups/reddit-watcher/* ./backups/

# 3. Extract configuration
tar -xzf backups/config_YYYYMMDD_HHMMSS.tar.gz

# 4. Deploy system
./deploy_production.sh deploy

# 5. Restore database
LATEST_DB_BACKUP=$(ls -t backups/reddit_watcher_db_*.sql.gz | head -1)
gunzip -c "$LATEST_DB_BACKUP" | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres

# 6. Restore data directories
tar -xzf backups/data_YYYYMMDD_HHMMSS.tar.gz

# 7. Start all services
docker-compose -f docker-compose.prod.yml up -d

# 8. Verify system health
./deploy_production.sh validate
```

**Data Corruption Recovery:**
```bash
# 1. Stop all services immediately
docker-compose -f docker-compose.prod.yml down

# 2. Identify extent of corruption
# Check database
docker-compose -f docker-compose.prod.yml up -d db
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT tablename FROM pg_tables WHERE schemaname = 'public';"

# Check for table corruption
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';" | while read schema table; do
    echo "Checking $table..."
    docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "SELECT count(*) FROM $table;" || echo "❌ $table is corrupted"
done

# 3. Stop database
docker-compose -f docker-compose.prod.yml down

# 4. Restore from latest good backup
LATEST_BACKUP=$(ls -t /var/backups/reddit-watcher/reddit_watcher_db_*.sql.gz | head -1)
echo "Restoring from: $LATEST_BACKUP"

# Remove corrupted data
docker volume rm reddit_watcher_postgres_data

# Start database with fresh volume
docker-compose -f docker-compose.prod.yml up -d db

# Wait for database to be ready
sleep 30

# Restore backup
gunzip -c "$LATEST_BACKUP" | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres

# 5. Start all services
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify data integrity
./deploy_production.sh validate
```

### Level 4: Security Incident Recovery

**Security Breach Response:**
```bash
# 1. Immediate containment
# Stop all external-facing services
docker-compose -f docker-compose.prod.yml stop traefik coordinator-agent

# Change all passwords immediately
# Generate new secrets
openssl rand -base64 32  # New DB password
openssl rand -base64 32  # New Redis password
openssl rand -base64 32  # New A2A API key

# 2. Preserve evidence
# Create forensic backup
tar -czf incident_$(date +%Y%m%d_%H%M%S).tar.gz \
    data/ \
    /var/log/ \
    docker-compose.prod.yml \
    .env.prod

# Copy logs
docker-compose -f docker-compose.prod.yml logs > incident_logs_$(date +%Y%m%d_%H%M%S).log

# 3. Investigate breach
# Check for unauthorized access
docker-compose -f docker-compose.prod.yml logs | grep -E "(401|403|unauthorized|failed login)"

# Check for data exfiltration
docker-compose -f docker-compose.prod.yml logs | grep -E "(download|export|SELECT.*FROM|dump)"

# Check system integrity
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT count(*) FROM reddit_posts;
SELECT count(*) FROM workflow_executions;
SELECT max(created_at) FROM reddit_posts;
"

# 4. Clean recovery
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Remove potentially compromised images
docker image prune -a

# Rebuild from source
git pull origin main
docker-compose -f docker-compose.prod.yml build --no-cache

# Update all secrets in .env.prod
# Update API keys if potentially compromised

# 5. Restore from clean backup (pre-incident)
# Identify last known good backup before incident
CLEAN_BACKUP=$(ls -t /var/backups/reddit-watcher/reddit_watcher_db_*.sql.gz | grep "YYYYMMDD" | head -1)
gunzip -c "$CLEAN_BACKUP" | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres

# 6. Enhanced security deployment
# Deploy with additional security measures
./deploy_production.sh deploy

# 7. Monitor for continued threats
# Enhanced logging
# Additional access controls
# Network monitoring
```

### Level 5: Catastrophic Loss Recovery

**Complete Infrastructure Loss:**
```bash
# 1. Emergency response
# Contact hosting provider
# Verify cloud backups are accessible

# 2. Provision new infrastructure
# New server(s) with same or better specs
# Configure networking and security
# Install base software

# 3. Restore from cloud backups
aws s3 sync s3://your-backup-bucket/reddit-watcher ./backups/

# 4. Verify backup integrity
LATEST_BACKUP=$(ls -t backups/reddit_watcher_db_*.sql.gz | head -1)
gunzip -t "$LATEST_BACKUP"

# 5. Deploy from scratch
git clone https://github.com/your-org/agentic-technical-watch.git
cd agentic-technical-watch

# Extract configuration
tar -xzf backups/config_YYYYMMDD_HHMMSS.tar.gz

# Deploy system
./deploy_production.sh deploy

# 6. Restore all data
# Database
gunzip -c "$LATEST_BACKUP" | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres

# Data directories
tar -xzf backups/data_YYYYMMDD_HHMMSS.tar.gz

# Restart services with restored data
docker-compose -f docker-compose.prod.yml restart

# 7. Update DNS and external configurations
# Update DNS records to point to new server
# Update monitoring systems
# Update external service webhooks

# 8. Full system verification
./deploy_production.sh validate

# 9. Notify stakeholders of recovery
```

## Data Recovery

### Database Point-in-Time Recovery

**PostgreSQL PITR Setup:**
```bash
# Enable WAL archiving for PITR
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -c "
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f';
ALTER SYSTEM SET max_wal_senders = 3;
"

# Restart database to apply changes
docker-compose -f docker-compose.prod.yml restart db

# Create base backup
docker-compose -f docker-compose.prod.yml exec db pg_basebackup -U postgres -D /var/lib/postgresql/basebackup -Ft -z -P
```

**Recovery to Specific Time:**
```bash
# Stop database
docker-compose -f docker-compose.prod.yml stop db

# Remove current data
docker volume rm reddit_watcher_postgres_data

# Restore base backup
docker-compose -f docker-compose.prod.yml up -d db
sleep 30

# Copy base backup
docker-compose -f docker-compose.prod.yml exec db sh -c "
cd /var/lib/postgresql/data
tar -xzf /var/lib/postgresql/basebackup/base.tar.gz
"

# Create recovery configuration
cat > recovery.conf << EOF
restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'
recovery_target_time = '2024-01-01 12:00:00'
recovery_target_action = 'promote'
EOF

docker-compose -f docker-compose.prod.yml exec db cp recovery.conf /var/lib/postgresql/data/

# Restart for recovery
docker-compose -f docker-compose.prod.yml restart db
```

### Individual Data Recovery

**Recover Specific Reddit Posts:**
```bash
# Query backup for specific data
BACKUP_FILE="backups/reddit_watcher_db_YYYYMMDD_HHMMSS.sql.gz"

# Extract specific table data
gunzip -c "$BACKUP_FILE" | grep -A 1000 "COPY public.reddit_posts" | head -1000 > recovered_posts.sql

# Review and selectively restore
docker-compose -f docker-compose.prod.yml exec -T db psql -U reddit_watcher_user -d reddit_watcher -f recovered_posts.sql
```

**Recover Configuration:**
```bash
# Extract specific configuration from backup
tar -xzf backups/config_YYYYMMDD_HHMMSS.tar.gz --wildcards "*.env*"

# Compare with current configuration
diff .env.prod.backup .env.prod

# Restore specific settings
grep "REDDIT_CLIENT_ID" .env.prod.backup >> .env.prod
```

## Security Incident Response

### Incident Classification

**Level 1: Low Impact**
- Failed login attempts
- Minor configuration exposure
- Non-sensitive data access

**Level 2: Medium Impact**
- Unauthorized API access
- Configuration file exposure
- Limited data access

**Level 3: High Impact**
- Database access
- Credential compromise
- Data modification

**Level 4: Critical Impact**
- Full system compromise
- Data exfiltration
- Service disruption

### Response Procedures

**Immediate Response (0-1 hour):**
```bash
# 1. Contain the incident
docker-compose -f docker-compose.prod.yml stop traefik  # Stop external access

# 2. Preserve evidence
docker-compose -f docker-compose.prod.yml logs > incident_logs_$(date +%Y%m%d_%H%M%S).log
cp -r data/ incident_data_$(date +%Y%m%d_%H%M%S)/

# 3. Assess damage
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    schemaname, tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
ORDER BY n_tup_ins + n_tup_upd + n_tup_del DESC;"

# 4. Change critical passwords
# Generate new passwords for all services
# Update .env.prod with new credentials
# Restart services with new credentials
```

**Investigation (1-24 hours):**
```bash
# 1. Analyze logs for attack vectors
grep -E "(authentication|authorization|login|access)" incident_logs_*.log

# 2. Check for data exfiltration
grep -E "(SELECT|COPY|pg_dump|export)" incident_logs_*.log

# 3. Identify compromised accounts
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT * FROM audit_log WHERE event_time > 'YYYY-MM-DD HH:MM:SS';"

# 4. Check system integrity
find . -name "*.py" -exec sha256sum {} \; > system_hashes.txt
# Compare with known good hashes

# 5. Network analysis
netstat -tlnp
ss -tlnp
```

**Recovery (24-48 hours):**
```bash
# 1. Clean system rebuild
docker-compose -f docker-compose.prod.yml down
docker system prune -a --volumes

# 2. Restore from clean backup
CLEAN_BACKUP=$(ls -t /var/backups/reddit-watcher/reddit_watcher_db_*.sql.gz | head -1)
# Verify backup is from before incident

# 3. Enhanced security deployment
# Implement additional security measures
# Update all credentials
# Deploy with security hardening

# 4. Monitoring enhancement
# Additional logging
# Real-time alerting
# Behavioral analysis
```

## Communication Procedures

### Stakeholder Notification

**Internal Notifications:**
```yaml
Technical Team: technical-team@yourdomain.com
Management: management@yourdomain.com
Security Team: security@yourdomain.com
Legal Team: legal@yourdomain.com
```

**External Notifications:**
```yaml
Hosting Provider: support@hostinger.com
DNS Provider: support@dns-provider.com
External APIs:
  - Reddit: api-support@reddit.com
  - Google: cloud-support@google.com
```

### Incident Communication Template

```
Subject: [SEVERITY] Reddit Technical Watcher Incident - [BRIEF DESCRIPTION]

INCIDENT SUMMARY
================
Start Time: YYYY-MM-DD HH:MM:SS UTC
Detection Time: YYYY-MM-DD HH:MM:SS UTC
Severity: [Low/Medium/High/Critical]
Status: [Investigating/Contained/Resolved]

IMPACT
======
Affected Services: [List affected components]
User Impact: [Description of user-facing impact]
Data Impact: [Any data loss or exposure]

TIMELINE
========
HH:MM - [Event description]
HH:MM - [Response action]
HH:MM - [Status update]

CURRENT STATUS
==============
[Current situation and ongoing actions]

NEXT UPDATE
===========
Next update scheduled: YYYY-MM-DD HH:MM:SS UTC
```

### Post-Incident Communication

```
Subject: [RESOLVED] Reddit Technical Watcher Incident - Post-Mortem

INCIDENT RESOLVED
=================
Resolution Time: YYYY-MM-DD HH:MM:SS UTC
Total Duration: X hours Y minutes
Final Status: Fully Resolved

ROOT CAUSE
==========
[Detailed explanation of what caused the incident]

RESOLUTION
==========
[Steps taken to resolve the incident]

IMPACT SUMMARY
==============
Service Availability: X.XX%
Data Loss: [None/Description]
Affected Users: [Number/Description]

LESSONS LEARNED
===============
[Key takeaways and improvements identified]

PREVENTION MEASURES
===================
[Steps being taken to prevent recurrence]

POST-MORTEM MEETING
===================
Date: YYYY-MM-DD
Time: HH:MM UTC
Participants: [List of attendees]
```

## Post-Recovery Procedures

### System Validation

**Complete Health Check:**
```bash
# 1. Full system validation
./deploy_production.sh validate

# 2. Performance baseline
docker stats --no-stream
curl -w "@curl-format.txt" -s http://localhost:8000/health

# 3. Data integrity verification
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher -c "
SELECT
    count(*) as total_posts,
    max(created_at) as latest_post,
    count(DISTINCT subreddit) as unique_subreddits
FROM reddit_posts;"

# 4. Workflow verification
# Trigger test workflow
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"test workflow"}]}},"id":"test"}' \
  http://localhost:8000/a2a
```

### Documentation Updates

**Incident Documentation:**
```bash
# Create incident report
cat > incident_report_$(date +%Y%m%d).md << EOF
# Incident Report - $(date +%Y-%m-%d)

## Incident Details
- Start Time:
- End Time:
- Duration:
- Severity:
- Root Cause:

## Impact
- Services Affected:
- Data Loss:
- Downtime:

## Resolution
- Actions Taken:
- Recovery Method:
- Verification:

## Lessons Learned
- What Went Well:
- What Could Be Improved:
- Action Items:

## Prevention
- Immediate Actions:
- Long-term Improvements:
EOF
```

**Update Runbooks:**
```bash
# Update this runbook with lessons learned
# Add new failure scenarios encountered
# Update recovery procedures based on experience
# Improve automation scripts
```

### Monitoring Enhancement

**Additional Monitoring:**
```bash
# Enhanced alerting rules
cat >> docker/prometheus/rules/reddit_watcher_alerts.yml << EOF

  - name: incident_prevention
    rules:
      - alert: SuspiciousActivity
        expr: rate(http_requests_total{status=~"4.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Suspicious HTTP activity detected"

      - alert: UnusualDataPatterns
        expr: increase(database_query_duration_seconds[1h]) > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Unusual database query patterns detected"
EOF
```

### Security Hardening

**Post-Incident Security:**
```bash
# 1. Update all credentials
# Generate new strong passwords
# Rotate API keys
# Update access tokens

# 2. Implement additional security controls
# Add rate limiting
# Implement request signing
# Add audit logging

# 3. Network security
# Update firewall rules
# Implement network segmentation
# Add intrusion detection

# 4. Access controls
# Review user permissions
# Implement principle of least privilege
# Add multi-factor authentication where possible
```

### Backup Strategy Review

**Backup Improvements:**
```bash
# 1. Increase backup frequency
# Change from daily to every 6 hours for critical data

# 2. Add real-time replication
# Set up hot standby database
# Implement real-time data sync

# 3. Test restore procedures
# Weekly restore tests
# Automated backup verification
# Document restore times

# 4. Geographic distribution
# Store backups in multiple regions
# Implement cross-region replication
```

### Disaster Recovery Testing

**Regular DR Tests:**
```bash
#!/bin/bash
# disaster_recovery_test.sh

echo "=== Disaster Recovery Test - $(date) ==="

# 1. Simulate failure
echo "Simulating system failure..."
docker-compose -f docker-compose.prod.yml down

# 2. Measure detection time
echo "Starting recovery timer..."
START_TIME=$(date +%s)

# 3. Execute recovery
./deploy_production.sh rollback

# 4. Verify recovery
./deploy_production.sh validate

# 5. Calculate RTO
END_TIME=$(date +%s)
RTO=$((END_TIME - START_TIME))

echo "Recovery completed in $RTO seconds"
echo "Target RTO: 3600 seconds (1 hour)"

if [ $RTO -lt 3600 ]; then
    echo "✅ RTO target met"
else
    echo "❌ RTO target exceeded"
fi

# 6. Document results
echo "DR Test Results - $(date): RTO=$RTO seconds" >> dr_test_results.log
```

**Schedule Regular Tests:**
```bash
# Monthly DR test (first Sunday of each month)
0 3 1-7 * 0 [ $(date +%u) -eq 7 ] && /path/to/disaster_recovery_test.sh

# Quarterly full DR simulation
# (Manual execution with full team participation)
```

This disaster recovery runbook should be:
1. Reviewed and updated quarterly
2. Tested regularly through simulations
3. Validated against actual incidents
4. Updated based on infrastructure changes
5. Accessible to all operations team members
