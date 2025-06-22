# New User Training Program

Comprehensive 2-week training program for new operations staff joining the Reddit Technical Watcher team.

## Training Overview

**Duration**: 2 weeks (80 hours)
**Format**: Hands-on training with mentorship
**Prerequisites**: Basic Linux knowledge, Docker familiarity
**Certification**: Level 1 Operations Certification

## Week 1: System Fundamentals

### Day 1: System Introduction (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Reddit Technical Watcher overview and business purpose
- System architecture and component relationships
- A2A (Agent-to-Agent) protocol introduction
- Development vs. production environments

**Hands-On Activities:**

```bash
# System exploration
ssh ops@prod-reddit-watcher.company.com
cd /opt/reddit-watcher
ls -la
cat README.md

# Check system architecture
docker-compose ps
docker network ls
docker volume ls

# Explore agent endpoints
curl https://api.company.com/coordinator/.well-known/agent.json | jq '.'
```

**Learning Objectives:**

- Understand system purpose and business value
- Identify all system components
- Navigate production environment
- Access basic documentation

#### Afternoon Session (4 hours)

**Topics:**

- User roles and responsibilities
- Security policies and access control
- Communication channels and escalation procedures
- Documentation structure and resources

**Hands-On Activities:**

```bash
# Access management systems
# - Grafana dashboard tour
# - Slack channel overview
# - Documentation portal

# Security verification
whoami
groups
sudo -l

# Communication setup
# - Join Slack channels
# - Set up email filters
# - Add emergency contacts
```

**Assessment:**

- Quiz: System components and architecture
- Practical: Navigate documentation and find specific information
- Role-play: Basic communication scenarios

### Day 2: Monitoring and Health Checks (8 hours)

#### Morning Session (4 hours)

**Topics:**

- System health monitoring concepts
- Grafana dashboard overview
- Prometheus metrics and alerting
- Log management and analysis

**Hands-On Activities:**

```bash
# Health check procedures
./scripts/health-check.sh
curl -s https://api.company.com/coordinator/health | jq '.'

# Grafana exploration
# - Navigate to Reddit Watcher Overview dashboard
# - Understand key metrics and panels
# - Set up personal dashboard preferences

# Log analysis
docker-compose logs --tail=100
grep -i "error" /var/log/reddit-watcher/application.log
```

**Learning Objectives:**

- Perform comprehensive health checks
- Navigate monitoring dashboards effectively
- Identify normal vs. abnormal system behavior
- Extract useful information from logs

#### Afternoon Session (4 hours)

**Topics:**

- Performance metrics interpretation
- Capacity planning basics
- Trend analysis and pattern recognition
- Proactive monitoring techniques

**Hands-On Activities:**

```bash
# Performance monitoring
docker stats --no-stream
free -h
df -h

# Metric analysis exercises
# - Identify performance trends
# - Recognize anomaly patterns
# - Practice metric correlation

# Monitoring tool practice
# - Create custom Grafana queries
# - Set up personal alerts
# - Practice log searching
```

**Assessment:**

- Practical: Perform complete system health check
- Analysis: Identify issues from provided metrics
- Exercise: Create monitoring dashboard

### Day 3: Agent Architecture (8 hours)

#### Morning Session (4 hours)

**Topics:**

- A2A protocol deep dive
- Individual agent responsibilities
- Service discovery mechanism
- Inter-agent communication patterns

**Hands-On Activities:**

```bash
# Agent discovery
curl -s https://api.company.com/coordinator/discover | jq '.'

# Agent card exploration
for agent in coordinator retrieval filter summarise alert; do
  echo "=== $agent Agent ==="
  curl -s https://api.company.com/$agent/.well-known/agent.json | jq '.skills[].name'
done

# A2A communication testing
./scripts/test-a2a-communication.sh
```

**Learning Objectives:**

- Understand A2A protocol implementation
- Identify each agent's role and capabilities
- Verify service discovery functionality
- Test inter-agent communication

#### Afternoon Session (4 hours)

**Topics:**

- Workflow orchestration concepts
- Data flow through the system
- Error handling and recovery mechanisms
- Circuit breaker patterns

**Hands-On Activities:**

```bash
# Workflow testing
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"topics": ["test"]}}' \
  "https://api.company.com/coordinator/skills/orchestrate_workflow"

# Data flow observation
# - Monitor workflow execution
# - Track data transformation between agents
# - Observe error handling

# Circuit breaker testing
./scripts/test-circuit-breakers.sh
```

**Assessment:**

- Diagram: Draw complete system data flow
- Practical: Execute and monitor a workflow
- Troubleshooting: Identify agent communication issues

### Day 4: Database and Infrastructure (8 hours)

#### Morning Session (4 hours)

**Topics:**

- PostgreSQL database structure
- Redis service discovery
- Docker container management
- Backup and recovery procedures

**Hands-On Activities:**

```bash
# Database exploration
docker exec postgres-reddit-watcher psql -U postgres -d reddit_watcher -c "\dt"
docker exec postgres-reddit-watcher psql -U postgres -d reddit_watcher -c "SELECT * FROM workflow_executions LIMIT 5;"

# Redis exploration
docker exec redis-reddit-watcher redis-cli keys "*"
docker exec redis-reddit-watcher redis-cli hgetall "agent:coordinator"

# Container management
docker-compose logs postgres --tail=50
docker inspect postgres-reddit-watcher | jq '.[0].State'
```

**Learning Objectives:**

- Navigate database structure
- Understand Redis usage patterns
- Manage Docker containers safely
- Verify backup procedures

#### Afternoon Session (4 hours)

**Topics:**

- Network configuration and connectivity
- Volume management and persistence
- Resource limits and monitoring
- Security considerations

**Hands-On Activities:**

```bash
# Network analysis
docker network inspect reddit-watcher_default
netstat -tulpn | grep -E ':(8000|8001|8002|8003|8004|5432|6379)'

# Volume inspection
docker volume ls
docker volume inspect reddit-watcher_postgres-data

# Security verification
# - Check file permissions
# - Verify encrypted connections
# - Review access controls
```

**Assessment:**

- Practical: Database query and backup verification
- Exercise: Container restart and health verification
- Security: Access control verification

### Day 5: Basic Operations (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Daily operations checklist
- Routine maintenance tasks
- Log rotation and cleanup
- Performance monitoring

**Hands-On Activities:**

```bash
# Daily operations practice
./scripts/daily-health-check.sh

# Maintenance tasks
sudo logrotate /etc/logrotate.d/reddit-watcher
docker system df
docker system prune -f

# Performance monitoring
./scripts/performance-monitor.sh --duration=30m
```

**Learning Objectives:**

- Execute daily operations checklist
- Perform routine maintenance safely
- Monitor system performance trends
- Identify when escalation is needed

#### Afternoon Session (4 hours)

**Topics:**

- Documentation usage and updates
- Incident reporting procedures
- Change management processes
- Team communication protocols

**Hands-On Activities:**

```bash
# Documentation practice
# - Update operational logs
# - Report documentation issues
# - Practice using troubleshooting guides

# Communication exercises
# - Practice incident reporting
# - Role-play escalation scenarios
# - Team coordination activities
```

**Assessment:**

- Comprehensive: Complete daily operations cycle
- Communication: Incident reporting simulation
- Documentation: Update procedures based on experience

## Week 2: Alert Management and Troubleshooting

### Day 6: Alert Management (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Alert classification and prioritization
- Prometheus alert rules
- Notification channels (Slack, email)
- Alert response procedures

**Hands-On Activities:**

```bash
# Alert exploration
curl -s http://prometheus:9090/api/v1/alerts | jq '.data.alerts[]'

# Alert rule analysis
cat /etc/prometheus/rules/reddit_watcher_alerts.yml

# Notification testing
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"channels": ["slack"], "test": true}}' \
  "https://api.company.com/alert/skills/test_notifications"
```

**Learning Objectives:**

- Classify alerts by severity and impact
- Understand alert rule configuration
- Test notification delivery
- Follow proper response procedures

#### Afternoon Session (4 hours)

**Topics:**

- Alert investigation techniques
- Root cause analysis basics
- Documentation requirements
- Escalation criteria and procedures

**Hands-On Activities:**

```bash
# Alert simulation exercises
# - Generate test alerts
# - Practice investigation procedures
# - Document findings

# Escalation practice
# - Role-play escalation scenarios
# - Practice communication templates
# - Understand escalation timelines
```

**Assessment:**

- Simulation: Complete alert response cycle
- Analysis: Root cause investigation exercise
- Communication: Escalation procedure demonstration

### Day 7: Basic Troubleshooting (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Troubleshooting methodology
- Log analysis techniques
- Common failure patterns
- Diagnostic tool usage

**Hands-On Activities:**

```bash
# Troubleshooting exercises
./scripts/troubleshooting-scenarios.sh

# Log analysis practice
grep -i "error\|exception\|fail" /var/log/reddit-watcher/*.log
journalctl -u reddit-watcher --since="1 hour ago"

# Diagnostic tool practice
./scripts/system-diagnostics.sh
./scripts/agent-diagnostics.sh coordinator
```

**Learning Objectives:**

- Apply systematic troubleshooting approach
- Extract relevant information from logs
- Use diagnostic tools effectively
- Recognize when to escalate

#### Afternoon Session (4 hours)

**Topics:**

- Agent-specific troubleshooting
- Database connectivity issues
- Network connectivity problems
- Performance troubleshooting basics

**Hands-On Activities:**

```bash
# Agent troubleshooting scenarios
# - Agent not responding
# - Service discovery failures
# - A2A communication issues

# Infrastructure troubleshooting
# - Database connection problems
# - Redis connectivity issues
# - Docker container problems

# Performance issue diagnosis
# - High CPU usage investigation
# - Memory leak detection
# - Slow response time analysis
```

**Assessment:**

- Practical: Troubleshoot provided scenarios
- Analysis: Performance issue investigation
- Documentation: Create troubleshooting report

### Day 8: Advanced Operations (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Configuration management
- Backup and recovery procedures
- Update and deployment processes
- Capacity planning basics

**Hands-On Activities:**

```bash
# Configuration management
# - Review configuration files
# - Practice safe configuration changes
# - Understand rollback procedures

# Backup procedures
./scripts/backup-database.sh
./scripts/verify-backup.sh

# Deployment observation
# - Watch deployment process
# - Understand rollback procedures
# - Practice health verification
```

**Learning Objectives:**

- Manage system configuration safely
- Execute backup and recovery procedures
- Understand deployment processes
- Plan for capacity requirements

#### Afternoon Session (4 hours)

**Topics:**

- Security monitoring and compliance
- Performance optimization techniques
- Automation and scripting basics
- Continuous improvement processes

**Hands-On Activities:**

```bash
# Security monitoring
./scripts/security-audit.sh
grep -i "auth\|login\|fail" /var/log/reddit-watcher/security.log

# Performance optimization
# - Review performance metrics
# - Identify optimization opportunities
# - Practice tuning procedures

# Script development
# - Create custom monitoring scripts
# - Automate routine tasks
# - Practice bash scripting
```

**Assessment:**

- Security: Security audit and reporting
- Performance: Optimization recommendations
- Automation: Create useful operations script

### Day 9: Emergency Procedures (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Emergency response procedures
- Disaster recovery planning
- System restoration procedures
- Communication during emergencies

**Hands-On Activities:**

```bash
# Emergency drill simulation
# - System failure scenario
# - Practice emergency procedures
# - Communication coordination

# Recovery procedures
./scripts/emergency-restore.sh
./scripts/verify-system-recovery.sh

# Documentation during emergencies
# - Practice incident logging
# - Emergency communication templates
# - Stakeholder notifications
```

**Learning Objectives:**

- Execute emergency response procedures
- Coordinate during crisis situations
- Perform system recovery operations
- Maintain clear communication

#### Afternoon Session (4 hours)

**Topics:**

- Post-incident procedures
- Root cause analysis techniques
- System hardening and prevention
- Lessons learned documentation

**Hands-On Activities:**

```bash
# Post-incident activities
# - Incident report writing
# - Root cause analysis practice
# - Prevention measure implementation

# System hardening
# - Security configuration review
# - Monitoring enhancement
# - Process improvement identification
```

**Assessment:**

- Simulation: Complete emergency response
- Analysis: Post-incident review and reporting
- Improvement: System hardening recommendations

### Day 10: Certification and Evaluation (8 hours)

#### Morning Session (4 hours)

**Topics:**

- Training review and consolidation
- Knowledge gap identification
- Skill demonstration preparation
- Certification requirements review

**Activities:**

- Comprehensive review of all training materials
- Practice exercises for weak areas
- Preparation for practical assessment
- Final questions and clarifications

#### Afternoon Session (4 hours)

**Final Assessment:**

**Written Exam (2 hours):**

- System architecture and components
- Alert classification and response
- Troubleshooting methodology
- Security and compliance

**Practical Assessment (2 hours):**

- Complete system health check
- Investigate and resolve simulated issues
- Emergency response simulation
- Documentation and communication

**Certification Requirements:**

- Written exam score ≥ 80%
- Practical assessment pass
- Mentor recommendation
- Completion of all training modules

## Training Resources

### Required Reading

- [System Overview](../system-overview.md)
- [Operations Dashboard](../operations-dashboard.md)
- [Health Monitoring](../health-monitoring.md)
- [Daily Operations](../../runbooks/daily-operations.md)

### Reference Materials

- [API Documentation](../../api/)
- [Troubleshooting Guide](../../troubleshooting/)
- [Runbooks](../../runbooks/)
- [Architecture Documentation](../../architecture/)

### Practice Environments

- **Training Environment**: training.company.com
- **Sandbox Environment**: sandbox.company.com
- **Simulation Tools**: Available on training systems

## Mentorship Program

### Assigned Mentor

Each trainee is assigned an experienced operations team member as mentor:

- Daily check-ins during training
- Hands-on guidance during exercises
- Assessment and feedback
- Ongoing support after certification

### Mentorship Activities

- Shadow mentor during real operations
- Participate in actual incident response
- Practice procedures in production environment
- Receive personalized feedback and coaching

## Continuing Education

### Monthly Training Sessions

- New feature training
- Advanced troubleshooting techniques
- Security updates and best practices
- Process improvements and updates

### Quarterly Assessments

- Skills evaluation and gap analysis
- Performance review and feedback
- Career development planning
- Advanced training recommendations

### Annual Certification Renewal

- Updated knowledge assessment
- Hands-on skills verification
- Process and procedure updates
- Continuing education requirements

---

*Next: [Administrator Training](./administrator-training.md)*
