# Production Deployment Guide

This comprehensive guide covers the complete production deployment process for the Reddit Technical Watcher system.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Deployment Process](#deployment-process)
- [Post-Deployment Verification](#post-deployment-verification)
- [Monitoring Setup](#monitoring-setup)
- [Troubleshooting](#troubleshooting)
- [Rollback Procedures](#rollback-procedures)

## Prerequisites

### System Requirements

**Minimum Production Requirements:**
- **CPU**: 4 cores (8 recommended)
- **RAM**: 8GB (16GB recommended)
- **Storage**: 100GB SSD (500GB recommended)
- **Network**: 1Gbps connection
- **OS**: Ubuntu 20.04 LTS or CentOS 8+

**Software Dependencies:**
- Docker 24.0+
- Docker Compose 2.20+
- curl
- jq
- Git 2.30+

### Network Requirements

**Required Ports:**
- `80/443`: HTTP/HTTPS (Traefik)
- `8000-8004`: Agent APIs (internal)
- `3000`: Grafana Dashboard
- `9090`: Prometheus
- `9093`: Alertmanager

**External Access Required:**
- Reddit API (`reddit.com`)
- Google Gemini API (`generativelanguage.googleapis.com`)
- SMTP server (for email alerts)
- Slack API (if using Slack notifications)

## Pre-Deployment Checklist

### 1. Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install additional tools
sudo apt install -y curl jq git htop
```

### 2. Configure Firewall

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 3000/tcp  # Grafana (restrict to admin IPs)
sudo ufw allow 9090/tcp  # Prometheus (restrict to admin IPs)
sudo ufw enable
```

### 3. Create Deployment User

```bash
# Create dedicated deployment user
sudo useradd -m -s /bin/bash reddit-watcher
sudo usermod -aG docker reddit-watcher

# Switch to deployment user
sudo su - reddit-watcher
```

### 4. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/agentic-technical-watch.git
cd agentic-technical-watch

# Checkout production tag
git checkout v1.0.0  # Use appropriate version tag
```

### 5. Configure Environment

```bash
# Copy and configure environment file
cp .env.prod.example .env.prod
chmod 600 .env.prod

# Edit with production values (see configuration guide below)
nano .env.prod
```

### Environment Configuration

**Critical Configuration Items:**

1. **Database Security:**
   ```env
   DB_PASSWORD=<generate-strong-password>
   REDIS_PASSWORD=<generate-strong-password>
   ```

2. **API Credentials:**
   ```env
   REDDIT_CLIENT_ID=<reddit-app-client-id>
   REDDIT_CLIENT_SECRET=<reddit-app-client-secret>
   GEMINI_API_KEY=<google-gemini-api-key>
   A2A_API_KEY=<generate-strong-api-key>
   ```

3. **Monitoring:**
   ```env
   GRAFANA_ADMIN_PASSWORD=<generate-strong-password>
   ALERTMANAGER_WEBHOOK_TOKEN=<generate-strong-token>
   ```

4. **Notifications:**
   ```env
   ALERT_EMAIL=alerts@yourdomain.com
   SMTP_SERVER=smtp.yourdomain.com
   SMTP_USERNAME=alerts@yourdomain.com
   SMTP_PASSWORD=<smtp-password>
   ```

5. **SSL/Domain:**
   ```env
   DOMAIN=yourdomain.com
   ACME_EMAIL=admin@yourdomain.com
   ```

## Deployment Process

### 1. Automated Deployment

The recommended method is using the automated deployment script:

```bash
# Make script executable
chmod +x deploy_production.sh

# Run full deployment
./deploy_production.sh deploy
```

### 2. Manual Deployment Steps

If you need to deploy manually or understand the process:

```bash
# 1. Validate environment
./deploy_production.sh validate

# 2. Create data directories
mkdir -p data/{postgres,redis,prometheus,grafana,alertmanager,traefik}

# 3. Build images
docker-compose -f docker-compose.prod.yml build

# 4. Start infrastructure
docker-compose -f docker-compose.prod.yml up -d db redis

# 5. Run migrations
docker-compose -f docker-compose.prod.yml run --rm coordinator-agent uv run alembic upgrade head

# 6. Start agents
docker-compose -f docker-compose.prod.yml up -d retrieval-agent filter-agent summarise-agent alert-agent coordinator-agent

# 7. Start monitoring
docker-compose -f docker-compose.prod.yml up -d prometheus grafana alertmanager node-exporter

# 8. Start reverse proxy
docker-compose -f docker-compose.prod.yml up -d traefik
```

### 3. Deployment Monitoring

Monitor deployment progress:

```bash
# Watch service status
watch docker-compose -f docker-compose.prod.yml ps

# Follow logs
docker-compose -f docker-compose.prod.yml logs -f

# Check specific service
docker-compose -f docker-compose.prod.yml logs coordinator-agent
```

## Post-Deployment Verification

### 1. Service Health Checks

```bash
# Check all services are running
docker-compose -f docker-compose.prod.yml ps

# Test health endpoints
curl -f http://localhost:8000/health  # Coordinator
curl -f http://localhost:8001/health  # Retrieval
curl -f http://localhost:8002/health  # Filter
curl -f http://localhost:8003/health  # Summarise
curl -f http://localhost:8004/health  # Alert
```

### 2. A2A Protocol Verification

```bash
# Test agent cards
curl -s http://localhost:8000/.well-known/agent.json | jq .

# Test service discovery
curl -s http://localhost:8000/discover | jq .

# Test agent communication
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"text":"test"}]}},"id":"test"}' \
  http://localhost:8000/a2a
```

### 3. Database Verification

```bash
# Connect to database
docker-compose -f docker-compose.prod.yml exec db psql -U reddit_watcher_user -d reddit_watcher

# Check tables exist
\dt

# Verify migrations
SELECT version_num FROM alembic_version;
```

### 4. Monitoring Stack Verification

- **Grafana**: http://localhost:3000 (admin / `$GRAFANA_ADMIN_PASSWORD`)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### 5. End-to-End Testing

```bash
# Test Reddit data retrieval
docker-compose -f docker-compose.prod.yml exec coordinator-agent \
  python -c "
import asyncio
from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.config import get_settings

async def test():
    config = get_settings()
    agent = CoordinatorAgent(config)
    # Trigger workflow
    result = await agent.execute_skill('trigger_monitoring_cycle', {})
    print('Workflow result:', result)

asyncio.run(test())
"
```

## Monitoring Setup

### 1. Configure Grafana Dashboards

1. Access Grafana at http://localhost:3000
2. Login with admin credentials
3. Verify dashboards are loaded:
   - **Reddit Watcher - System Overview**
   - **A2A Protocol Metrics**
   - **Infrastructure Metrics**

### 2. Configure Alerting

1. Verify Prometheus targets: http://localhost:9090/targets
2. Check alert rules: http://localhost:9090/alerts
3. Test Alertmanager: http://localhost:9093

### 3. Set Up External Monitoring

**Uptime Monitoring:**
```bash
# Configure external uptime monitoring for:
# - https://yourdomain.com/health
# - https://yourdomain.com:3000  # Grafana
# - https://yourdomain.com:9090  # Prometheus
```

**Log Aggregation:**
```bash
# Configure log forwarding to external service
# Docker logs are available at:
docker-compose -f docker-compose.prod.yml logs --since 1h
```

## Troubleshooting

### Common Issues

**1. Services Won't Start**
```bash
# Check Docker daemon
sudo systemctl status docker

# Check disk space
df -h

# Check memory usage
free -h

# Review service logs
docker-compose -f docker-compose.prod.yml logs [service-name]
```

**2. Database Connection Issues**
```bash
# Check database is running
docker-compose -f docker-compose.prod.yml ps db

# Test database connection
docker-compose -f docker-compose.prod.yml exec db pg_isready

# Check database logs
docker-compose -f docker-compose.prod.yml logs db
```

**3. Agent Communication Issues**
```bash
# Check Redis connectivity
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# Verify service discovery
curl http://localhost:8000/discover

# Check A2A protocol logs
docker-compose -f docker-compose.prod.yml logs coordinator-agent | grep -i a2a
```

**4. Monitoring Issues**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify Grafana data sources
curl -u admin:$GRAFANA_ADMIN_PASSWORD http://localhost:3000/api/datasources

# Check Alertmanager configuration
curl http://localhost:9093/api/v1/status
```

### Performance Tuning

**1. Resource Optimization**
```bash
# Monitor resource usage
docker stats

# Adjust resource limits in docker-compose.prod.yml
# Scale services if needed
docker-compose -f docker-compose.prod.yml up -d --scale retrieval-agent=2
```

**2. Database Performance**
```bash
# Monitor database performance
docker-compose -f docker-compose.prod.yml exec db \
  psql -U reddit_watcher_user -d reddit_watcher -c "
  SELECT query, calls, total_time, mean_time
  FROM pg_stat_statements
  ORDER BY total_time DESC LIMIT 10;"
```

## Rollback Procedures

### 1. Automatic Rollback

```bash
# Use deployment script for automatic rollback
./deploy_production.sh rollback
```

### 2. Manual Rollback

```bash
# 1. Stop current services
docker-compose -f docker-compose.prod.yml down

# 2. Restore database backup (if needed)
gunzip -c database_backups/reddit_watcher_backup_YYYYMMDD_HHMMSS.sql.gz | \
  docker-compose -f docker-compose.prod.yml exec -T db \
  psql -U reddit_watcher_user -d postgres

# 3. Checkout previous version
git checkout v1.0.0-previous  # Use appropriate tag

# 4. Restart services
docker-compose -f docker-compose.prod.yml up -d

# 5. Verify rollback
./deploy_production.sh validate
```

### 3. Emergency Procedures

**Complete System Failure:**
```bash
# 1. Stop all services
docker-compose -f docker-compose.prod.yml down

# 2. Clear Docker system (CAUTION: removes all data)
docker system prune -a --volumes

# 3. Restore from backups
# Follow backup restoration procedures

# 4. Redeploy from clean state
./deploy_production.sh deploy
```

## Maintenance

### Daily Tasks

```bash
# Check service health
./deploy_production.sh status

# Review logs for errors
docker-compose -f docker-compose.prod.yml logs --since 24h | grep -i error

# Monitor disk usage
df -h
```

### Weekly Tasks

```bash
# Create backup
./deploy_production.sh backup

# Review monitoring alerts
# Check Grafana dashboards
# Review system performance metrics
```

### Monthly Tasks

```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Review and rotate logs
# Update Docker images
# Security audit
```

## Security Considerations

### 1. Access Control

- Use strong passwords for all services
- Implement IP whitelisting for admin interfaces
- Regular security updates
- Monitor access logs

### 2. Network Security

- Configure firewall rules
- Use SSL/TLS for all communications
- VPN access for administrative tasks
- Network segmentation

### 3. Data Protection

- Encrypt data at rest
- Regular backups
- Secure backup storage
- Data retention policies

## Support and Documentation

- **System Logs**: `docker-compose -f docker-compose.prod.yml logs`
- **Monitoring**: http://localhost:3000
- **Health Status**: http://localhost:8000/health
- **Runbooks**: `/docs/runbooks/`
- **Configuration**: `/docs/operations/`

For additional support, see the troubleshooting guides in the `/docs/runbooks/` directory.
