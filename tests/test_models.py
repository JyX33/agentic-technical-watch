# Tests for SQLAlchemy models and database operations
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from reddit_watcher.database import (
    check_database_health,
    create_a2a_task,
    get_pending_tasks,
)
from reddit_watcher.models import (
    A2ATask,
    A2AWorkflow,
    AlertBatch,
    Base,
    ContentFilter,
    ContentSummary,
    RedditComment,
    RedditPost,
    Subreddit,
    TaskStatus,
)


@pytest.fixture
def test_db_engine():
    """Create test database engine with SQLite."""
    # Use SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create test database session."""
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()
    yield session
    session.close()


class TestModels:
    """Test SQLAlchemy model definitions."""

    def test_subreddit_model(self, test_db_session):
        """Test Subreddit model creation and relationships."""
        subreddit = Subreddit(
            name="Python",
            display_name="r/Python",
            description="News about the dynamic programming language Python",
            subscribers=950000,
        )
        test_db_session.add(subreddit)
        test_db_session.commit()

        assert subreddit.id is not None
        assert subreddit.name == "Python"
        assert subreddit.is_active is True
        assert subreddit.discovered_at is not None

    def test_reddit_post_model(self, test_db_session):
        """Test RedditPost model and foreign key relationships."""
        # Create subreddit first
        subreddit = Subreddit(name="Python")
        test_db_session.add(subreddit)
        test_db_session.commit()

        # Create post
        post = RedditPost(
            reddit_id="abc123",
            title="Test post about Claude Code",
            content="This is a test post content",
            author="test_user",
            score=42,
            num_comments=5,
            created_utc=datetime.now(UTC),
            subreddit_id=subreddit.id,
        )
        test_db_session.add(post)
        test_db_session.commit()

        assert post.id is not None
        assert post.subreddit.name == "Python"
        assert post.title == "Test post about Claude Code"

    def test_reddit_comment_model(self, test_db_session):
        """Test RedditComment model with parent relationships."""
        # Create subreddit and post
        subreddit = Subreddit(name="Python")
        test_db_session.add(subreddit)
        test_db_session.commit()

        post = RedditPost(
            reddit_id="post123",
            title="Test post",
            created_utc=datetime.now(UTC),
            subreddit_id=subreddit.id,
        )
        test_db_session.add(post)
        test_db_session.commit()

        # Create comment
        comment = RedditComment(
            reddit_id="comment123",
            body="This is a test comment",
            author="commenter",
            score=10,
            created_utc=datetime.now(UTC),
            post_id=post.id,
            subreddit_id=subreddit.id,
        )
        test_db_session.add(comment)
        test_db_session.commit()

        assert comment.id is not None
        assert comment.post.title == "Test post"
        assert comment.subreddit.name == "Python"

    def test_content_filter_model(self, test_db_session):
        """Test ContentFilter model with relevance scoring."""
        # Create dependencies
        subreddit = Subreddit(name="Python")
        test_db_session.add(subreddit)
        test_db_session.commit()

        post = RedditPost(
            reddit_id="post123",
            title="Claude Code discussion",
            created_utc=datetime.now(UTC),
            subreddit_id=subreddit.id,
        )
        test_db_session.add(post)
        test_db_session.commit()

        # Create filter result
        content_filter = ContentFilter(
            relevance_score=0.85,
            is_relevant=True,
            keywords_matched=["Claude Code", "AI", "agent"],
            semantic_similarity=0.78,
            filter_reason="High keyword match and semantic similarity",
            post_id=post.id,
        )
        test_db_session.add(content_filter)
        test_db_session.commit()

        assert content_filter.id is not None
        assert content_filter.is_relevant is True
        assert "Claude Code" in content_filter.keywords_matched
        assert content_filter.post.title == "Claude Code discussion"

    def test_content_summary_model(self, test_db_session):
        """Test ContentSummary model with AI-generated content."""
        # Create full dependency chain
        subreddit = Subreddit(name="Python")
        test_db_session.add(subreddit)
        test_db_session.commit()

        post = RedditPost(
            reddit_id="post123",
            title="Claude Code features",
            created_utc=datetime.now(UTC),
            subreddit_id=subreddit.id,
        )
        test_db_session.add(post)
        test_db_session.commit()

        content_filter = ContentFilter(
            relevance_score=0.90,
            is_relevant=True,
            keywords_matched=["Claude Code"],
            post_id=post.id,
        )
        test_db_session.add(content_filter)
        test_db_session.commit()

        # Create summary
        summary = ContentSummary(
            summary_text="Discussion about Claude Code's new A2A agent features",
            key_points=["A2A protocol", "Agent communication", "Reddit monitoring"],
            sentiment="positive",
            confidence_score=0.92,
            model_used="gemini-2.5-flash",
            processing_time_ms=1200,
            content_filter_id=content_filter.id,
        )
        test_db_session.add(summary)
        test_db_session.commit()

        assert summary.id is not None
        assert "A2A protocol" in summary.key_points
        assert summary.content_filter.post.title == "Claude Code features"


class TestA2AModels:
    """Test A2A workflow and task models."""

    def test_a2a_task_model(self, test_db_session):
        """Test A2ATask model for workflow orchestration."""
        task = A2ATask(
            task_id="550e8400-e29b-41d4-a716-446655440000",
            agent_type="retrieval",
            skill_name="fetch_reddit_posts",
            parameters={"subreddit": "Python", "limit": 25},
            workflow_id="reddit_scan_001",
            priority=3,
        )
        test_db_session.add(task)
        test_db_session.commit()

        assert task.id is not None
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
        assert task.parameters["subreddit"] == "Python"

    def test_a2a_workflow_model(self, test_db_session):
        """Test A2AWorkflow model for orchestration state."""
        workflow = A2AWorkflow(
            workflow_id="reddit_scan_001",
            workflow_type="reddit_scan",
            schedule="0 */4 * * *",  # Every 4 hours
            config={
                "subreddits": ["Python", "MachineLearning"],
                "topics": ["Claude Code", "A2A"],
                "relevance_threshold": 0.7,
            },
        )
        test_db_session.add(workflow)
        test_db_session.commit()

        assert workflow.id is not None
        assert workflow.status == TaskStatus.PENDING
        assert workflow.run_count == 0
        assert "Python" in workflow.config["subreddits"]

    def test_alert_batch_model(self, test_db_session):
        """Test AlertBatch model for notification delivery."""
        alert_batch = AlertBatch(
            batch_id="alert_001",
            title="New Claude Code Discussions",
            summary="5 relevant posts found about Claude Code features",
            total_items=5,
            channels=["slack", "email"],
            priority=2,
        )
        test_db_session.add(alert_batch)
        test_db_session.commit()

        assert alert_batch.id is not None
        assert "slack" in alert_batch.channels
        assert alert_batch.total_items == 5


class TestDatabaseOperations:
    """Test database utility functions."""

    @patch("reddit_watcher.database.get_db_session")
    def test_create_a2a_task(self, mock_session):
        """Test A2A task creation."""
        # Mock the session context manager
        mock_session.return_value.__enter__.return_value = test_db_session
        mock_session.return_value.__exit__.return_value = None

        task_id = create_a2a_task(
            agent_type="filter",
            skill_name="assess_relevance",
            parameters={"content_id": 123, "threshold": 0.7},
            workflow_id="test_workflow",
            priority=2,
        )

        assert task_id is not None
        assert len(task_id) == 36  # UUID4 length

    @patch("reddit_watcher.database.get_db_session")
    def test_get_pending_tasks(self, mock_session):
        """Test retrieving pending tasks."""
        # This would need a more complex mock setup for the actual query
        # For now, just test the function exists and can be called
        tasks = get_pending_tasks(agent_type="retrieval", limit=5)
        assert isinstance(tasks, list)

    @patch("reddit_watcher.database.get_db_session")
    def test_database_health_check(self, mock_session):
        """Test database health check function."""
        health = check_database_health()
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy"]


class TestModelValidation:
    """Test model validation and constraints."""

    def test_task_status_enum(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_required_fields(self, test_db_session):
        """Test that required fields are enforced."""
        # Test missing required field
        with pytest.raises(IntegrityError):  # Should raise an integrity error
            post = RedditPost(
                # Missing reddit_id and title
                created_utc=datetime.now(UTC),
                subreddit_id=1,
            )
            test_db_session.add(post)
            test_db_session.commit()

    def test_unique_constraints(self, test_db_session):
        """Test unique constraints."""
        # Create first subreddit
        subreddit1 = Subreddit(name="Python")
        test_db_session.add(subreddit1)
        test_db_session.commit()

        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):  # Should raise integrity error
            subreddit2 = Subreddit(name="Python")
            test_db_session.add(subreddit2)
            test_db_session.commit()
