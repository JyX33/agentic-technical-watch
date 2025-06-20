# Reddit Technical Watcher - A2A Task Board

This board tracks all tasks required for the A2A-based Reddit Technical Watcher project. Due dates assume a 9-week timeline starting June 27, 2025.

## Phase A: Infrastructure & A2A Foundation

**Target Due: End of Week 1**

- [ ] **A1**: Create repository with A2A SDK and modern uv setup
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: --
  - **Details**: Python 3.12+, a2a-sdk, pre-commit with ruff, GitHub Actions with `uv sync --locked`

- [ ] **A2**: Configure Docker multi-stage builds with uv best practices
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: A1
  - **Details**: PostgreSQL 15, Redis 7, 5 A2A agent services, UV_COMPILE_BYTECODE=1

- [ ] **A3**: Implement A2A-aware configuration module with Pydantic
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: A2
  - **Details**: Reddit API, Gemini API, A2A endpoints, database URLs, .env support

- [ ] **A4**: Create A2A agent base class with service discovery
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: A3
  - **Details**: Agent Card generation, Redis discovery, health checks, async HTTP server

## Phase B: Persistence & A2A State Management

**Target Due: End of Week 2**

- [ ] **B1**: Define SQLAlchemy models for Reddit data and A2A coordination
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-04
  - **Depends On**: A3
  - **Details**: subreddits, posts, comments, summaries, agent_tasks, agent_state tables

- [ ] **B2**: Set up Alembic with A2A task tracking schema
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-04
  - **Depends On**: B1
  - **Details**: Initial migration 0001_initial_a2a_schema, task coordination fields

- [ ] **B3**: Implement Redis-backed agent discovery system
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-04
  - **Depends On**: A4, B1
  - **Details**: Agent registry, health tracking, service discovery patterns

## Phase C: A2A Agent Implementation

**Target Due: End of Week 5**

### C1: RetrievalAgent (Week 3)

- [ ] **C1.1**: Implement RetrievalAgent with PRAW integration
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-11
  - **Depends On**: A4, B1
  - **Details**: A2A skills: fetchPosts, fetchComments, discoverSubreddits

- [ ] **C1.2**: Add OAuth 2.0 authentication and rate limiting
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-11
  - **Depends On**: C1.1
  - **Details**: 100 QPM limit, exponential backoff, user agent compliance

- [ ] **C1.3**: Implement cursor-based pagination and idempotency
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-11
  - **Depends On**: C1.2
  - **Details**: PostgreSQL content tracking, duplicate prevention

### C2: FilterAgent (Week 3)

- [ ] **C2.1**: Create FilterAgent with keyword filtering capability
  - **Priority**: Must-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-11
  - **Depends On**: A4, B1
  - **Details**: A2A skill: keywordFilter, configurable term matching

- [ ] **C2.2**: Add semantic filtering with sentence-transformers
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-11
  - **Depends On**: C2.1
  - **Details**: all-MiniLM-L6-v2 model, similarity scoring, relevance thresholds

- [ ] **C2.3**: Implement hybrid scoring algorithm
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-11
  - **Depends On**: C2.2
  - **Details**: Weighted keyword + semantic scores, configurable thresholds

### C3: SummariseAgent (Week 4)

- [ ] **C3.1**: Implement SummariseAgent with Gemini 2.5 Flash integration
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-18
  - **Depends On**: A4, B1
  - **Details**: A2A skill: summarizeContent, primary/fallback model strategy

- [ ] **C3.2**: Add rate limiting and retry logic for Gemini API
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-18
  - **Depends On**: C3.1
  - **Details**: 100 QPM limit, exponential backoff, quota management

- [ ] **C3.3**: Implement recursive chunking for long content
  - **Priority**: Should-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-18
  - **Depends On**: C3.2
  - **Details**: Token counting, content splitting, summary aggregation

- [ ] **C3.4**: Add extractive summarization fallback
  - **Priority**: Should-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-18
  - **Depends On**: C3.1
  - **Details**: spaCy-based backup, API failure handling

### C4: AlertAgent (Week 4)

- [ ] **C4.1**: Create AlertAgent with Slack webhook integration
  - **Priority**: Must-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-18
  - **Depends On**: A4, B1
  - **Details**: A2A skill: sendSlack, rich message formatting

- [ ] **C4.2**: Add SMTP email delivery capability
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-18
  - **Depends On**: C4.1
  - **Details**: A2A skill: sendEmail, HTML/text templates

- [ ] **C4.3**: Implement alert deduplication and delivery tracking
  - **Priority**: Must-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-18
  - **Depends On**: C4.1
  - **Details**: Content hash comparison, delivery status logging

### C5: CoordinatorAgent (Week 5)

- [ ] **C5.1**: Implement CoordinatorAgent workflow orchestration
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-07-25
  - **Depends On**: C1.1, C2.1, C3.1, C4.1
  - **Details**: A2A task delegation, sequential workflow management

- [ ] **C5.2**: Add comprehensive error handling and retry logic
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-07-25
  - **Depends On**: C5.1
  - **Details**: Circuit breakers, partial failure recovery, correlation IDs

- [ ] **C5.3**: Implement scheduling integration and state persistence
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-07-25
  - **Depends On**: C5.2
  - **Details**: 4-hour cycle management, workflow state tracking

### C6: A2A Idempotency and State Management

- [ ] **C6.1**: Implement A2A task ID tracking and deduplication
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-25
  - **Depends On**: B1, C5.1
  - **Details**: Unique task constraints, duplicate task prevention

- [ ] **C6.2**: Add agent state synchronization mechanisms
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-25
  - **Depends On**: C6.1
  - **Details**: Agent coordination tables, state recovery procedures

## Phase D: Integration & Workflow Testing

**Target Due: End of Week 7**

- [ ] **D1**: Create A2A integration testing framework
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-01
  - **Depends On**: All C-tasks
  - **Details**: Docker Compose test environment, agent communication validation

- [ ] **D2**: Implement end-to-end workflow testing
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-01
  - **Depends On**: D1
  - **Details**: Complete 4-hour cycle simulation, external API mocking

- [ ] **D3**: Add failure mode and chaos testing
  - **Priority**: Should-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-08
  - **Depends On**: D2
  - **Details**: Agent failure scenarios, network partitions, graceful degradation

- [ ] **D4**: Implement Reddit API rate limiting and authentication tests
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-08-08
  - **Depends On**: C1.2
  - **Details**: OAuth flow validation, rate limit compliance testing

- [ ] **D5**: Add Gemini API integration and fallback testing
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-08-08
  - **Depends On**: C3.1, C3.4
  - **Details**: Primary/fallback model switching, quota exhaustion handling

## Phase E: Monitoring & Deployment Preparation

**Target Due: End of Week 8**

- [ ] **E1**: Implement structured logging with A2A correlation IDs
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: D1
  - **Details**: JSON logging format, task traceability, correlation tracking

- [ ] **E2**: Add agent health monitoring and discovery tracking
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: E1, B3
  - **Details**: Health check endpoints, dependency monitoring, discovery failures

- [ ] **E3**: Create monitoring dashboard and alerting configuration
  - **Priority**: Should-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: E2
  - **Details**: Performance metrics, error rate monitoring, operational alerts

- [ ] **E4**: Implement SSL/TLS configuration for A2A communication
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: A2
  - **Details**: Nginx reverse proxy, certificate management, secure agent communication

- [ ] **E5**: Add production Docker hardening and security measures
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: A2
  - **Details**: Non-root containers, resource limits, secret management

## Phase F: Hostinger VPS Deployment & Finalization

**Target Due: End of Week 9**

- [ ] **F1**: Create Hostinger VPS deployment configuration
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-22
  - **Depends On**: E4, E5
  - **Details**: Docker Compose production setup, environment configuration

- [ ] **F2**: Implement backup and disaster recovery procedures
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-22
  - **Depends On**: F1
  - **Details**: PostgreSQL backups, Redis persistence, agent state recovery

- [ ] **F3**: Write comprehensive deployment and operational documentation
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-22
  - **Depends On**: F1, F2
  - **Details**: Installation guides, troubleshooting runbooks, monitoring procedures

- [ ] **F4**: Perform final quality assurance and security audit
  - **Priority**: Must-Have
  - **Owner**: Project Lead
  - **Due**: 2025-08-22
  - **Depends On**: F1, F2, F3
  - **Details**: Security review, performance validation, compliance verification

- [ ] **F5**: Execute production deployment and handoff
  - **Priority**: Must-Have
  - **Owner**: Project Lead
  - **Due**: 2025-08-22
  - **Depends On**: F4
  - **Details**: Live deployment, monitoring setup, stakeholder handoff

## Task Dependencies Summary

**Critical Path**:
A1 → A2 → A3 → A4 → B1 → B2 → C1.1 → C2.1 → C3.1 → C4.1 → C5.1 → D1 → D2 → E1 → E2 → F1 → F5

**Parallel Development Tracks**:

- Track 1: RetrievalAgent (C1.x) + Reddit API testing (D4)
- Track 2: FilterAgent (C2.x) + SummariseAgent (C3.x) + Gemini testing (D5)
- Track 3: AlertAgent (C4.x) + CoordinatorAgent (C5.x)
- Track 4: Infrastructure (E4, E5) + Deployment (F1, F2)

**Resource Allocation**:

- **@developer_A**: Infrastructure, coordination, deployment (35% of tasks)
- **@developer_B**: Data layer, retrieval, summarization (40% of tasks)
- **@developer_C**: Filtering, alerting, content processing (25% of tasks)

**Risk Mitigation**:

- Buffer time built into weeks 7-8 for integration issues
- Parallel development reduces critical path dependencies
- Early A2A foundation work reduces protocol integration risks
- Comprehensive testing strategy catches issues before deployment
