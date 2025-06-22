# System Architecture & Design Documentation

Comprehensive documentation of the Reddit Technical Watcher system architecture, design decisions, and technical specifications.

## Architecture Overview

The Reddit Technical Watcher is an autonomous agent-based system built on Google's **Agent-to-Agent (A2A) protocol** that monitors Reddit every 4 hours for configurable topics (e.g., "Claude Code"). The system follows a **microservices architecture** with five specialized agents orchestrating the complete workflow: **Collect → Filter → Summarize → Alert**.

## Documentation Structure

### Core Architecture
- **[System Architecture](./system-architecture.md)** - High-level system design and component relationships
- **[Agent Architecture](./agent-architecture.md)** - A2A agent design patterns and communication protocols
- **[Data Architecture](./data-architecture.md)** - Data models, flow, and persistence strategies

### Design Decisions
- **[Architectural Decisions](./architectural-decisions.md)** - Key design decisions and rationale
- **[Technology Choices](./technology-choices.md)** - Technology stack selection and justification
- **[Design Patterns](./design-patterns.md)** - Software patterns and architectural styles

### Technical Specifications
- **[API Specifications](./api-specifications.md)** - A2A protocol implementation and endpoints
- **[Database Schema](./database-schema.md)** - Complete database design and relationships
- **[Security Architecture](./security-architecture.md)** - Security design and implementation

### Infrastructure Design
- **[Deployment Architecture](./deployment-architecture.md)** - Infrastructure and deployment strategies
- **[Monitoring Architecture](./monitoring-architecture.md)** - Observability and monitoring design
- **[Scalability Design](./scalability-design.md)** - Performance and scaling considerations

## Quick Reference

### System Components

**Core Agents:**
- **CoordinatorAgent** (Port 8000): Workflow orchestration via A2A protocol
- **RetrievalAgent** (Port 8001): Reddit API data collection and subreddit discovery
- **FilterAgent** (Port 8002): Content relevance filtering with semantic analysis
- **SummariseAgent** (Port 8003): AI-powered content summarization via Gemini
- **AlertAgent** (Port 8004): Multi-channel notification delivery

**Infrastructure:**
- **PostgreSQL**: Primary data persistence with SQLAlchemy 2.0
- **Redis**: A2A service discovery and caching
- **Docker/Compose**: Containerization and orchestration
- **FastAPI**: HTTP servers with A2A protocol support

### Technology Stack

**Core Technologies:**
- **Python 3.12+** with `uv` dependency management
- **Google A2A SDK** for agent-to-agent communication
- **FastAPI** for HTTP API endpoints
- **SQLAlchemy 2.0** with Alembic migrations
- **Pydantic** for configuration and data validation

**External APIs:**
- **Reddit API (PRAW)** for content retrieval
- **Google Gemini 2.5 Flash** for AI summarization
- **Slack Webhooks** for notifications
- **SMTP** for email alerts

### Key Design Principles

1. **A2A Protocol Compliance**: All agents implement Google's A2A standard
2. **Service Discovery**: Redis-backed dynamic agent registration
3. **Asynchronous Processing**: Non-blocking I/O for high performance
4. **Error Resilience**: Circuit breakers and graceful degradation
5. **Security First**: Authentication, authorization, and audit logging

## Architecture Diagrams

### High-Level System Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Reddit API    │    │   Gemini API    │    │ Slack/Email APIs│
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ RetrievalAgent  │    │ SummariseAgent  │    │   AlertAgent    │
│   (Port 8001)   │    │   (Port 8003)   │    │   (Port 8004)   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │              ┌───────┴───────┐              │
          │              │ FilterAgent   │              │
          │              │ (Port 8002)   │              │
          │              └───────┬───────┘              │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   CoordinatorAgent      │
                    │     (Port 8000)         │
                    │   A2A Orchestration     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    Infrastructure       │
                    │  PostgreSQL + Redis     │
                    │   Docker Compose        │
                    └─────────────────────────┘
```

### A2A Communication Flow
```
1. HTTP Request → CoordinatorAgent
2. A2A Message → RetrievalAgent (collect data)
3. A2A Message → FilterAgent (relevance filtering)
4. A2A Message → SummariseAgent (AI summarization)
5. A2A Message → AlertAgent (notification delivery)
6. HTTP Response ← CoordinatorAgent (workflow status)
```

## Design Goals

### Primary Objectives
- **Autonomous Operation**: Minimal human intervention required
- **Scalable Architecture**: Handle increasing data volumes
- **Reliable Processing**: Fault-tolerant with graceful degradation
- **Real-time Alerting**: Timely notification delivery
- **Maintainable Code**: Clear separation of concerns

### Quality Attributes
- **Performance**: Sub-second API response times
- **Reliability**: 99.9% uptime target
- **Scalability**: Horizontal scaling capability
- **Security**: Authentication and audit trails
- **Observability**: Comprehensive monitoring and logging

## Implementation Phases

### Phase A: Foundation (Completed)
✅ Repository bootstrap with uv and A2A SDK
✅ Docker multi-stage build infrastructure
✅ Pydantic configuration with A2A settings
✅ BaseA2AAgent class and service discovery

### Phase B: Core Agents (Completed)
✅ SQLAlchemy models for state management
✅ Alembic migration pipeline
✅ Individual agent implementations
✅ A2A communication protocols
✅ Error handling and circuit breakers

### Phase C: Production (Completed)
✅ Comprehensive testing suite
✅ Monitoring and alerting setup
✅ Security implementation
✅ Production deployment automation

## Future Evolution

### Planned Enhancements
- **Machine Learning**: Enhanced content filtering with ML models
- **Multi-Platform**: Expand beyond Reddit to other social platforms
- **Advanced Analytics**: Trend analysis and predictive insights
- **API Gateway**: Centralized API management and rate limiting

### Scalability Roadmap
- **Microservice Decomposition**: Further agent specialization
- **Event-Driven Architecture**: Async event processing
- **Multi-Region Deployment**: Geographic distribution
- **Auto-Scaling**: Dynamic resource allocation

## Documentation Standards

### Architecture Documentation
- **C4 Model**: Context, Container, Component, Code diagrams
- **ADRs**: Architectural Decision Records for major decisions
- **RFC Process**: Request for Comments for significant changes
- **Version Control**: All architecture documents in Git

### Review Process
- **Quarterly Reviews**: Architecture assessment and updates
- **Change Management**: Formal review for architectural changes
- **Stakeholder Approval**: Engineering and operations sign-off
- **Documentation Updates**: Immediate documentation of changes

## Getting Started

### For Developers
1. **Read**: [System Architecture](./system-architecture.md)
2. **Understand**: [Agent Architecture](./agent-architecture.md)
3. **Review**: [Architectural Decisions](./architectural-decisions.md)
4. **Study**: [API Specifications](./api-specifications.md)

### For Operations
1. **Overview**: [Deployment Architecture](./deployment-architecture.md)
2. **Monitoring**: [Monitoring Architecture](./monitoring-architecture.md)
3. **Security**: [Security Architecture](./security-architecture.md)
4. **Scaling**: [Scalability Design](./scalability-design.md)

### For Architects
1. **Decisions**: [Architectural Decisions](./architectural-decisions.md)
2. **Patterns**: [Design Patterns](./design-patterns.md)
3. **Technology**: [Technology Choices](./technology-choices.md)
4. **Future**: Evolution and roadmap planning

---

*This architecture serves as the foundation for a robust, scalable, and maintainable Reddit monitoring system.*
