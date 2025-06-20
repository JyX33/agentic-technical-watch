# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Reddit Technical Watcher** - an autonomous agent-based system that monitors Reddit every 4 hours for content related to configurable topics (e.g., "Claude Code"). The system collects, filters, summarizes, and alerts on relevant posts, comments, and subreddits using a modular agent architecture.

**Core Workflow:** Collect → Filter → Summarize → Alert

## Architecture

The system follows a **multi-agent architecture** orchestrated by Celery:

- **Retrieval Agent**: Fetches new posts, comments, and discovers subreddits via Reddit API (PRAW)
- **Filtering Agent**: Determines relevance using keyword matching and semantic similarity scoring
- **Summarization Agent**: Generates concise summaries using pluggable LLM providers (OpenAI, Anthropic, Gemini)
- **Alerting Agent**: Sends notifications via Slack and email
- **Orchestrator**: Coordinates the agent workflow via Celery chains

**Key Technologies:**
- Python 3.12+ with `uv` for dependency management
- Celery with Redis for task orchestration
- PostgreSQL with SQLAlchemy 2.0 and Alembic migrations
- Docker/Compose for containerization
- PRAW for Reddit API access
- LiteLLM for multi-provider LLM access

## Development Commands

### Environment Setup
```bash
# Start development stack
make dev

# Install dependencies
uv sync

# Run database migrations
make migrate
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=reddit_watcher
```

### Code Quality
```bash
# Format and lint (via pre-commit)
pre-commit run --all-files

# Run linting only
ruff check .

# Format code
ruff format .
```

### Celery Operations
```bash
# Start Celery worker
celery -A reddit_watcher.celery_app worker --loglevel=info

# Start Celery beat scheduler
celery -A reddit_watcher.celery_app beat --loglevel=info

# Monitor tasks
celery -A reddit_watcher.celery_app flower
```

## Code Organization

```
reddit_watcher/
├── agents/           # Agent implementations
│   ├── retrieval.py  # Reddit data fetching
│   ├── filtering.py  # Relevance determination
│   ├── summarise.py  # LLM-based summarization
│   └── alerting.py   # Notification delivery
├── db/
│   ├── models.py     # SQLAlchemy data models
│   └── migrations/   # Alembic migration files
├── config.py         # Pydantic settings management
├── celery_app.py     # Celery application factory
└── tasks.py          # Celery task definitions
```

## Data Models

Key database tables:
- `subreddits`: Discovered Reddit communities
- `posts`: Reddit submissions
- `comments`: Post comments
- `summaries`: Generated content summaries
- `alerts`: Sent notifications
- `cursors`: Processing checkpoints for idempotency

## Configuration

Settings are managed via Pydantic with `.env` file support:
- Database connection (`DATABASE_URL`)
- Redis connection (`REDIS_URL`) 
- Reddit API credentials (`REDDIT_*`)
- LLM provider settings (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Notification channels (`SLACK_WEBHOOK_URL`, `SMTP_*`)

## Key Design Patterns

**Idempotency**: All agents use database cursors and unique constraints to prevent duplicate processing.

**Pluggable LLMs**: Summarization agent abstracts LLM providers via LiteLLM, supporting OpenAI, Anthropic, and Google models.

**Error Handling**: Robust retry logic and fallback mechanisms throughout the pipeline.

**Observability**: Structured JSON logging with correlation IDs and Celery task context.

## Testing Strategy

- **Unit Tests**: 100% coverage for pure functions and agent logic
- **Contract Tests**: Agent input/output validation with fixtures
- **Integration Tests**: Full stack tests with temporary database
- **End-to-End Tests**: Complete 4-hour cycle simulation
- **Chaos Tests**: Failure scenarios (worker crashes, API timeouts)

## Development Workflow

1. All agents implement a standardized interface pattern
2. Database changes require Alembic migrations
3. New features should include comprehensive tests
4. Use `pre-commit` hooks for code quality
5. Follow the multi-stage development phases (A→B→C→D→E→F)

## Deployment

The system is containerized with Docker and designed for cloud deployment:
- Multi-stage Dockerfile with non-root user
- Docker Compose for local development
- Environment-based configuration
- Health checks and monitoring hooks
- Scalable worker architecture