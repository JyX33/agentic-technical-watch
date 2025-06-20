# Project Task Board

This board tracks all tasks required for the Reddit Technical Watcher project. Due dates are indicative and should be confirmed during sprint planning.

## Phase A: Infrastructure

**Target Due: End of Week 1**

- [ ] **A1**: Create the initial project repository structure with uv and configure CI/CD basics.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: --

- [ ] **A2**: Configure the Docker-compose environment for local development (Postgres, Redis, Mailhog).
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: A1

- [ ] **A3**: Implement the Pydantic-based configuration module for managing settings and secrets.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: A2

- [ ] **A4**: Create the core Celery application factory and define the periodic Beat schedule.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-06-27
  - **Depends On**: A3

## Phase B: Persistence

**Target Due: End of Week 2**

- [ ] **B1**: Define the SQLAlchemy 2.0 data models for all required database tables.
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-04
  - **Depends On**: A3

- [ ] **B2**: Set up the Alembic migration pipeline and generate the initial database schema migration.
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-04
  - **Depends On**: B1

## Phase C: Agents

**Target Due: End of Week 5**

- [ ] **C1**: Implement the Retrieval Agent to fetch new posts from Reddit.
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-11
  - **Depends On**: A4, B1

- [ ] **C2**: Extend the Retrieval Agent to fetch comments for retrieved posts.
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-11
  - **Depends On**: C1

- [ ] **C3**: Extend the Retrieval Agent to discover new, relevant subreddits.
  - **Priority**: Should-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-11
  - **Depends On**: C1

- [ ] **C4**: Implement the initial keyword-based Filtering Agent to determine content relevance.
  - **Priority**: Must-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-18
  - **Depends On**: C1, C2

- [ ] **C5**: Enhance the Filtering Agent with semantic similarity scoring for higher precision.
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-18
  - **Depends On**: C4

- [ ] **C6**: Implement the core pluggable Summarisation Agent.
  - **Priority**: Must-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-25
  - **Depends On**: C4

- [ ] **C6.1**: Research and select the primary summarization model (OpenAI vs. Anthropic vs. Gemini).
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-25
  - **Depends On**: C6

- [ ] **C6.2**: Implement a simple fallback extractive summarizer for cost/outage mitigation.
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-25
  - **Depends On**: C6

- [ ] **C7**: Implement the Alerting Agent to send notifications to Slack.
  - **Priority**: Must-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-25
  - **Depends On**: C6

- [ ] **C8**: Implement fallback Alerting Agent to send notifications via email (SMTP).
  - **Priority**: Should-Have
  - **Owner**: @developer_C
  - **Due**: 2025-07-25
  - **Depends On**: C6

- [ ] **C9**: Implement idempotency guards using database constraints and persistent cursors.
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-07-25
  - **Depends On**: B1, C1

## Phase D: Workflow & Integration

**Target Due: End of Week 7**

- [ ] **D1**: Compose the end-to-end Celery workflow chain connecting all agents.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-01
  - **Depends On**: All C-tasks

- [ ] **D2**: Create and pass an end-to-end "happy path" integration test.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-01
  - **Depends On**: D1

- [ ] **D3**: Create and pass failure-mode integration tests (e.g., API errors, timeouts).
  - **Priority**: Should-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-08
  - **Depends On**: D2

- [ ] **D4**: Implement and test a central rate-limiter for the Reddit API client.
  - **Priority**: Must-Have
  - **Owner**: @developer_B
  - **Due**: 2025-08-08
  - **Depends On**: C1

- [ ] **D5**: Create and test a chaos scenario (e.g., kill a Celery worker mid-run).
  - **Priority**: Should-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-08
  - **Depends On**: D1

## Phase E: Observability & Ops

**Target Due: End of Week 8**

- [ ] **E1**: Configure structured JSON logging (structlog) with correlation IDs.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: A3, D1

- [ ] **E2**: Implement Prometheus metrics for key application events (counters, histograms).
  - **Priority**: Should-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: E1

- [ ] **E3**: Create a sample Grafana dashboard JSON file for key metrics.
  - **Priority**: Could-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: E2

- [ ] **E4**: Create Alertmanager rules for critical failures (e.g., high task error rate).
  - **Priority**: Could-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: E2

- [ ] **E5**: Configure and test Celery worker autoscaling strategy for handling data spikes.
  - **Priority**: Could-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-15
  - **Depends On**: D1, E2

## Phase F: Finalization

**Target Due: End of Week 9**

- [ ] **F1**: Harden the production Dockerfile (slim image, non-root user, security scan).
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-22
  - **Depends On**: All build artifacts

- [ ] **F2**: Write comprehensive README.md and user documentation.
  - **Priority**: Must-Have
  - **Owner**: @developer_A
  - **Due**: 2025-08-22
  - **Depends On**: All other tasks

- [ ] **F3**: Perform final Quality Assurance checks and prepare for project hand-off.
  - **Priority**: Must-Have
  - **Owner**: Project Lead
  - **Due**: 2025-08-22
  - **Depends On**: F1, F2
