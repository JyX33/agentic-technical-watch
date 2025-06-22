# Code Review - Recommended Fixes

This document provides specific code fixes for the critical and high-priority issues identified in the comprehensive code review.

## 🚨 Critical Security Fixes

### 1. Implement Authentication Middleware

Create `reddit_watcher/auth_middleware.py`:

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import wraps
import jwt
from datetime import datetime, timedelta
from typing import Optional

from reddit_watcher.config import get_settings

security = HTTPBearer()

class AuthMiddleware:
    def __init__(self):
        self.settings = get_settings()

    async def verify_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> str:
        """Verify bearer token or API key."""
        token = credentials.credentials

        # Check API key first
        if self.settings.a2a_api_key and token == self.settings.a2a_api_key:
            return "api_key"

        # Check JWT token
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=["HS256"]
            )
            return payload.get("sub", "unknown")
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication credentials"
            )

# Update server.py to use authentication
from reddit_watcher.auth_middleware import AuthMiddleware

auth = AuthMiddleware()

@app.post("/skills/{skill_name}", dependencies=[Depends(auth.verify_token)])
async def invoke_skill(skill_name: str, request: dict):
    # Existing implementation
```

### 2. Fix Async Event Loop Blocking

Update `reddit_watcher/agents/retrieval_agent.py`:

```python
# Replace time.sleep with asyncio.sleep
async def _ensure_rate_limit(self) -> None:
    """Ensure we don't exceed Reddit API rate limits."""
    current_time = asyncio.get_event_loop().time()
    time_since_last = current_time - self._last_request_time

    if time_since_last < self._min_request_interval:
        sleep_time = self._min_request_interval - time_since_last
        self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
        await asyncio.sleep(sleep_time)  # Fixed: was time.sleep()

    self._last_request_time = asyncio.get_event_loop().time()
```

### 3. Fix HTML Injection Vulnerability

Update `reddit_watcher/agents/alert_agent.py`:

```python
from markupsafe import Markup, escape
import jinja2

class AlertAgent(BaseA2AAgent):
    def __init__(self):
        super().__init__(...)
        # Configure Jinja2 with autoescape
        self.jinja_env = jinja2.Environment(
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            loader=jinja2.BaseLoader()
        )

    def _create_email_html_content(self, summary_data: dict[str, Any]) -> str:
        """Create HTML email content with proper escaping."""
        template_str = """
        <!DOCTYPE html>
        <html>
        <head><title>Reddit Technical Watcher Alert</title></head>
        <body>
            <h2>{{ title | e }}</h2>
            <p><strong>Topic:</strong> {{ topic | e }}</p>
            <p><strong>Time Range:</strong> {{ time_range | e }}</p>

            <h3>Summary</h3>
            <div>{{ summary_content | e | nl2br }}</div>

            <h3>Top Posts</h3>
            <ul>
            {% for post in posts %}
                <li>
                    <a href="{{ post.url | e }}">{{ post.title | e }}</a>
                    (Score: {{ post.score | e }})
                </li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """

        template = self.jinja_env.from_string(template_str)
        return template.render(**summary_data)
```

### 4. Fix Database Configuration

Update `reddit_watcher/config.py`:

```python
class Settings(BaseSettings):
    # Add production database configuration
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Validate and secure database URL."""
        if not v:
            raise ValueError("Database URL cannot be empty")

        # Parse and validate
        parsed = urlparse(v)
        if parsed.scheme not in ["postgresql", "postgresql+asyncpg"]:
            raise ValueError("Must use PostgreSQL")

        # Ensure password is not default in production
        if "postgres:postgres" in v and cls.is_production():
            raise ValueError(
                "Default PostgreSQL credentials not allowed in production"
            )

        return v
```

## 🏗️ Architecture Improvements

### 5. Replace Singleton with Dependency Injection

Update `reddit_watcher/agents/base.py`:

```python
from typing import Protocol

class ConfigProvider(Protocol):
    """Protocol for configuration providers."""
    def get_setting(self, key: str) -> Any: ...
    def get_all_settings(self) -> dict[str, Any]: ...

class BaseA2AAgent(ABC):
    def __init__(
        self,
        config: ConfigProvider,  # Inject config instead of using singleton
        agent_type: str,
        name: str,
        description: str,
        version: str = "1.0.0"
    ):
        self.config = config
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.version = version
        self.logger = logging.getLogger(f"{__name__}.{agent_type}")
```

### 6. Implement Circuit Breaker Pattern

Create `reddit_watcher/circuit_breaker.py`:

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any, Optional
import asyncio
from functools import wraps

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        return (
            self.last_failure_time and
            datetime.now() - self.last_failure_time >
            timedelta(seconds=self.recovery_timeout)
        )

    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

# Usage in CoordinatorAgent
class CoordinatorAgent(BaseA2AAgent):
    @CircuitBreaker(failure_threshold=3, recovery_timeout=120)
    async def _call_agent(
        self,
        agent_url: str,
        skill: str,
        params: dict
    ) -> dict:
        """Call an agent with circuit breaker protection."""
        # Existing implementation
```

### 7. Fix Resource Management

Update `reddit_watcher/agents/coordinator_agent.py`:

```python
class CoordinatorAgent(BaseA2AAgent):
    async def __aenter__(self):
        """Async context manager entry."""
        self._http_session = await self._ensure_http_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self._cleanup_http_session()

    async def _cleanup_http_session(self) -> None:
        """Clean up HTTP session properly."""
        if hasattr(self, "_http_session") and self._http_session:
            if not self._http_session.closed:
                await self._http_session.close()
            self._http_session = None

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, "_http_session") and self._http_session:
            if not self._http_session.closed:
                asyncio.create_task(self._http_session.close())
```

## 📊 Database Performance Fixes

### 8. Add Missing Indexes Migration

Create `alembic/versions/xxxx_add_missing_indexes.py`:

```python
"""Add missing indexes for performance

Revision ID: xxxx
Revises: previous_revision
Create Date: 2024-xx-xx

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add critical performance indexes
    op.create_index(
        'ix_reddit_comments_post_id',
        'reddit_comments',
        ['post_id']
    )
    op.create_index(
        'ix_reddit_posts_subreddit_created',
        'reddit_posts',
        ['subreddit', 'created_utc']
    )
    op.create_index(
        'ix_content_filters_post_id',
        'content_filters',
        ['post_id']
    )
    op.create_index(
        'ix_content_filters_comment_id',
        'content_filters',
        ['comment_id']
    )
    op.create_index(
        'ix_content_summaries_filter_id',
        'content_summaries',
        ['content_filter_id']
    )
    op.create_index(
        'ix_alert_deliveries_batch_id',
        'alert_deliveries',
        ['alert_batch_id']
    )

def downgrade():
    op.drop_index('ix_reddit_comments_post_id')
    op.drop_index('ix_reddit_posts_subreddit_created')
    op.drop_index('ix_content_filters_post_id')
    op.drop_index('ix_content_filters_comment_id')
    op.drop_index('ix_content_summaries_filter_id')
    op.drop_index('ix_alert_deliveries_batch_id')
```

### 9. Fix Model Relationships

Update `reddit_watcher/models.py`:

```python
class RedditPost(Base):
    __tablename__ = "reddit_posts"

    # ... existing fields ...

    # Fix: Rename duplicate relationship
    subreddit_obj: Mapped[Subreddit] = relationship(
        "Subreddit",
        back_populates="posts"
    )

    # Add cascade options
    comments: Mapped[list["RedditComment"]] = relationship(
        "RedditComment",
        back_populates="post",
        cascade="all, delete-orphan"
    )
    content_filters: Mapped[list["ContentFilter"]] = relationship(
        "ContentFilter",
        back_populates="post",
        cascade="all, delete-orphan"
    )
```

## 🧪 Testing Improvements

### 10. Add Integration Test for Workflow

Create `tests/integration/test_full_workflow.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.database.utils import get_test_db_session

@pytest.mark.asyncio
async def test_complete_workflow_with_failures():
    """Test complete workflow with agent failures and recovery."""

    # Setup test database
    async with get_test_db_session() as session:
        coordinator = CoordinatorAgent()

        # Mock agent responses
        with patch.object(coordinator, '_call_agent') as mock_call:
            # Simulate retrieval agent failure then success
            mock_call.side_effect = [
                Exception("Network error"),  # First attempt fails
                {"status": "success", "posts_found": 10},  # Retry succeeds
                {"status": "success", "relevant": True},  # Filter success
                {"status": "success", "summary": "Test summary"},  # Summarize
                {"status": "success", "delivered": True}  # Alert
            ]

            # Run workflow
            result = await coordinator.execute_skill(
                "start_monitoring_cycle",
                {"topics": ["test"]}
            )

            # Verify retry logic worked
            assert result["status"] == "success"
            assert mock_call.call_count == 5  # Including retry
```

## 🔒 Security Configuration

### 11. Secure Docker Compose

Update `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME:-reddit_watcher}
      POSTGRES_USER: ${DB_USER:-reddit_watcher_user}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?Database password required}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-reddit_watcher_user}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:?Redis password required}
    networks:
      - internal
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Agents with proper security
  coordinator:
    build:
      context: .
      target: runtime
    environment:
      - AGENT_TYPE=coordinator
      - A2A_API_KEY=${A2A_API_KEY:?API key required}
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://default:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal
      - external
    ports:
      - "8000:8000"
    user: appuser:appuser

networks:
  internal:
    driver: bridge
    internal: true
  external:
    driver: bridge

volumes:
  postgres_data:
```

## Conclusion

These fixes address the most critical issues identified in the code review. Implement them in order of priority, starting with security fixes. Each fix includes specific code examples that can be directly applied to the codebase.

Remember to:
1. Test each fix thoroughly
2. Update documentation as you go
3. Run security scans after implementing fixes
4. Monitor performance improvements from database indexes
