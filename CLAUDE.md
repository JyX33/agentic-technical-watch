# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Reddit Technical Watcher** - an autonomous agent-based system that monitors Reddit every 4 hours for content related to configurable topics (e.g., "Claude Code"). The system collects, filters, summarizes, and alerts on relevant posts, comments, and subreddits using Google's **A2A (Agent-to-Agent) protocol**.

**Core Workflow:** Collect → Filter → Summarize → Alert

## Architecture

The system follows **Google's A2A (Agent-to-Agent) protocol** for multi-agent communication:

- **RetrievalAgent**: Fetches new posts, comments, and discovers subreddits via Reddit API (PRAW)
- **FilterAgent**: Determines relevance using keyword matching and semantic similarity scoring
- **SummariseAgent**: Generates concise summaries using Gemini 2.5 Flash
- **AlertAgent**: Sends notifications via Slack and email
- **CoordinatorAgent**: Orchestrates the agent workflow via A2A protocol

**Key Technologies:**

- Python 3.12+ with `uv` for dependency management
- **Google A2A SDK** for agent-to-agent communication
- **FastAPI** servers for each agent with A2A protocol support
- **Redis** for A2A service discovery and state management
- PostgreSQL with SQLAlchemy 2.0 and Alembic migrations (planned)
- Docker/Compose for containerization
- PRAW for Reddit API access
- Gemini 2.5 Flash for AI summarization

## Development Commands

### Environment Setup

```bash
# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Start development services (Redis, PostgreSQL)
docker-compose up -d redis postgres
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_a2a_base.py

# Run with coverage
uv run pytest --cov=reddit_watcher

# Test A2A agent functionality
uv run python tests/cli/test_agent_cli.py
```

### Code Quality

```bash
# Format and lint (via pre-commit)
uv run pre-commit run --all-files

# Run linting only
uv run ruff check .

# Format code
uv run ruff format .
```

### A2A Agent Operations

```bash
# Run test agent server
uv run python -m reddit_watcher.agents.test_agent

# Test agent endpoints
curl http://localhost:8000/.well-known/agent.json
curl http://localhost:8000/health
curl http://localhost:8000/discover
```

## Code Organization

```
reddit_watcher/
├── agents/                # A2A Agent implementations
│   ├── base.py           # BaseA2AAgent abstract class & AgentExecutor
│   ├── server.py         # A2A HTTP server & service discovery
│   ├── test_agent.py     # Test agent for validation
│   └── __init__.py
├── config.py             # Pydantic settings with A2A configuration
└── __init__.py
tests/
├── test_a2a_base.py      # A2A agent functionality tests
├── test_config.py        # Configuration validation tests
docs/
├── specs/                # Project specifications
│   └── prompt_plan.md    # 16-step implementation plan
Dockerfile                # Multi-stage Docker build with uv
docker-compose.yml        # Development services (Redis, PostgreSQL)
pyproject.toml           # uv project configuration
tests/cli/test_agent_cli.py        # Manual A2A agent testing CLI
```

## A2A Agent Architecture

Each agent inherits from `BaseA2AAgent` and provides:

- **Agent Cards**: JSON metadata at `/.well-known/agent.json` describing capabilities
- **Skills**: Specific functions the agent can perform (health_check, data processing, etc.)
- **Service Discovery**: Redis-backed agent registration and discovery
- **HTTP Endpoints**: FastAPI server with A2A protocol support
- **Health Monitoring**: `/health` endpoint for service monitoring

## Configuration

Settings are managed via Pydantic with `.env` file support:

### A2A Protocol Settings

- `A2A_HOST` / `A2A_PORT`: Agent server binding
- `A2A_API_KEY`: API key authentication (optional)
- `A2A_BEARER_TOKEN`: Bearer token authentication (optional)

### Core Infrastructure

- `DATABASE_URL`: PostgreSQL connection (planned)
- `REDIS_URL`: Redis for A2A service discovery
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`: Reddit API credentials
- `GEMINI_API_KEY`: Google Gemini for summarization
- `SLACK_WEBHOOK_URL` / `SMTP_*`: Notification channels

## Security

**Environment Variables**: All sensitive configuration is managed through environment variables and **never committed to version control**.

**Credential Management**:
- Copy `.env.example` to `.env` and populate with your actual API keys and credentials
- The `.env` file is automatically ignored by git via `.gitignore`
- Never commit real API keys, tokens, or credentials to the repository
- Use placeholder values in `.env.example` for documentation purposes

**Required Credentials**:
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`: Reddit API application credentials
- `GEMINI_API_KEY`: Google Gemini API key for AI summarization
- `SLACK_WEBHOOK_URL` / `SMTP_*`: Optional notification service credentials

**Security Best Practices**:
- Rotate API keys regularly
- Use least-privilege access for service accounts
- Monitor API usage for anomalies
- Keep dependencies updated via `uv sync`

## Key Design Patterns

**A2A Protocol Compliance**: All agents implement Google's A2A standard for interoperability.

**Agent Cards**: Self-describing JSON metadata enabling dynamic service discovery.

**Skill-Based Architecture**: Each agent exposes discrete skills that can be invoked via A2A protocol.

**Service Discovery**: Redis-backed agent registration with TTL and health monitoring.

**Async-First**: All agent operations use async/await for high-performance I/O.

**Error Handling**: Robust error propagation through A2A EventQueue with structured responses.

## Testing Strategy

- **Unit Tests**: Core agent functionality and skill execution (`test_a2a_base.py`)
- **Integration Tests**: A2A protocol compliance and agent communication (planned)
- **Agent Card Validation**: JSON schema validation for service discovery
- **Health Check Tests**: Service monitoring and discovery validation
- **CLI Testing**: Manual validation via `tests/cli/test_agent_cli.py`

## Development Workflow

1. All agents inherit from `BaseA2AAgent` for A2A compliance
2. Implement required methods: `get_skills()`, `execute_skill()`, `get_health_status()`
3. Use `pre-commit` hooks for code quality (ruff formatting/linting)
4. Test agents via CLI before integration
5. Follow 16-step implementation plan in `docs/specs/prompt_plan.md`

## Implementation Status

**✅ Phase A: Foundation (Steps 1-4)**

- Step 1: Repository bootstrap with uv and A2A SDK
- Step 2: Docker multi-stage build infrastructure
- Step 3: Pydantic configuration with A2A settings
- Step 4: BaseA2AAgent class and service discovery

**🔄 Phase B: Core Agents (Steps 5-11)**

- Step 5: SQLAlchemy models for state management
- Step 6: Alembic migration pipeline
- Steps 7-11: Individual agent implementations

**⏳ Phase C: Production (Steps 12-16)**

- Testing, monitoring, and deployment to Hostinger VPS

## Deployment

Current containerization setup:

- Multi-stage Dockerfile with uv and non-root user
- Docker Compose with Redis and PostgreSQL services
- Environment-based configuration via `.env` files
- FastAPI servers with health checks and graceful shutdown
