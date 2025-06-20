# Reddit Technical Watcher - A2A Technical Specification

## 1. System Overview

The Reddit Technical Watcher is a multi-agent system built on Google's A2A (Agent-to-Agent) protocol v0.2.3. It autonomously monitors Reddit every 4 hours for content related to configurable topics (e.g., "Claude Code"), processes this content through a specialized agent pipeline, and delivers intelligent alerts.

### 1.1 Architecture Principles

- **Agent Autonomy**: Each agent operates independently with clearly defined responsibilities
- **A2A Communication**: Standardized HTTP/JSON-RPC communication between agents
- **Fault Tolerance**: Graceful degradation and recovery from agent failures
- **Observability**: Comprehensive logging and monitoring of agent interactions
- **Extensibility**: New agents can be added without modifying existing ones

### 1.2 Core Workflow

```
CoordinatorAgent (4-hour timer)
    ↓ A2A Task: fetchPosts("Claude Code")
RetrievalAgent (Reddit API via PRAW)
    ↓ A2A Task: keywordFilter(posts[])
FilterAgent (Keyword + Semantic filtering)
    ↓ A2A Task: summarizeContent(relevant_posts[])
SummariseAgent (Gemini 2.5 Flash)
    ↓ A2A Task: sendSlack(summaries[])
AlertAgent (Slack/Email delivery)
```

## 2. Agent Specifications

### 2.1 CoordinatorAgent

**Purpose**: Orchestrates the complete monitoring workflow via A2A task delegation.

**Agent Card**:

```json
{
  "name": "CoordinatorAgent",
  "description": "Orchestrates Reddit monitoring workflow",
  "endpoint": "http://coordinator:8000",
  "capabilities": [
    {
      "name": "orchestrateWorkflow",
      "description": "Execute complete 4-hour monitoring cycle",
      "parameters": {
        "topic": "string",
        "cycle_id": "string"
      }
    }
  ],
  "authentication": {
    "type": "bearer",
    "required": true
  }
}
```

**Key Responsibilities**:

- Schedule and initiate 4-hour monitoring cycles
- Delegate tasks to specialized agents via A2A protocol
- Handle partial failures and implement retry logic
- Maintain audit trail of all agent interactions
- Coordinate agent discovery and health monitoring

**Error Handling**:

- Circuit breaker pattern for failed agents
- Fallback strategies for critical path failures
- Comprehensive error logging with correlation IDs

### 2.2 RetrievalAgent

**Purpose**: Fetch new content from Reddit API using PRAW with OAuth 2.0.

**Agent Card**:

```json
{
  "name": "RetrievalAgent",
  "description": "Reddit content retrieval via PRAW",
  "endpoint": "http://retrieval:8001",
  "capabilities": [
    {
      "name": "fetchPosts",
      "description": "Search Reddit posts by topic",
      "parameters": {
        "topic": "string",
        "limit": "integer",
        "timeframe": "string",
        "cursor": "string"
      }
    },
    {
      "name": "fetchComments",
      "description": "Retrieve comments for specific posts",
      "parameters": {
        "post_ids": "array",
        "max_depth": "integer"
      }
    },
    {
      "name": "discoverSubreddits",
      "description": "Find new subreddits related to topic",
      "parameters": {
        "topic": "string",
        "min_subscribers": "integer"
      }
    }
  ]
}
```

**Technical Implementation**:

- PRAW 7.x with OAuth 2.0 authentication
- Rate limiting: 100 QPM with exponential backoff
- Cursor-based pagination for large result sets
- User agent: "reddit-watcher/1.0 (by /u/username)"
- Idempotency via content ID tracking in PostgreSQL

**Data Processing**:

- Extract: post ID, title, content, author, subreddit, timestamp, score
- Store in PostgreSQL with unique constraints
- Return paginated results as A2A artifacts

### 2.3 FilterAgent

**Purpose**: Determine content relevance using keyword matching and semantic similarity.

**Agent Card**:

```json
{
  "name": "FilterAgent",
  "description": "Content relevance filtering",
  "endpoint": "http://filter:8002",
  "capabilities": [
    {
      "name": "keywordFilter",
      "description": "Filter content by keyword matching",
      "parameters": {
        "content_items": "array",
        "keywords": "array",
        "match_threshold": "float"
      }
    },
    {
      "name": "semanticFilter",
      "description": "Filter using semantic similarity",
      "parameters": {
        "content_items": "array",
        "topic_description": "string",
        "similarity_threshold": "float"
      }
    }
  ]
}
```

**Technical Implementation**:

- **Keyword Filtering**: Case-insensitive matching with configurable term lists
- **Semantic Filtering**: sentence-transformers (all-MiniLM-L6-v2) for embeddings
- **Scoring Algorithm**: Weighted combination of keyword + semantic scores
- **Thresholds**: Configurable relevance thresholds (default: 0.7)
- **Performance**: Batch processing with embedding caching

**Filtering Logic**:

```python
def calculate_relevance_score(content, topic):
    keyword_score = keyword_match_score(content, TOPIC_KEYWORDS)
    semantic_score = cosine_similarity(
        embed_text(content),
        embed_text(TOPIC_DESCRIPTION)
    )
    return 0.4 * keyword_score + 0.6 * semantic_score
```

### 2.4 SummariseAgent

**Purpose**: Generate intelligent summaries using Gemini 2.5 Flash models.

**Agent Card**:

```json
{
  "name": "SummariseAgent",
  "description": "AI-powered content summarization",
  "endpoint": "http://summarise:8003",
  "capabilities": [
    {
      "name": "summarizeContent",
      "description": "Generate concise summaries of content",
      "parameters": {
        "content_items": "array",
        "max_length": "integer",
        "style": "string"
      }
    }
  ]
}
```

**Technical Implementation**:

- **Primary Model**: gemini-2.5-flash-lite-preview (lowest latency/cost)
- **Fallback Model**: gemini-2.5-flash (higher quality)
- **Rate Limiting**: 100 QPM with intelligent queuing
- **Context Management**: Recursive chunking for long content
- **Backup Strategy**: Simple extractive summarization using spaCy

**Summarization Pipeline**:

1. Content preprocessing and token counting
2. Chunking if content exceeds model limits
3. Primary model API call with retry logic
4. Fallback to secondary model on failure
5. Final fallback to extractive summarization
6. Quality validation and formatting

**Prompt Engineering**:

```
Summarize this Reddit discussion about [TOPIC] in 2-3 sentences.
Focus on: key insights, questions raised, community sentiment.
Content: [CONTENT]
```

### 2.5 AlertAgent

**Purpose**: Deliver formatted notifications via multiple channels.

**Agent Card**:

```json
{
  "name": "AlertAgent",
  "description": "Multi-channel notification delivery",
  "endpoint": "http://alert:8004",
  "capabilities": [
    {
      "name": "sendSlack",
      "description": "Send formatted Slack notification",
      "parameters": {
        "summaries": "array",
        "channel": "string",
        "priority": "string"
      }
    },
    {
      "name": "sendEmail",
      "description": "Send HTML email notification",
      "parameters": {
        "summaries": "array",
        "recipients": "array",
        "subject": "string"
      }
    }
  ]
}
```

**Technical Implementation**:

- **Slack Integration**: Webhook API with rich message formatting
- **Email Integration**: SMTP with HTML/text templates
- **Deduplication**: Content hash-based duplicate detection
- **Formatting**: Adaptive formatting based on content volume
- **Delivery Tracking**: Success/failure logging with retry logic

**Message Templates**:

- **Single Item**: Title, summary, metadata, direct link
- **Multiple Items**: Grouped by subreddit with aggregate statistics
- **No Content**: Optional heartbeat message indicating system health

## 3. A2A Communication Patterns

### 3.1 Task Delegation Flow

```
CoordinatorAgent creates task:
{
  "id": "task_001_fetch",
  "type": "fetchPosts",
  "parameters": {"topic": "Claude Code", "limit": 50},
  "context_id": "cycle_2025_001",
  "created_at": "2025-06-20T10:00:00Z"
}

RetrievalAgent processes and responds:
{
  "task_id": "task_001_fetch",
  "status": "completed",
  "result": {
    "posts": [...],
    "next_cursor": "abc123",
    "total_found": 47
  },
  "completed_at": "2025-06-20T10:02:30Z"
}
```

### 3.2 Error Handling Patterns

**Agent Unavailable**:

```json
{
  "task_id": "task_002_filter",
  "status": "failed",
  "error": {
    "code": "AGENT_UNAVAILABLE",
    "message": "FilterAgent not responding",
    "retry_after": 300
  }
}
```

**Partial Success**:

```json
{
  "task_id": "task_003_summarize",
  "status": "partial_success",
  "result": {
    "successful_summaries": 15,
    "failed_summaries": 2,
    "summaries": [...],
    "errors": [...]
  }
}
```

### 3.3 Agent Discovery

Agents register with Redis-backed service discovery:

```python
# Agent registration
redis_client.hset(
    "agent:registry",
    "RetrievalAgent",
    json.dumps({
        "endpoint": "http://retrieval:8001",
        "health_check": "/health",
        "last_seen": "2025-06-20T10:00:00Z",
        "capabilities": [...]
    })
)

# Agent discovery
available_agents = redis_client.hgetall("agent:registry")
```

## 4. Data Models and Storage

### 4.1 PostgreSQL Schema

**Core Tables**:

```sql
-- Reddit content storage
CREATE TABLE subreddits (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    subscribers INTEGER,
    discovered_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE posts (
    id VARCHAR(20) PRIMARY KEY, -- Reddit post ID
    subreddit_id UUID REFERENCES subreddits(id),
    title TEXT NOT NULL,
    content TEXT,
    author VARCHAR(100),
    score INTEGER,
    created_utc TIMESTAMP WITH TIME ZONE,
    url TEXT,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- A2A coordination
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    parameters JSONB,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    context_id VARCHAR(100)
);

CREATE TABLE summaries (
    id UUID PRIMARY KEY,
    content_id VARCHAR(20) REFERENCES posts(id),
    summary_text TEXT NOT NULL,
    model_used VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(content_id) -- Prevent duplicate summaries
);
```

### 4.2 Redis Schema

**Agent Discovery**:

```
agent:registry -> Hash of agent_name -> agent_metadata
agent:health -> Hash of agent_name -> last_heartbeat
```

**Task Coordination**:

```
task:queue:{agent_name} -> List of pending task IDs
task:status:{task_id} -> Task status and metadata
task:results:{task_id} -> Task results and artifacts
```

## 5. External Integrations

### 5.1 Reddit API Integration

**Authentication**:

```python
reddit = praw.Reddit(
    client_id=settings.REDDIT_CLIENT_ID,
    client_secret=settings.REDDIT_CLIENT_SECRET,
    user_agent=settings.REDDIT_USER_AGENT,
    username=settings.REDDIT_USERNAME,
    password=settings.REDDIT_PASSWORD
)
```

**Rate Limiting**:

- Built-in PRAW rate limiting (100 QPM)
- Custom exponential backoff for 429 responses
- Request queuing during rate limit periods

**Search Strategy**:

```python
# Multi-faceted search approach
def search_reddit_content(topic, timeframe="day"):
    # 1. Global search across all subreddits
    global_posts = reddit.subreddit("all").search(
        topic, time_filter=timeframe, limit=25
    )

    # 2. Targeted subreddit monitoring
    targeted_posts = []
    for sub in MONITORED_SUBREDDITS:
        targeted_posts.extend(
            reddit.subreddit(sub).new(limit=10)
        )

    # 3. Subreddit discovery
    discovered_subs = reddit.subreddits.search(topic, limit=5)

    return combine_and_deduplicate(global_posts, targeted_posts)
```

### 5.2 Gemini API Integration

**Model Configuration**:

```python
import google.generativeai as genai

# Primary model (fast, cost-effective)
PRIMARY_MODEL = "gemini-2.5-flash-lite-preview"
FALLBACK_MODEL = "gemini-2.5-flash"

genai.configure(api_key=settings.GEMINI_API_KEY)

primary_model = genai.GenerativeModel(PRIMARY_MODEL)
fallback_model = genai.GenerativeModel(FALLBACK_MODEL)
```

**Rate Limiting & Retry Logic**:

```python
@retry(
    retry=retry_if_exception_type(genai.types.ApiException),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(3)
)
async def generate_summary(content: str) -> str:
    try:
        response = await primary_model.generate_content_async(
            f"Summarize this Reddit discussion: {content}"
        )
        return response.text
    except genai.types.ApiException as e:
        if "quota" in str(e).lower():
            # Switch to fallback model
            response = await fallback_model.generate_content_async(content)
            return response.text
        raise
```

## 6. Deployment Architecture

### 6.1 Hostinger VPS Configuration

**Server Specifications**:

- VPS KVM 2: 2 vCPU, 4GB RAM, 80GB SSD
- Ubuntu 22.04 LTS with Docker pre-installed
- Static IP with SSL/TLS certificates for A2A communication

**Docker Compose Stack**:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: reddit_watcher
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  coordinator:
    build: .
    command: python -m reddit_watcher.agents.coordinator
    environment:
      - AGENT_TYPE=coordinator
      - A2A_PORT=8000
    depends_on: [postgres, redis]

  retrieval:
    build: .
    command: python -m reddit_watcher.agents.retrieval
    environment:
      - AGENT_TYPE=retrieval
      - A2A_PORT=8001
    depends_on: [postgres, redis]

  # ... other agents

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
```

### 6.2 Security Configuration

**SSL/TLS for A2A Communication**:

```nginx
upstream coordinator_backend {
    server coordinator:8000;
}

server {
    listen 443 ssl;
    server_name coordinator.reddit-watcher.local;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/certs/key.pem;

    location / {
        proxy_pass http://coordinator_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Agent Authentication**:

```python
# Each agent validates incoming A2A requests
def validate_a2a_request(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError("Missing or invalid authorization")

    token = auth_header[7:]  # Remove "Bearer "
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload["agent_id"]
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid JWT token")
```

## 7. Monitoring and Observability

### 7.1 Structured Logging

**Log Format**:

```json
{
  "timestamp": "2025-06-20T10:00:00Z",
  "level": "INFO",
  "agent": "RetrievalAgent",
  "task_id": "task_001_fetch",
  "context_id": "cycle_2025_001",
  "message": "Successfully fetched 47 posts",
  "metadata": {
    "execution_time_ms": 2300,
    "api_calls": 3,
    "rate_limit_remaining": 97
  }
}
```

**Correlation Tracking**:

- Each monitoring cycle gets unique `context_id`
- A2A tasks inherit `context_id` for traceability
- Agent interactions logged with full task chain

### 7.2 Health Monitoring

**Agent Health Checks**:

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent": "RetrievalAgent",
        "version": "1.0.0",
        "last_task": "2025-06-20T09:58:00Z",
        "dependencies": {
            "reddit_api": await check_reddit_connection(),
            "database": await check_db_connection(),
            "redis": await check_redis_connection()
        }
    }
```

**Alerting Rules**:

- Agent down for >5 minutes
- Task failure rate >5% in 1 hour
- API rate limit exhaustion
- Database connection failures

### 7.3 Performance Metrics

**Key Performance Indicators**:

- End-to-end cycle time (target: <10 minutes)
- Agent response times (target: <2 seconds)
- Task success rate (target: >99%)
- Content processing throughput
- Resource utilization (CPU, memory, network)

## 8. Operational Procedures

### 8.1 Deployment Process

1. **Pre-deployment**: Run full test suite, build Docker images
2. **Deployment**: Rolling update of agent services
3. **Validation**: Health checks and smoke tests
4. **Monitoring**: Watch metrics for anomalies
5. **Rollback**: Automated rollback on failure detection

### 8.2 Troubleshooting Guide

**Common Issues**:

- **Agent Discovery Failures**: Check Redis connectivity and agent registration
- **Reddit API Errors**: Verify OAuth credentials and rate limit status
- **Gemini API Failures**: Check API key validity and quota usage
- **Task Timeouts**: Review agent performance and resource constraints

**Diagnostic Commands**:

```bash
# Check agent health
curl -s https://coordinator.reddit-watcher.local/health | jq

# View recent tasks
docker exec postgres psql -U reddit_watcher -c "
  SELECT task_type, status, created_at
  FROM agent_tasks
  ORDER BY created_at DESC
  LIMIT 10;"

# Monitor agent logs
docker logs --tail 100 -f reddit-watcher_coordinator_1
```

This technical specification provides the comprehensive foundation for implementing the A2A-based Reddit Technical Watcher system with clear agent responsibilities, communication patterns, and operational procedures.
