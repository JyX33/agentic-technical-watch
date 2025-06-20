# ABOUTME: Tests for RetrievalAgent Reddit data fetching functionality
# ABOUTME: Validates PRAW integration, A2A skills, rate limiting, and error handling

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from praw.exceptions import RedditAPIException
from praw.models import Comment

from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.config import reset_settings


class TestRetrievalAgent:
    """Test cases for RetrievalAgent."""

    def setup_method(self):
        """Set up test environment."""
        reset_settings()

    def teardown_method(self):
        """Clean up after tests."""
        reset_settings()

    def test_agent_initialization(self):
        """Test RetrievalAgent initialization."""
        agent = RetrievalAgent()

        assert agent.agent_type == "retrieval"
        assert agent.name == "Reddit Retrieval Agent"
        assert "PRAW" in agent.description
        assert agent.version == "1.0.0"
        assert agent.settings is not None

    def test_agent_skills(self):
        """Test agent skills definition."""
        agent = RetrievalAgent()
        skills = agent.get_skills()

        assert len(skills) == 5
        skill_names = [skill.name for skill in skills]
        assert "health_check" in skill_names
        assert "fetch_posts_by_topic" in skill_names
        assert "fetch_comments_from_post" in skill_names
        assert "discover_subreddits" in skill_names
        assert "fetch_subreddit_info" in skill_names

    def test_agent_card_generation(self):
        """Test Agent Card generation includes Reddit skills."""
        agent = RetrievalAgent()
        agent_card = agent.generate_agent_card()

        assert agent_card.name == agent.name
        assert agent_card.description == agent.description
        assert len(agent_card.skills) == 5

        # Check for Reddit-specific skills
        skill_names = [skill.name for skill in agent_card.skills]
        assert "fetch_posts_by_topic" in skill_names
        assert "discover_subreddits" in skill_names

    @pytest.mark.asyncio
    async def test_health_check_no_credentials(self):
        """Test health check when Reddit credentials are not configured."""
        agent = RetrievalAgent()
        result = await agent.execute_skill("health_check", {})

        assert result["skill"] == "health_check"
        assert result["status"] == "success"
        assert "reddit" in result["result"]

        reddit_status = result["result"]["reddit"]
        assert reddit_status["credentials_configured"] is False
        assert reddit_status["connectivity"] in ["not_initialized", "failed"]

    @pytest.mark.asyncio
    async def test_health_check_with_credentials(self):
        """Test health check with Reddit credentials configured."""
        with patch.dict(
            "os.environ",
            {
                "REDDIT_CLIENT_ID": "test-client-id",
                "REDDIT_CLIENT_SECRET": "test-client-secret",
            },
        ):
            reset_settings()

            # Mock the Reddit client initialization
            with patch(
                "reddit_watcher.agents.retrieval_agent.praw.Reddit"
            ) as mock_reddit:
                mock_reddit_instance = MagicMock()
                mock_reddit_instance.read_only = True
                mock_reddit.return_value = mock_reddit_instance

                agent = RetrievalAgent()
                result = await agent.execute_skill("health_check", {})

                assert result["skill"] == "health_check"
                assert result["status"] == "success"

                reddit_status = result["result"]["reddit"]
                assert reddit_status["credentials_configured"] is True
                assert reddit_status["initialized"] is True

    @pytest.mark.asyncio
    async def test_fetch_posts_by_topic_no_client(self):
        """Test fetch_posts_by_topic when Reddit client is not initialized."""
        agent = RetrievalAgent()
        agent._reddit_client = None  # Force no client

        result = await agent.execute_skill(
            "fetch_posts_by_topic", {"topic": "Claude Code"}
        )

        assert result["skill"] == "fetch_posts_by_topic"
        assert result["status"] == "error"
        assert "not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_posts_by_topic_no_topic(self):
        """Test fetch_posts_by_topic with missing topic parameter."""
        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_reddit.return_value = mock_reddit_instance

            # Patch credentials check
            with patch.object(RetrievalAgent, "_initialize_reddit_client"):
                agent = RetrievalAgent()
                agent._reddit_client = mock_reddit_instance  # Set mock client directly

                result = await agent.execute_skill("fetch_posts_by_topic", {})

                assert result["skill"] == "fetch_posts_by_topic"
                assert result["status"] == "error"
                assert "required" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_posts_by_topic_success(self):
        """Test successful fetch_posts_by_topic execution."""
        mock_submission = MagicMock()
        mock_submission.id = "test123"
        mock_submission.title = "Test Post"
        mock_submission.selftext = "Test content"
        mock_submission.is_self = True
        mock_submission.url = "https://reddit.com/r/test/test123"
        mock_submission.author = "testuser"
        mock_submission.subreddit = "test"
        mock_submission.created_utc = 1640995200  # 2022-01-01 00:00:00 UTC
        mock_submission.score = 42
        mock_submission.upvote_ratio = 0.95
        mock_submission.num_comments = 5
        mock_submission.is_video = False
        mock_submission.over_18 = False
        mock_submission.permalink = "/r/test/comments/test123/"

        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_subreddit = MagicMock()
            mock_subreddit.search.return_value = [mock_submission]
            mock_reddit_instance.subreddit.return_value = mock_subreddit
            mock_reddit.return_value = mock_reddit_instance

            # Mock database operations
            with patch(
                "reddit_watcher.agents.retrieval_agent.get_db_session"
            ) as mock_db_session:
                mock_session = MagicMock()
                mock_session.query.return_value.filter_by.return_value.first.return_value = None
                mock_db_session.return_value.__enter__.return_value = mock_session

                with patch.object(RetrievalAgent, "_initialize_reddit_client"):
                    agent = RetrievalAgent()
                    agent._reddit_client = (
                        mock_reddit_instance  # Set mock client directly
                    )

                    result = await agent.execute_skill(
                        "fetch_posts_by_topic",
                        {"topic": "Claude Code", "limit": 10},
                    )

                assert result["skill"] == "fetch_posts_by_topic"
                assert result["status"] == "success"
                assert result["result"]["topic"] == "Claude Code"
                assert result["result"]["posts_found"] == 1
                assert len(result["result"]["posts"]) == 1
                assert result["result"]["posts"][0]["post_id"] == "test123"

    @pytest.mark.asyncio
    async def test_fetch_comments_from_post_no_client(self):
        """Test fetch_comments_from_post when Reddit client is not initialized."""
        agent = RetrievalAgent()
        agent._reddit_client = None  # Force no client

        result = await agent.execute_skill(
            "fetch_comments_from_post", {"post_id": "test123"}
        )

        assert result["skill"] == "fetch_comments_from_post"
        assert result["status"] == "error"
        assert "not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_comments_from_post_no_post_id(self):
        """Test fetch_comments_from_post with missing post_id parameter."""
        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_reddit.return_value = mock_reddit_instance

            with patch.object(RetrievalAgent, "_initialize_reddit_client"):
                agent = RetrievalAgent()
                agent._reddit_client = mock_reddit_instance  # Set mock client directly

                result = await agent.execute_skill("fetch_comments_from_post", {})

                assert result["skill"] == "fetch_comments_from_post"
                assert result["status"] == "error"
                assert "required" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_comments_from_post_success(self):
        """Test successful fetch_comments_from_post execution."""
        # Use spec to make mock behave like a Comment
        mock_comment = MagicMock(spec=Comment)
        mock_comment.id = "comment123"
        mock_comment.body = "Test comment"
        mock_comment.author = "commenter"
        mock_comment.created_utc = 1640995200
        mock_comment.score = 10
        mock_comment.parent_id = "t3_test123"
        mock_comment.permalink = "/r/test/comments/test123/comment123/"
        mock_comment.is_submitter = False

        mock_submission = MagicMock()
        mock_submission.comments.replace_more = MagicMock()
        mock_submission.comments.list.return_value = [mock_comment]

        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_reddit_instance.submission.return_value = mock_submission
            mock_reddit.return_value = mock_reddit_instance

            # Mock database operations
            with patch(
                "reddit_watcher.agents.retrieval_agent.get_db_session"
            ) as mock_db_session:
                mock_session = MagicMock()
                mock_session.query.return_value.filter_by.return_value.first.return_value = None
                mock_db_session.return_value.__enter__.return_value = mock_session

                with patch.object(RetrievalAgent, "_initialize_reddit_client"):
                    agent = RetrievalAgent()
                    agent._reddit_client = (
                        mock_reddit_instance  # Set mock client directly
                    )

                    result = await agent.execute_skill(
                        "fetch_comments_from_post",
                        {"post_id": "test123", "limit": 10},
                    )

                assert result["skill"] == "fetch_comments_from_post"
                assert result["status"] == "success"
                assert result["result"]["post_id"] == "test123"
                assert result["result"]["comments_found"] == 1
                assert len(result["result"]["comments"]) == 1
                assert result["result"]["comments"][0]["comment_id"] == "comment123"

    @pytest.mark.asyncio
    async def test_discover_subreddits_success(self):
        """Test successful discover_subreddits execution."""
        mock_subreddit = MagicMock()
        mock_subreddit.display_name = "ClaudeCode"
        mock_subreddit.title = "Claude Code Discussion"
        mock_subreddit.public_description = "All about Claude Code"
        mock_subreddit.subscribers = 1000
        mock_subreddit.created_utc = 1640995200
        mock_subreddit.over18 = False
        mock_subreddit.lang = "en"

        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_reddit_instance.subreddits.search.return_value = [mock_subreddit]
            mock_reddit.return_value = mock_reddit_instance

            # Mock database operations
            with patch(
                "reddit_watcher.agents.retrieval_agent.get_db_session"
            ) as mock_db_session:
                mock_session = MagicMock()
                mock_session.query.return_value.filter_by.return_value.first.return_value = None
                mock_db_session.return_value.__enter__.return_value = mock_session

                with patch.object(RetrievalAgent, "_initialize_reddit_client"):
                    agent = RetrievalAgent()
                    agent._reddit_client = (
                        mock_reddit_instance  # Set mock client directly
                    )

                    result = await agent.execute_skill(
                        "discover_subreddits",
                        {"topic": "Claude Code", "limit": 5},
                    )

                assert result["skill"] == "discover_subreddits"
                assert result["status"] == "success"
                assert result["result"]["topic"] == "Claude Code"
                assert result["result"]["subreddits_found"] == 1
                assert len(result["result"]["subreddits"]) == 1
                assert result["result"]["subreddits"][0]["name"] == "ClaudeCode"

    @pytest.mark.asyncio
    async def test_fetch_subreddit_info_success(self):
        """Test successful fetch_subreddit_info execution."""
        mock_subreddit = MagicMock()
        mock_subreddit.display_name = "test"
        mock_subreddit.title = "Test Subreddit"
        mock_subreddit.public_description = "A test subreddit"
        mock_subreddit.subscribers = 500
        mock_subreddit.created_utc = 1640995200
        mock_subreddit.over18 = False
        mock_subreddit.lang = "en"

        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_reddit_instance.subreddit.return_value = mock_subreddit
            mock_reddit.return_value = mock_reddit_instance

            with patch.object(RetrievalAgent, "_initialize_reddit_client"):
                agent = RetrievalAgent()
                agent._reddit_client = mock_reddit_instance  # Set mock client directly

                result = await agent.execute_skill(
                    "fetch_subreddit_info",
                    {"subreddit_name": "test"},
                )

            assert result["skill"] == "fetch_subreddit_info"
            assert result["status"] == "success"
            assert result["result"]["subreddit_name"] == "test"
            assert result["result"]["info"]["name"] == "test"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiting is applied correctly."""
        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit"):
            agent = RetrievalAgent()

            # Set a very low rate limit for testing
            agent._min_request_interval = 0.1  # 100ms between requests

            start_time = datetime.now(UTC)
            agent._ensure_rate_limit()
            agent._ensure_rate_limit()  # Should sleep
            end_time = datetime.now(UTC)

            # Should have taken at least the minimum interval
            elapsed = (end_time - start_time).total_seconds()
            assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_reddit_api_exception_handling(self):
        """Test handling of Reddit API exceptions."""
        with patch("reddit_watcher.agents.retrieval_agent.praw.Reddit") as mock_reddit:
            mock_reddit_instance = MagicMock()
            mock_reddit_instance.read_only = True
            mock_subreddit = MagicMock()
            mock_subreddit.search.side_effect = RedditAPIException(
                ["SUBREDDIT_REQUIRED", "Please include a subreddit", ""]
            )
            mock_reddit_instance.subreddit.return_value = mock_subreddit
            mock_reddit.return_value = mock_reddit_instance

            agent = RetrievalAgent()
            result = await agent.execute_skill(
                "fetch_posts_by_topic",
                {"topic": "Claude Code"},
            )

            assert result["skill"] == "fetch_posts_by_topic"
            assert result["status"] == "error"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_skill_execution(self):
        """Test executing unknown skill raises error."""
        agent = RetrievalAgent()

        with pytest.raises(ValueError, match="Unknown skill"):
            await agent.execute_skill("unknown_skill", {})

    def test_extract_post_data(self):
        """Test extraction of post data from PRAW submission."""
        mock_submission = MagicMock()
        mock_submission.id = "test123"
        mock_submission.title = "Test Post"
        mock_submission.selftext = "Test content"
        mock_submission.is_self = True
        mock_submission.url = "https://reddit.com/r/test/test123"
        mock_submission.author = "testuser"
        mock_submission.subreddit = "test"
        mock_submission.created_utc = 1640995200
        mock_submission.score = 42
        mock_submission.upvote_ratio = 0.95
        mock_submission.num_comments = 5
        mock_submission.is_video = False
        mock_submission.over_18 = False
        mock_submission.permalink = "/r/test/comments/test123/"

        agent = RetrievalAgent()
        post_data = agent._extract_post_data(mock_submission)

        assert post_data["post_id"] == "test123"
        assert post_data["title"] == "Test Post"
        assert post_data["content"] == "Test content"
        assert post_data["author"] == "testuser"
        assert post_data["subreddit"] == "test"
        assert post_data["score"] == 42

    def test_extract_comment_data(self):
        """Test extraction of comment data from PRAW comment."""
        mock_comment = MagicMock()
        mock_comment.id = "comment123"
        mock_comment.body = "Test comment"
        mock_comment.author = "commenter"
        mock_comment.created_utc = 1640995200
        mock_comment.score = 10
        mock_comment.parent_id = "t3_test123"
        mock_comment.permalink = "/r/test/comments/test123/comment123/"
        mock_comment.is_submitter = False

        agent = RetrievalAgent()
        comment_data = agent._extract_comment_data(mock_comment, "test123")

        assert comment_data["comment_id"] == "comment123"
        assert comment_data["post_id"] == "test123"
        assert comment_data["body"] == "Test comment"
        assert comment_data["author"] == "commenter"
        assert comment_data["score"] == 10

    def test_extract_subreddit_data(self):
        """Test extraction of subreddit data from PRAW subreddit."""
        mock_subreddit = MagicMock()
        mock_subreddit.display_name = "test"
        mock_subreddit.title = "Test Subreddit"
        mock_subreddit.public_description = "A test subreddit"
        mock_subreddit.subscribers = 500
        mock_subreddit.created_utc = 1640995200
        mock_subreddit.over18 = False
        mock_subreddit.lang = "en"

        agent = RetrievalAgent()
        subreddit_data = agent._extract_subreddit_data(mock_subreddit)

        assert subreddit_data["name"] == "test"
        assert subreddit_data["title"] == "Test Subreddit"
        assert subreddit_data["description"] == "A test subreddit"
        assert subreddit_data["subscribers"] == 500
        assert subreddit_data["over_18"] is False

    def test_get_health_status(self):
        """Test detailed health status retrieval."""
        agent = RetrievalAgent()
        health = agent.get_health_status()

        assert "retrieval_specific" in health
        retrieval_health = health["retrieval_specific"]

        assert "reddit_client_initialized" in retrieval_health
        assert "reddit_credentials" in retrieval_health
        assert "rate_limit_rpm" in retrieval_health
        assert "min_request_interval" in retrieval_health
