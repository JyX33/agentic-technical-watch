# User Guide & Training Materials

Comprehensive user documentation and training materials for operations staff managing the Reddit Technical Watcher system.

## Documentation Structure

### Getting Started
- **[Quick Start Guide](./quick-start.md)** - Get up and running in 15 minutes
- **[System Overview](./system-overview.md)** - Understand the architecture and components
- **[User Roles](./user-roles.md)** - Different user types and their responsibilities

### Daily Operations
- **[Operations Dashboard](./operations-dashboard.md)** - Using the monitoring dashboard
- **[Health Monitoring](./health-monitoring.md)** - Monitoring system health and performance
- **[Alert Management](./alert-management.md)** - Managing and responding to alerts

### Administration Tasks
- **[Configuration Management](./configuration-management.md)** - Managing system configuration
- **[User Management](./user-management.md)** - Managing user access and permissions
- **[Backup Management](./backup-management.md)** - Database backup and recovery procedures

### Advanced Operations
- **[Performance Tuning](./performance-tuning.md)** - Optimizing system performance
- **[Troubleshooting](./troubleshooting-guide.md)** - Common issues and solutions
- **[Maintenance Procedures](./maintenance-procedures.md)** - Routine maintenance tasks

### Training Programs
- **[New User Training](./training/new-user-training.md)** - 2-week training program for new staff
- **[Administrator Training](./training/administrator-training.md)** - Advanced training for administrators
- **[Emergency Response Training](./training/emergency-response-training.md)** - Emergency procedures training

## User Roles and Responsibilities

### Operations Operator (Level 1)
**Responsibilities:**
- Monitor system health dashboard
- Respond to basic alerts
- Perform routine health checks
- Escalate complex issues

**Required Training:**
- [New User Training](./training/new-user-training.md)
- [Health Monitoring](./health-monitoring.md)
- [Alert Management](./alert-management.md)

### Systems Administrator (Level 2)
**Responsibilities:**
- Manage system configuration
- Perform maintenance tasks
- Troubleshoot complex issues
- Manage user access

**Required Training:**
- All Level 1 training
- [Administrator Training](./training/administrator-training.md)
- [Configuration Management](./configuration-management.md)
- [Performance Tuning](./performance-tuning.md)

### Senior Administrator (Level 3)
**Responsibilities:**
- System architecture decisions
- Emergency response leadership
- Advanced troubleshooting
- Training coordination

**Required Training:**
- All Level 2 training
- [Emergency Response Training](./training/emergency-response-training.md)
- [System Architecture](../architecture/)
- [Incident Management](../runbooks/incident-response.md)

## Quick Reference

### System URLs
- **Production Dashboard**: https://monitor.company.com/reddit-watcher
- **Grafana Monitoring**: https://grafana.company.com/reddit-watcher
- **Log Management**: https://logs.company.com/reddit-watcher
- **Status Page**: https://status.company.com

### API Endpoints
```bash
# Health checks
curl https://api.company.com/coordinator/health
curl https://api.company.com/retrieval/health
curl https://api.company.com/filter/health
curl https://api.company.com/summarise/health
curl https://api.company.com/alert/health

# Service discovery
curl https://api.company.com/coordinator/discover

# System metrics
curl https://api.company.com/coordinator/metrics
```

### Common Commands
```bash
# Check system status
./scripts/system-status.sh

# View logs
docker-compose logs --tail=100

# Restart service
docker-compose restart service-name

# Check service health
./scripts/health-check.sh
```

## Support and Resources

### Internal Support
- **Help Desk**: helpdesk@company.com
- **Operations Team**: operations@company.com
- **Engineering Team**: engineering@company.com

### Communication Channels
- **Slack Support**: #reddit-watcher-support
- **Emergency**: #reddit-watcher-incidents
- **General**: #reddit-watcher-general

### Documentation Resources
- **API Documentation**: [docs/api/](../api/)
- **Troubleshooting**: [docs/troubleshooting/](../troubleshooting/)
- **Runbooks**: [docs/runbooks/](../runbooks/)

### External Resources
- **Docker Documentation**: https://docs.docker.com/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Redis Documentation**: https://redis.io/docs/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/

## Training Schedule

### New User Onboarding (2 weeks)
- **Week 1**: System overview, basic operations, monitoring
- **Week 2**: Alert management, basic troubleshooting, procedures

### Quarterly Training Updates
- **Q1**: Security updates and best practices
- **Q2**: Performance optimization techniques
- **Q3**: New features and system updates
- **Q4**: Emergency response drill and review

### Annual Certification
- **Level 1**: Basic operations certification
- **Level 2**: Advanced administration certification
- **Level 3**: Expert troubleshooting certification

## Feedback and Improvement

### Documentation Feedback
- **Feedback Form**: https://forms.company.com/reddit-watcher-docs
- **Email**: docs-feedback@company.com
- **Slack**: #reddit-watcher-docs

### Training Feedback
- **Training Evaluation**: End of each training session
- **Quarterly Review**: Training effectiveness assessment
- **Annual Survey**: Comprehensive training needs analysis

### Continuous Improvement
- Monthly documentation review
- Quarterly training content updates
- Annual curriculum revision
- Regular user feedback integration

## Getting Help

### Immediate Support
1. **Check this documentation** for common issues
2. **Search Slack history** in #reddit-watcher-support
3. **Contact help desk** for account/access issues
4. **Escalate to on-call** for system issues

### Escalation Process
1. **Level 1**: Self-service documentation
2. **Level 2**: Help desk or team lead
3. **Level 3**: Senior administrator
4. **Level 4**: Engineering team

### Training Requests
- **New user training**: Contact training@company.com
- **Specific skill training**: Submit request via training portal
- **Group training**: Contact training coordinator
- **Custom training**: Discuss with team manager

---

*Welcome to the Reddit Technical Watcher operations team!*
