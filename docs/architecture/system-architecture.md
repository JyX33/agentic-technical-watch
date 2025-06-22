# System Architecture

Detailed technical architecture of the Reddit Technical Watcher system, including component relationships, data flow, and integration patterns.

## System Overview

The Reddit Technical Watcher is a **microservices-based autonomous monitoring system** built on **Google's Agent-to-Agent (A2A) protocol**. The system monitors Reddit every 4 hours for configurable topics, processes content through a multi-stage pipeline, and delivers actionable alerts via multiple channels.

### Core Workflow

```
Reddit API → Collect → Filter → Summarize → Alert → Stakeholders
```

## Architecture Layers

### 1. Presentation Layer

**External Interfaces:**

- **REST APIs**: A2A-compliant HTTP endpoints for each agent
- **Agent Cards**: Service discovery via `/.well-known/agent.json`
- **Health Endpoints**: System monitoring and health checks
- **Admin Interface**: Configuration and monitoring dashboards

**API Standards:**

- **JSON-RPC 2.0**: A2A protocol communication
- **OpenAPI 3.0**: API specification and documentation
- **HTTP/2**: Modern protocol support with TLS
- **CORS**: Cross-origin resource sharing for web clients

### 2. Application Layer

**Agent Services:**

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ CoordinatorAgent│  │ RetrievalAgent  │  │   FilterAgent   │
│   Port 8000     │  │   Port 8001     │  │   Port 8002     │
│                 │  │                 │  │                 │
│ • Orchestration │  │ • Reddit API    │  │ • Relevance     │
│ • Workflow Mgmt │  │ • Data Collection│  │ • Semantic      │
│ • A2A Routing   │  │ • Subreddit     │  │ • Filtering     │
│ • State Mgmt    │  │   Discovery     │  │ • Scoring       │
└─────────────────┘  └─────────────────┘  └─────────────────┘

┌─────────────────┐  ┌─────────────────┐
│ SummariseAgent  │  │   AlertAgent    │
│   Port 8003     │  │   Port 8004     │
│                 │  │                 │
│ • AI Summary    │  │ • Multi-channel │
│ • Gemini API    │  │ • Slack/Email   │
│ • Content       │  │ • Delivery      │
│   Processing    │  │ • Tracking      │
└─────────────────┘  └─────────────────┘
```

**Agent Characteristics:**

- **Autonomous**: Each agent operates independently
- **Stateless**: No shared state between requests
- **Resilient**: Circuit breakers and graceful degradation
- **Observable**: Comprehensive logging and metrics

### 3. Business Logic Layer

**Core Domain Services:**

**Workflow Orchestration:**

```python
class WorkflowOrchestrator:
    async def execute_monitoring_cycle(self, topics: List[str]) -> WorkflowResult:
        # 1. Retrieve Reddit content
        posts = await self.retrieval_agent.retrieve_posts(topics)

        # 2. Filter for relevance
        relevant_posts = await self.filter_agent.filter_posts(posts, topics)

        # 3. Generate summaries
        summaries = await self.summarise_agent.summarise_posts(relevant_posts)

        # 4. Send alerts
        alerts = await self.alert_agent.send_alerts(summaries)

        return WorkflowResult(posts, relevant_posts, summaries, alerts)
```

**Content Processing Pipeline:**

- **Data Validation**: Pydantic models for type safety
- **Transformation**: Reddit data → structured format
- **Enrichment**: Metadata addition and categorization
- **Aggregation**: Content grouping and deduplication

### 4. Data Access Layer

**Data Persistence:**

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   PostgreSQL    │  │      Redis      │  │   File System   │
│                 │  │                 │  │                 │
│ • Workflow Data │  │ • Service       │  │ • Logs          │
│ • Reddit Posts  │  │   Discovery     │  │ • Metrics       │
│ • Summaries     │  │ • Session Cache │  │ • Backups       │
│ • Alert History │  │ • Rate Limiting │  │ • Temp Files    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Data Access Patterns:**

- **Repository Pattern**: Abstracted data access
- **Unit of Work**: Transaction management
- **Connection Pooling**: Efficient resource usage
- **Async ORM**: Non-blocking database operations

### 5. Infrastructure Layer

**Container Orchestration:**

```yaml
# Docker Compose Architecture
services:
  # Application Services
  coordinator-agent:    # Workflow orchestration
  retrieval-agent:      # Reddit data collection
  filter-agent:         # Content filtering
  summarise-agent:      # AI summarization
  alert-agent:          # Notification delivery

  # Infrastructure Services
  postgres:             # Primary database
  redis:                # Service discovery & cache
  prometheus:           # Metrics collection
  grafana:              # Monitoring dashboards
```

## Component Architecture

### Agent-to-Agent Communication

**A2A Protocol Implementation:**

```
┌─────────────────┐
│   HTTP Client   │
└─────────┬───────┘
          │ JSON-RPC 2.0
          ▼
┌─────────────────┐
│  FastAPI Server │
│                 │
│ • Authentication│
│ • Rate Limiting │
│ • Request       │
│   Validation    │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ A2A Agent Server│
│                 │
│ • Agent Card    │
│ • Service       │
│   Discovery     │
│ • Skill         │
│   Execution     │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│  BaseA2AAgent   │
│                 │
│ • Skill         │
│   Management    │
│ • Error         │
│   Handling      │
│ • Metrics       │
└─────────────────┘
```

### Service Discovery Mechanism

**Redis-Based Discovery:**

```python
# Agent Registration
agent_info = {
    "name": "Reddit Retrieval Agent",
    "type": "retrieval",
    "version": "1.0.0",
    "service_url": "http://localhost:8001",
    "health_endpoint": "http://localhost:8001/health",
    "last_seen": "2025-06-22T10:30:00Z"
}

# TTL-based registration
redis.hset(f"agent:{agent_type}", mapping=agent_info)
redis.expire(f"agent:{agent_type}", 300)  # 5 minutes TTL
```

### Data Flow Architecture

**End-to-End Data Flow:**

```
1. Scheduled Trigger (Cron/Timer)
         ↓
2. CoordinatorAgent.orchestrate_workflow()
         ↓
3. RetrievalAgent.retrieve_posts(topics)
         ↓ Reddit API calls
4. Raw Reddit Data (posts, comments, subreddits)
         ↓
5. FilterAgent.filter_posts(data, topics)
         ↓ Relevance scoring
6. Filtered Relevant Content
         ↓
7. SummariseAgent.summarise_posts(content)
         ↓ Gemini API calls
8. AI-Generated Summaries
         ↓
9. AlertAgent.send_alerts(summaries)
         ↓ Slack/Email APIs
10. Delivered Notifications
```

## Integration Architecture

### External API Integrations

**Reddit API Integration:**

```python
class RedditAPIClient:
    def __init__(self, client_id: str, client_secret: str):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Reddit Technical Watcher v1.0.0"
        )

    async def search_posts(self, topics: List[str]) -> List[RedditPost]:
        # Rate-limited API calls with retry logic
        # Circuit breaker pattern for resilience
        # Data transformation to internal models
```

**Gemini AI Integration:**

```python
class GeminiAPIClient:
    def __init__(self, api_key: str):
        self.client = genai.GenerativeModel('gemini-2.5-flash')

    async def generate_summary(self, content: str) -> str:
        # Prompt engineering for effective summaries
        # Token limit management
        # Fallback to alternative models
```

### Security Architecture Integration

**Authentication & Authorization:**

```
┌─────────────────┐
│   API Gateway   │  ← Optional future enhancement
└─────────┬───────┘
          │
┌─────────▼───────┐
│ Auth Middleware │
│                 │
│ • API Key Auth  │
│ • Bearer Token  │
│ • Rate Limiting │
│ • Audit Logging│
└─────────┬───────┘
          │
┌─────────▼───────┐
│  Agent Server   │
│                 │
│ • Skill Auth    │
│ • Resource      │
│   Access        │
│ • Request       │
│   Validation    │
└─────────────────┘
```

## Scalability Architecture

### Horizontal Scaling Patterns

**Agent Scaling:**

```yaml
# Docker Compose Scaling
services:
  retrieval-agent:
    scale: 3  # Multiple instances
    deploy:
      replicas: 3

  filter-agent:
    scale: 2
    deploy:
      replicas: 2
```

**Load Balancing:**

```
┌─────────────────┐
│  Load Balancer  │
│   (HAProxy)     │
└─────────┬───────┘
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
┌───────┐ ┌───────┐ ┌───────┐
│Agent1 │ │Agent2 │ │Agent3 │
│:8001  │ │:8011  │ │:8021  │
└───────┘ └───────┘ └───────┘
```

### Performance Optimization

**Caching Strategy:**

```
┌─────────────────┐
│   Application   │
│     Cache       │  ← In-memory (Redis)
└─────────┬───────┘
          │
┌─────────▼───────┐
│   Database      │
│     Cache       │  ← Query result cache
└─────────┬───────┘
          │
┌─────────▼───────┐
│   Persistent    │
│    Storage      │  ← PostgreSQL
└─────────────────┘
```

**Async Processing:**

```python
# Non-blocking I/O throughout the stack
async def process_workflow():
    # Concurrent agent communication
    tasks = [
        retrieve_posts(topics),
        get_existing_summaries(),
        check_rate_limits()
    ]

    results = await asyncio.gather(*tasks)
    return process_results(results)
```

## Monitoring and Observability Architecture

### Metrics Collection

**Prometheus Integration:**

```
Application Metrics → Prometheus → Grafana → Alerts
         ↓
  Custom Metrics:
  • Workflow execution time
  • Agent response times
  • API call success rates
  • Resource utilization
```

**Distributed Tracing:**

```python
# OpenTelemetry integration
@trace_async("workflow.execution")
async def execute_workflow(span_context):
    with tracer.start_as_current_span("retrieval.posts") as span:
        posts = await retrieval_agent.retrieve_posts()
        span.set_attribute("posts.count", len(posts))
```

### Logging Architecture

**Structured Logging:**

```python
import structlog

logger = structlog.get_logger("reddit_watcher.coordinator")

await logger.ainfo(
    "workflow.started",
    workflow_id=workflow_id,
    topics=topics,
    timestamp=datetime.utcnow().isoformat()
)
```

**Log Aggregation:**

```
Agent Logs → JSON Format → File System → Log Rotation
                ↓
        Log Aggregation Service (ELK Stack)
                ↓
        Centralized Log Analysis
```

## Deployment Architecture

### Container Strategy

**Multi-Stage Docker Builds:**

```dockerfile
# Production optimized builds
FROM python:3.12-slim as base
FROM base as dependencies
FROM dependencies as application
FROM application as production

# Non-root user security
USER reddit-watcher:reddit-watcher
```

**Service Mesh (Future):**

```
┌─────────────────┐
│   Istio/Envoy   │  ← Service mesh proxy
└─────────┬───────┘
          │
┌─────────▼───────┐
│  Agent Service  │
│                 │
│ • mTLS          │
│ • Circuit       │
│   Breaker       │
│ • Retry Logic   │
└─────────────────┘
```

## Configuration Architecture

### Environment-Based Configuration

**Configuration Hierarchy:**

```
1. Environment Variables (highest priority)
2. .env Files
3. Configuration Files
4. Default Values (lowest priority)
```

**Pydantic Configuration:**

```python
class Settings(BaseSettings):
    # Type-safe configuration with validation
    database_url: str = Field(..., description="PostgreSQL URL")
    redis_url: str = Field(..., description="Redis URL")

    # Environment-specific overrides
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__"
    )
```

## Error Handling Architecture

### Circuit Breaker Pattern

**Implementation:**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException()
```

### Graceful Degradation

**Fallback Strategies:**

- **Service Unavailable**: Return cached results
- **API Rate Limited**: Implement exponential backoff
- **Database Failure**: Use read replicas or cached data
- **External API Down**: Skip non-critical operations

## Security Architecture

### Defense in Depth

**Security Layers:**

1. **Network Security**: VPC, security groups, firewalls
2. **Application Security**: Authentication, authorization
3. **Data Security**: Encryption at rest and in transit
4. **Operational Security**: Audit logging, monitoring

**Secrets Management:**

```python
# Environment-based secrets (never in code)
DATABASE_URL=postgresql://user:pass@host:5432/db
REDDIT_CLIENT_SECRET=secret_key_here
GEMINI_API_KEY=api_key_here
```

---

*Next: [Agent Architecture](./agent-architecture.md)*
