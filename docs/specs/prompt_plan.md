# Reddit Technical Watcher - A2A Implementation Steps

This document breaks down the implementation plan into granular, testable steps for building an Agent-to-Agent (A2A) protocol-based Reddit monitoring system.

*Owner assignments are placeholders and should be updated by the project lead.*

---

## Step 1: Repository Bootstrap with A2A Foundation

- **Phase Task:** A1
- **Owner:** `@developer_A`
- **Estimated Time:** 3 hours

### Context

New project using Google's A2A protocol. Need Python 3.12+ environment with modern uv dependency management.

### Requirements

1. Initialize Git repo with `uv` for Python 3.12+ project and dependency management.
2. Add A2A SDK dependency: `uv add a2a-sdk`
3. Add basic package structure (`reddit_watcher/__init__.py`, `reddit_watcher/agents/`)
4. Configure `pre-commit` with `ruff` for linting and formatting.
5. Add standard `.editorconfig`, `.gitignore`, and `pyproject.toml`.
6. Provide GitHub Actions workflow that uses `uv sync --locked` and runs `pytest`.

### Prompt for Code Generation

```
Create a modern Python 3.12+ project named "reddit-watcher" managed by `uv`. Install the a2a-sdk package and configure with `pre-commit` using `ruff`. Include a GitHub Actions workflow that uses `uv sync --locked` and runs `pytest`. Add one empty test file `tests/test_smoke.py` that asserts `True is True`. Use pyproject.toml for all configuration.
```

---

## Step 2: Docker Multi-Stage Build with uv

- **Phase Task:** A2
- **Owner:** `@developer_A`
- **Estimated Time:** 3 hours

### Context

Modern Docker setup using uv best practices for Python 3.12+ with multi-stage builds.

### Requirements

1. `docker-compose.yml` with services: db (postgres:15), redis (redis:7), and 5 A2A agent services.
2. Multi-stage `Dockerfile` using `ghcr.io/astral-sh/uv:latest` with proper layer caching.
3. Set `UV_COMPILE_BYTECODE=1` and `UV_LINK_MODE=copy` for containers.
4. `Makefile` target `make dev` to spin up the stack.
5. Separate dependency installation from project installation for optimal caching.

### Prompt for Code Generation

```
Create a multi-stage Dockerfile using uv best practices for Python 3.12+. Copy from ghcr.io/astral-sh/uv:latest, set UV_COMPILE_BYTECODE=1 and UV_LINK_MODE=copy. Use --no-install-project for dependency caching. Add docker-compose.yml with PostgreSQL 15, Redis 7, and placeholder services for 5 A2A agents. Include a Makefile with 'dev' target.
```

---

## Step 3: Configuration Module with A2A Settings

- **Phase Task:** A3
- **Owner:** `@developer_A`
- **Estimated Time:** 2 hours

### Context

Unified settings for A2A agents, databases, and external APIs.

### Requirements

1. Create `reddit_watcher/config.py` using Pydantic `BaseSettings`.
2. Include settings for A2A agent URLs, Reddit API, Gemini API, databases.
3. Support `.env` file overrides for all configurations.
4. Implement as singleton pattern for consistent access.

### Prompt for Code Generation

```
Implement a Pydantic BaseSettings class for A2A agent configuration. Include settings for Reddit API (client_id, client_secret, user_agent), Gemini API key, PostgreSQL URL, Redis URL, and A2A agent endpoints. Provide comprehensive unit tests with temporary .env files.
```

---

## Step 4: A2A Agent Base Class and Discovery

- **Phase Task:** A4
- **Owner:** `@developer_A`
- **Estimated Time:** 4 hours

### Context

Foundation for all A2A agents with standardized Agent Card implementation.

### Requirements

1. Create `reddit_watcher/agents/base.py` with A2A agent base class.
2. Implement Agent Card generation and HTTP server setup.
3. Add agent discovery mechanism using Redis for service registry.
4. Include health check endpoints and graceful shutdown.

### Prompt for Code Generation

```
Create a base A2A agent class using the a2a-sdk. Implement Agent Card generation, HTTP server setup with proper async handling, and Redis-backed service discovery. Include health checks, graceful shutdown, and standardized error handling. Provide comprehensive tests.
```

---

## Step 5: SQLAlchemy Models for A2A State Management

- **Phase Task:** B1
- **Owner:** `@developer_B`
- **Estimated Time:** 4 hours

### Context

Database models supporting A2A agent state and coordination.

### Requirements

1. Create `reddit_watcher/db/models.py` with SQLAlchemy 2.0 DeclarativeBase.
2. Define tables: `subreddits`, `posts`, `comments`, `summaries`, `alerts`, `agent_tasks`, `agent_state`.
3. Add A2A task tracking and agent coordination fields.
4. Include comprehensive relationship mappings and constraints.

### Prompt for Code Generation

```
Implement SQLAlchemy 2.0 models for Reddit data (subreddits, posts, comments) and A2A coordination (agent_tasks, agent_state). Include proper relationships, constraints, and indexes. Add unit tests using pytest-postgresql for database operations.
```

---

## Step 6: Alembic Migration Pipeline

- **Phase Task:** B2
- **Owner:** `@developer_B`
- **Estimated Time:** 2 hours

### Context

Database schema management for A2A agent system.

### Requirements

1. Configure `alembic.ini` and `alembic/env.py` targeting the models.
2. Generate initial migration `0001_initial_a2a_schema`.
3. Add `make migrate` helper to `Makefile`.
4. Include CI step for migration validation.

### Prompt for Code Generation

```
Set up Alembic for SQLAlchemy 2.0 models with proper async support. Generate initial migration including all tables. Add Makefile targets for migration management and CI validation step.
```

---

## Step 7: RetrievalAgent - Reddit Data Fetching

- **Phase Task:** C1
- **Owner:** `@developer_B`
- **Estimated Time:** 6 hours

### Context

A2A agent for Reddit data retrieval using PRAW with OAuth 2.0.

### Requirements

1. Implement `RetrievalAgent` in `reddit_watcher/agents/retrieval.py`.
2. A2A skills: `fetchPosts`, `fetchComments`, `discoverSubreddits`.
3. PRAW integration with proper rate limiting (100 QPM).
4. Agent Card advertising capabilities and authentication requirements.
5. Cursor-based pagination and idempotency.

### Prompt for Code Generation

```
Create RetrievalAgent as A2A service with three skills: fetchPosts (search Reddit posts), fetchComments (get post comments), discoverSubreddits (find new subreddits). Use PRAW with OAuth 2.0, respect rate limits, implement cursor-based pagination. Include comprehensive tests with mocked PRAW.
```

---

## Step 8: FilterAgent - Content Relevance Assessment

- **Phase Task:** C2
- **Owner:** `@developer_C`
- **Estimated Time:** 5 hours

### Context

A2A agent for determining content relevance using keyword and semantic filtering.

### Requirements

1. Implement `FilterAgent` with skills: `keywordFilter`, `semanticFilter`.
2. Keyword-based filtering with configurable term matching.
3. Semantic similarity using sentence-transformers (all-MiniLM-L6-v2).
4. Configurable relevance thresholds and scoring.
5. A2A communication for receiving content lists and returning filtered results.

### Prompt for Code Generation

```
Create FilterAgent with keyword and semantic filtering capabilities. Use sentence-transformers for semantic similarity scoring. Implement configurable thresholds and return relevance scores. Include dependency injection for embedding models and comprehensive test coverage.
```

---

## Step 9: SummariseAgent - AI Content Summarization

- **Phase Task:** C3
- **Owner:** `@developer_B`
- **Estimated Time:** 8 hours

### Context

A2A agent using Gemini 2.5 Flash for content summarization.

### Requirements

1. Implement `SummariseAgent` with skill: `summarizeContent`.
2. Primary: Gemini 2.5 Flash-Lite, Fallback: Gemini 2.5 Flash.
3. Handle rate limiting (100 QPM) and implement retry logic.
4. Recursive chunking for content exceeding token limits.
5. Simple extractive fallback for API failures.

### Prompt for Code Generation

```
Create SummariseAgent using Gemini 2.5 Flash models via Google AI SDK. Implement primary/fallback strategy, rate limiting, and recursive summarization. Include simple extractive backup using spaCy. Add comprehensive testing with mocked API responses.
```

---

## Step 10: AlertAgent - Multi-Channel Notifications

- **Phase Task:** C4
- **Owner:** `@developer_C`
- **Estimated Time:** 4 hours

### Context

A2A agent for delivering notifications via Slack and email.

### Requirements

1. Implement `AlertAgent` with skills: `sendSlack`, `sendEmail`.
2. Slack webhook integration with rich message formatting.
3. SMTP email delivery with HTML/text templates.
4. Alert deduplication and delivery tracking.
5. Configurable channel routing and formatting.

### Prompt for Code Generation

```
Create AlertAgent with Slack webhook and SMTP email capabilities. Include rich message formatting, template system, and delivery tracking. Implement deduplication and configurable routing. Test with responses library for webhook mocking.
```

**Status: COMPLETED** ✅ - Implemented AlertAgent with full Slack webhook and SMTP email capabilities, including rich message formatting, HTML/text templates, deduplication, and comprehensive test coverage.

---

## Step 11: CoordinatorAgent - Workflow Orchestration

- **Phase Task:** C5
- **Owner:** `@developer_A`
- **Estimated Time:** 6 hours

### Context

Master A2A agent orchestrating the 4-hour monitoring cycle.

### Requirements

1. Implement `CoordinatorAgent` for workflow management.
2. A2A task delegation to other agents in sequence.
3. Error handling, retries, and partial failure recovery.
4. Scheduling integration and state persistence.
5. Comprehensive workflow logging and monitoring.

### Prompt for Code Generation

```
Create CoordinatorAgent that orchestrates the complete workflow via A2A task delegation. Implement robust error handling, retry logic, and partial failure recovery. Include scheduling integration and comprehensive audit logging of agent interactions.
```

---

## Step 12: A2A Idempotency and State Management

- **Phase Task:** C6
- **Owner:** `@developer_B`
- **Estimated Time:** 4 hours

### Context

Ensure consistent agent state and prevent duplicate processing.

### Requirements

1. Implement A2A task ID tracking and deduplication.
2. Database constraints for unique content processing.
3. Agent state synchronization mechanisms.
4. Recovery procedures for incomplete tasks.

### Prompt for Code Generation

```
Add A2A task ID tracking, database constraints for idempotency, and agent state synchronization. Implement recovery procedures for interrupted tasks. Include Alembic migration and comprehensive testing.
```

**Status: COMPLETED** ✅ - Implemented comprehensive A2A idempotency and state management system with task deduplication, agent coordination, recovery procedures, Alembic migration, and extensive test coverage. Added new models (AgentState, TaskRecovery, ContentDeduplication) with unique constraints, distributed locking, and recovery strategies.

---

## Step 13: Integration Testing Framework

- **Phase Task:** D1
- **Owner:** `@developer_A`
- **Estimated Time:** 5 hours

### Context

End-to-end testing of A2A agent communication and workflows.

### Requirements

1. Docker Compose test environment with all agents.
2. A2A communication testing and validation.
3. Mock external APIs (Reddit, Gemini) for isolated testing.
4. Complete workflow simulation and verification.

### Prompt for Code Generation

```
Create integration testing framework using Docker Compose. Test A2A agent discovery, communication, and complete workflow execution. Mock external APIs and validate end-to-end functionality. Include test data fixtures and assertion helpers.
```

**Status: COMPLETED** ✅ - Implemented comprehensive integration testing framework with Docker Compose test environment, A2A communication testing, mock APIs (Reddit, Gemini, Slack), complete workflow simulation, test data fixtures, assertion helpers, and integration test runner with Makefile targets.

---

## Step 14: Failure Mode and Chaos Testing

- **Phase Task:** D2
- **Owner:** `@developer_A`
- **Estimated Time:** 4 hours

### Context (Step 14)

Test agent resilience and communication failure scenarios.

### Requirements (Step 14)

1. Agent failure simulation and recovery testing.
2. Network partition and timeout scenarios.
3. API rate limiting and error response handling.
4. Graceful degradation validation.

### Prompt for Code Generation (Step 14)

```bash
Implement chaos testing for A2A agent failures, network issues, and API errors. Test agent recovery, timeout handling, and graceful degradation. Include automated failure injection and recovery verification.
```

---

## Step 15: Monitoring and Observability

- **Phase Task:** E1
- **Owner:** `@developer_A`
- **Estimated Time:** 4 hours

### Context (Step 15)

Production-ready monitoring for A2A agent system.

### Requirements (Step 15)

1. Structured logging with A2A task correlation IDs.
2. Agent health monitoring and discovery tracking.
3. Performance metrics and error rate monitoring.
4. Dashboard configuration for operational insight.

### Prompt for Code Generation (Step 15)

```bash
Implement structured logging with A2A task correlation, agent health monitoring, and performance metrics. Create monitoring dashboard configuration and alerting rules for production deployment.
```

---

## Step 16: Hostinger VPS Deployment

- **Phase Task:** F1
- **Owner:** `@developer_A`
- **Estimated Time:** 5 hours

### Context (Step 16)

Production deployment on Hostinger VPS with security hardening.

### Requirements (Step 16)

1. VPS configuration and Docker deployment.
2. Security hardening and network configuration.
3. SSL/TLS setup for A2A agent communication.
4. Backup and monitoring configuration.
5. Deployment documentation and runbooks.

### Prompt for Code Generation (Step 16)

```bash
Create Hostinger VPS deployment configuration with Docker Compose, SSL/TLS for A2A communication, security hardening, and backup procedures. Include deployment scripts and operational runbooks.
```
