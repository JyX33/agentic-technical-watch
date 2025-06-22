# Reddit Technical Watcher

An autonomous agent-based system that monitors Reddit for technical discussions and provides intelligent summaries using **Google's A2A (Agent-to-Agent) protocol**.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![A2A Protocol](https://img.shields.io/badge/A2A-Agent--to--Agent-green.svg)](https://github.com/google-a2a/A2A)
[![uv](https://img.shields.io/badge/uv-dependency%20management-orange.svg)](https://github.com/astral-sh/uv)

## 🎯 What It Does

Reddit Technical Watcher automatically:

- **Monitors** Reddit every 4 hours for configurable topics (e.g., "Claude Code", "A2A", "Agent-to-Agent")
- **Filters** content for relevance using intelligent scoring
- **Summarizes** key discussions using Gemini 2.5 Flash
- **Alerts** you via Slack and email about important developments

**Example Topics:** AI tools, programming frameworks, cloud platforms, developer productivity tools

## ✨ Key Features

- 🤖 **Multi-Agent Architecture** using Google's A2A protocol
- 🔍 **Smart Content Discovery** from Reddit posts and comments
- 🧠 **AI-Powered Summarization** with Gemini integration
- 📡 **Service Discovery** with automatic agent registration
- 🐳 **Container-Ready** with Docker and docker-compose
- ⚡ **Real-time Communication** between agents via A2A protocol
- 📊 **Health Monitoring** and observability for all agents

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- [uv](https://github.com/astral-sh/uv) for dependency management

### 1. Clone and Setup

```bash
git clone <repository-url>
cd agentic-technical-watch

# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### 2. Start Infrastructure

```bash
# Start Redis and PostgreSQL
docker-compose up -d redis postgres
```

### 3. Test the System

```bash
# Run the test agent
uv run python tests/cli/test_agent_cli.py

# Or start an interactive agent server
uv run python -m reddit_watcher.agents.test_agent
```

### 4. Check Agent Endpoints

```bash
# Agent discovery metadata
curl http://localhost:8000/.well-known/agent.json

# Health status
curl http://localhost:8000/health

# Service discovery
curl http://localhost:8000/discover
```

## 🏗️ Architecture

The system uses **Google's A2A (Agent-to-Agent) protocol** for multi-agent communication:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  RetrievalAgent │    │   FilterAgent   │    │ SummariseAgent  │
│   (Reddit API)  │───▶│  (Relevance)    │───▶│   (Gemini AI)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐              │
│ CoordinatorAgent│◄───│   AlertAgent    │◄─────────────┘
│  (Orchestrator) │    │ (Slack/Email)   │
└─────────────────┘    └─────────────────┘

               A2A Protocol Communication
                   Redis Service Discovery
```

### Agent Responsibilities

| Agent | Purpose | Technologies |
|-------|---------|-------------|
| **RetrievalAgent** | Fetch Reddit posts and comments | PRAW, Reddit API |
| **FilterAgent** | Determine content relevance | Keyword matching, semantic scoring |
| **SummariseAgent** | Generate intelligent summaries | Gemini 2.5 Flash |
| **AlertAgent** | Send notifications | Slack WebHooks, SMTP |
| **CoordinatorAgent** | Orchestrate the workflow | A2A protocol coordination |

## 🛠️ Development

### Project Structure

```
reddit_watcher/
├── agents/                # A2A Agent implementations
│   ├── base.py           # BaseA2AAgent abstract class
│   ├── server.py         # A2A HTTP server & service discovery
│   └── test_agent.py     # Test agent for validation
├── config.py             # Pydantic configuration management
tests/
├── test_a2a_base.py      # A2A functionality tests
└── test_config.py        # Configuration tests
docs/specs/               # Implementation specifications
Dockerfile                # Multi-stage container build
docker-compose.yml        # Development services
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/test_a2a_base.py -v

# Run with coverage
uv run pytest --cov=reddit_watcher
```

### Code Quality

```bash
# Auto-format and lint
uv run pre-commit run --all-files

# Manual linting
uv run ruff check .

# Manual formatting
uv run ruff format .
```

### Creating New Agents

1. **Inherit from BaseA2AAgent**:

```python
from reddit_watcher.agents.base import BaseA2AAgent
from a2a.types import AgentSkill

class MyAgent(BaseA2AAgent):
    def __init__(self):
        super().__init__(
            agent_type="my_agent",
            name="My Custom Agent",
            description="Does something useful",
            version="1.0.0"
        )

    def get_skills(self) -> list[AgentSkill]:
        return [
            AgentSkill(
                id="my_skill",
                name="my_skill",
                description="My agent's capability",
                tags=["custom"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[]
            )
        ]

    async def execute_skill(self, skill_name: str, parameters: dict) -> dict:
        if skill_name == "my_skill":
            return {"status": "success", "result": "Hello A2A!"}
        raise ValueError(f"Unknown skill: {skill_name}")

    def get_health_status(self) -> dict:
        health = self.get_common_health_status()
        health.update({"custom_status": "operational"})
        return health
```

2. **Test your agent**:

```python
# Create test script
agent = MyAgent()
result = await agent.execute_skill("my_skill", {})
print(result)
```

3. **Deploy as A2A server**:

```python
from reddit_watcher.agents.server import run_agent_server

if __name__ == "__main__":
    agent = MyAgent()
    run_agent_server(agent)  # Starts on http://localhost:8000
```

## ⚙️ Configuration

Configuration is managed via environment variables and `.env` files:

### Core Settings

```env
# A2A Protocol
A2A_HOST=0.0.0.0
A2A_PORT=8000
A2A_API_KEY=your-api-key-here
A2A_BEARER_TOKEN=your-bearer-token

# Infrastructure
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reddit_watcher

# Reddit API
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-secret

# AI Services
GEMINI_API_KEY=your-gemini-api-key

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SMTP_SERVER=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Monitoring Topics
REDDIT_TOPICS=Claude Code,A2A,Agent-to-Agent
PROCESSING_INTERVAL=14400  # 4 hours in seconds
RELEVANCE_THRESHOLD=0.7
```

### Docker Environment

```bash
# Copy example environment
cp .env.example .env

# Edit with your credentials
nano .env

# Start with docker-compose
docker-compose up -d
```

## 📡 A2A API Endpoints

Each agent exposes standard A2A protocol endpoints:

### Service Discovery

- `GET /.well-known/agent.json` - Agent Card metadata
- `GET /health` - Health status and metrics
- `GET /discover` - Discover other registered agents

### A2A Protocol

- `POST /a2a/message` - Send messages to agent skills
- `POST /a2a/stream` - Streaming message support
- `GET /a2a/task/{task_id}` - Get task status

### Example Agent Card

```json
{
  "name": "Test A2A Agent",
  "description": "Test agent for validating A2A protocol implementation",
  "version": "1.0.0",
  "url": "http://localhost:8000",
  "provider": {
    "organization": "Reddit Technical Watcher",
    "url": "https://github.com/reddit-technical-watcher"
  },
  "skills": [
    {
      "id": "health_check",
      "name": "health_check",
      "description": "Check the health status of the agent",
      "tags": ["health", "status"],
      "inputModes": ["text/plain", "application/json"],
      "outputModes": ["application/json"]
    }
  ]
}
```

## 🔧 Implementation Status

### ✅ **Phase A: Foundation (Complete)**

- [x] Repository bootstrap with uv and A2A SDK
- [x] Docker multi-stage build infrastructure
- [x] Pydantic configuration with A2A settings
- [x] BaseA2AAgent class and service discovery

### 🔄 **Phase B: Core Agents (In Progress)**

- [ ] SQLAlchemy models for state management
- [ ] Alembic migration pipeline
- [ ] RetrievalAgent - Reddit data fetching
- [ ] FilterAgent - Content relevance assessment
- [ ] SummariseAgent - AI summarization with Gemini
- [ ] AlertAgent - Multi-channel notifications
- [ ] CoordinatorAgent - Workflow orchestration

### ⏳ **Phase C: Production (Planned)**

- [ ] Integration testing framework
- [ ] Monitoring and observability
- [ ] Deployment to Hostinger VPS

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Install dev dependencies**: `uv sync`
4. **Make your changes** following the existing patterns
5. **Run tests**: `uv run pytest`
6. **Run quality checks**: `uv run pre-commit run --all-files`
7. **Commit changes**: `git commit -m 'Add amazing feature'`
8. **Push to branch**: `git push origin feature/amazing-feature`
9. **Create Pull Request**

### Development Guidelines

- All agents must inherit from `BaseA2AAgent`
- Follow A2A protocol standards for interoperability
- Include comprehensive tests for new functionality
- Use async/await for all I/O operations
- Document A2A skills and capabilities clearly

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Google A2A Team** for the Agent-to-Agent protocol
- **Astral** for the uv dependency management tool
- **FastAPI** for the excellent async web framework
- **Reddit API** for providing access to community discussions

---

**Built with ❤️ using Google's A2A Protocol**
