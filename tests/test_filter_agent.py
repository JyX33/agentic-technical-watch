# ABOUTME: Tests for FilterAgent content relevance assessment functionality
# ABOUTME: Validates keyword matching, semantic similarity, A2A skills, and database integration

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.config import reset_settings
from reddit_watcher.models import RedditComment, RedditPost


class TestFilterAgent:
    """Test cases for FilterAgent."""

    def setup_method(self):
        """Set up test environment."""
        reset_settings()

    def teardown_method(self):
        """Clean up after tests."""
        reset_settings()

    def test_agent_initialization(self):
        """Test FilterAgent initialization."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            assert agent.agent_type == "filter"
            assert agent.name == "Content Filter Agent"
            assert "relevance" in agent.description
            assert agent.version == "1.0.0"
            assert agent.settings is not None

    def test_agent_skills(self):
        """Test agent skills definition."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            skills = agent.get_skills()

            assert len(skills) == 5
            skill_names = [skill.name for skill in skills]
            assert "health_check" in skill_names
            assert "filter_content_by_keywords" in skill_names
            assert "filter_content_by_semantic_similarity" in skill_names
            assert "batch_filter_posts" in skill_names
            assert "batch_filter_comments" in skill_names

    def test_agent_card_generation(self):
        """Test Agent Card generation includes filter skills."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent_card = agent.generate_agent_card()

            assert agent_card.name == agent.name
            assert agent_card.description == agent.description
            assert len(agent_card.skills) == 5

            # Check for filter-specific skills
            skill_names = [skill.name for skill in agent_card.skills]
            assert "filter_content_by_keywords" in skill_names
            assert "filter_content_by_semantic_similarity" in skill_names

    @pytest.mark.asyncio
    async def test_health_check_without_semantic_model(self):
        """Test health check when semantic model is not initialized."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = None

            result = await agent.execute_skill("health_check", {})

            assert result["skill"] == "health_check"
            assert result["status"] == "success"
            assert "filter_specific" in result["result"]

            filter_status = result["result"]["filter_specific"]
            assert filter_status["model_initialized"] is False
            assert filter_status["model_status"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_health_check_with_semantic_model(self):
        """Test health check with semantic model initialized."""
        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = mock_model

            result = await agent.execute_skill("health_check", {})

            assert result["skill"] == "health_check"
            assert result["status"] == "success"

            filter_status = result["result"]["filter_specific"]
            assert filter_status["model_initialized"] is True
            assert filter_status["model_status"] == "operational"
            assert filter_status["embedding_dimension"] == 3

    def test_keyword_matching_exact_match(self):
        """Test keyword matching with exact matches."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            text = "This is about Claude Code and AI programming"
            topics = ["Claude Code", "Python", "AI"]

            result = agent._match_keywords(text, topics)

            assert "Claude Code" in result["matched_keywords"]
            assert "AI" in result["matched_keywords"]
            assert "Python" not in result["matched_keywords"]
            assert result["match_score"] > 0
            assert result["total_matches"] > 0

    def test_keyword_matching_partial_words(self):
        """Test keyword matching with partial word matches."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            text = "I love using Claude for programming tasks"
            topics = ["Claude Code", "Programming Tools"]

            result = agent._match_keywords(text, topics)

            # Should match partial words from "Claude Code"
            assert len(result["matched_keywords"]) > 0
            assert result["match_score"] > 0

    def test_keyword_matching_case_insensitive(self):
        """Test that keyword matching is case insensitive."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            text = "CLAUDE CODE is amazing for development"
            topics = ["claude code", "development"]

            result = agent._match_keywords(text, topics)

            assert "claude code" in result["matched_keywords"]
            assert "development" in result["matched_keywords"]

    def test_find_positions(self):
        """Test position finding utility method."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            text = "the quick brown fox jumps over the lazy dog"
            pattern = "the"

            positions = agent._find_positions(text, pattern)

            assert len(positions) == 2
            assert 0 in positions  # First "the"
            assert 31 in positions  # Second "the"

    @pytest.mark.asyncio
    async def test_filter_content_by_keywords_success(self):
        """Test successful keyword-based content filtering."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            result = await agent.execute_skill(
                "filter_content_by_keywords",
                {
                    "title": "Claude Code Tutorial",
                    "content": "Learn how to use Claude Code for AI development",
                    "topics": ["Claude Code", "AI development"],
                },
            )

            assert result["skill"] == "filter_content_by_keywords"
            assert result["status"] == "success"
            assert result["result"]["is_relevant"] is True
            assert "Claude Code" in result["result"]["keywords_matched"]

    @pytest.mark.asyncio
    async def test_filter_content_by_keywords_no_content(self):
        """Test keyword filtering with missing content."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            result = await agent.execute_skill(
                "filter_content_by_keywords", {"topics": ["Claude Code"]}
            )

            assert result["skill"] == "filter_content_by_keywords"
            assert result["status"] == "error"
            assert "required" in result["error"]

    @pytest.mark.asyncio
    async def test_filter_content_by_semantic_similarity_no_model(self):
        """Test semantic filtering when model is not initialized."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = None

            result = await agent.execute_skill(
                "filter_content_by_semantic_similarity",
                {
                    "title": "Test Title",
                    "content": "Test content",
                },
            )

            assert result["skill"] == "filter_content_by_semantic_similarity"
            assert result["status"] == "error"
            assert "not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_filter_content_by_semantic_similarity_success(self):
        """Test successful semantic similarity filtering."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = [
            np.array([[0.1, 0.2, 0.3]]),  # Text embedding (1, 3)
            np.array([[0.2, 0.3, 0.4]]),  # Topic embedding 1 (1, 3)
            np.array([[0.1, 0.1, 0.1]]),  # Topic embedding 2 (1, 3)
        ]

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = mock_model

            result = await agent.execute_skill(
                "filter_content_by_semantic_similarity",
                {
                    "title": "AI Development",
                    "content": "Building applications with AI",
                    "topics": ["AI Programming", "Web Development"],
                },
            )

            assert result["skill"] == "filter_content_by_semantic_similarity"
            assert result["status"] == "success"
            assert "max_similarity" in result["result"]
            assert "topic_similarities" in result["result"]

    def test_compute_semantic_similarity(self):
        """Test semantic similarity computation."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = [
            np.array([[0.8, 0.6, 0.0]]),  # Text embedding (1, 3)
            np.array([[0.6, 0.8, 0.0]]),  # First topic embedding (1, 3)
            np.array([[0.0, 0.0, 1.0]]),  # Second topic embedding (1, 3)
        ]

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = mock_model

            result = agent._compute_semantic_similarity(
                "Test text", ["similar topic", "different topic"]
            )

            assert "max_similarity" in result
            assert "best_topic" in result
            assert "topic_similarities" in result
            assert len(result["topic_similarities"]) == 2

    @pytest.mark.asyncio
    async def test_batch_filter_posts_no_ids(self):
        """Test batch post filtering with no post IDs."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            result = await agent.execute_skill("batch_filter_posts", {})

            assert result["skill"] == "batch_filter_posts"
            assert result["status"] == "error"
            assert "required" in result["error"]

    @pytest.mark.asyncio
    async def test_batch_filter_posts_success(self):
        """Test successful batch post filtering."""
        mock_post = MagicMock(spec=RedditPost)
        mock_post.id = 1
        mock_post.post_id = "test123"
        mock_post.title = "Claude Code Tutorial"
        mock_post.content = "Learn AI development"

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_post,  # Post found
            None,  # No existing filter
        ]

        with (
            patch.object(FilterAgent, "_initialize_semantic_model"),
            patch(
                "reddit_watcher.agents.filter_agent.get_db_session"
            ) as mock_db_session,
        ):
            mock_db_session.return_value.__enter__.return_value = mock_session
            agent = FilterAgent()

            result = await agent.execute_skill(
                "batch_filter_posts",
                {
                    "post_ids": ["test123"],
                    "topics": ["Claude Code"],
                    "use_semantic": False,
                },
            )

            assert result["skill"] == "batch_filter_posts"
            assert result["status"] == "success"
            assert result["result"]["total_posts"] == 1
            assert result["result"]["processed"] == 1

    @pytest.mark.asyncio
    async def test_batch_filter_comments_success(self):
        """Test successful batch comment filtering."""
        mock_comment = MagicMock(spec=RedditComment)
        mock_comment.id = 1
        mock_comment.comment_id = "comment123"
        mock_comment.body = "Claude Code is great for AI development"

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_comment,  # Comment found
            None,  # No existing filter
        ]

        with (
            patch.object(FilterAgent, "_initialize_semantic_model"),
            patch(
                "reddit_watcher.agents.filter_agent.get_db_session"
            ) as mock_db_session,
        ):
            mock_db_session.return_value.__enter__.return_value = mock_session
            agent = FilterAgent()

            result = await agent.execute_skill(
                "batch_filter_comments",
                {
                    "comment_ids": ["comment123"],
                    "topics": ["Claude Code"],
                    "use_semantic": False,
                },
            )

            assert result["skill"] == "batch_filter_comments"
            assert result["status"] == "success"
            assert result["result"]["total_comments"] == 1
            assert result["result"]["processed"] == 1

    @pytest.mark.asyncio
    async def test_process_single_post(self):
        """Test processing a single post for filtering."""
        mock_post = MagicMock(spec=RedditPost)
        mock_post.post_id = "test123"
        mock_post.title = "Claude Code Tutorial"
        mock_post.content = "Learn AI development with Claude"

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = None  # Disable semantic for this test

            result = await agent._process_single_post(
                mock_post, ["Claude Code"], use_semantic=False
            )

            assert "relevance_score" in result
            assert "is_relevant" in result
            assert "keywords_matched" in result
            assert "filter_reason" in result
            assert "Claude Code" in result["keywords_matched"]

    @pytest.mark.asyncio
    async def test_process_single_comment(self):
        """Test processing a single comment for filtering."""
        mock_comment = MagicMock(spec=RedditComment)
        mock_comment.comment_id = "comment123"
        mock_comment.body = "I love using Claude Code for AI projects"

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = None  # Disable semantic for this test

            result = await agent._process_single_comment(
                mock_comment, ["Claude Code"], use_semantic=False
            )

            assert "relevance_score" in result
            assert "is_relevant" in result
            assert "keywords_matched" in result
            assert "filter_reason" in result
            assert "Claude Code" in result["keywords_matched"]

    @pytest.mark.asyncio
    async def test_unknown_skill_execution(self):
        """Test executing unknown skill raises error."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()

            with pytest.raises(ValueError, match="Unknown skill"):
                await agent.execute_skill("unknown_skill", {})

    def test_get_health_status_with_model(self):
        """Test detailed health status with semantic model."""
        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = mock_model

            health = agent.get_health_status()

            assert "filter_specific" in health
            filter_health = health["filter_specific"]

            assert filter_health["semantic_model_initialized"] is True
            assert filter_health["model_status"] == "operational"
            assert filter_health["embedding_dimension"] == 3

    def test_get_health_status_without_model(self):
        """Test detailed health status without semantic model."""
        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = None

            health = agent.get_health_status()

            assert "filter_specific" in health
            filter_health = health["filter_specific"]

            assert filter_health["semantic_model_initialized"] is False
            assert filter_health["model_status"] == "not_initialized"

    def test_semantic_model_initialization_success(self):
        """Test successful semantic model initialization."""
        mock_transformer = MagicMock()

        with patch("reddit_watcher.agents.filter_agent.SentenceTransformer") as mock_st:
            mock_st.return_value = mock_transformer

            agent = FilterAgent()

            assert agent._semantic_model is mock_transformer
            mock_st.assert_called_once_with("all-MiniLM-L6-v2")

    def test_semantic_model_initialization_failure(self):
        """Test semantic model initialization failure handling."""
        with patch("reddit_watcher.agents.filter_agent.SentenceTransformer") as mock_st:
            mock_st.side_effect = Exception("Model load failed")

            agent = FilterAgent()

            assert agent._semantic_model is None

    def test_topic_embedding_caching(self):
        """Test that topic embeddings are cached properly."""

        def mock_encode_func(input_list):
            # Return different embeddings based on input
            if input_list == ["test text"]:
                return np.array([[0.1, 0.2, 0.3]])
            elif input_list == ["topic1"]:
                return np.array([[0.4, 0.5, 0.6]])
            elif input_list == ["topic2"]:
                return np.array([[0.7, 0.8, 0.9]])
            elif input_list == ["another test"]:
                return np.array([[0.2, 0.3, 0.4]])
            else:
                return np.array([[0.1, 0.1, 0.1]])  # Default

        mock_model = MagicMock()
        mock_model.encode.side_effect = mock_encode_func

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = mock_model

            # First computation should cache embeddings
            agent._compute_semantic_similarity("test text", ["topic1", "topic2"])

            # Verify embeddings are cached
            assert "topic1" in agent._topic_embeddings
            assert "topic2" in agent._topic_embeddings

            # Get call count after first computation
            first_call_count = mock_model.encode.call_count

            # Second computation should use cached embeddings (only encode new text)
            agent._compute_semantic_similarity("another test", ["topic1", "topic2"])

            # Should have made only 1 additional call (for the new text)
            assert mock_model.encode.call_count == first_call_count + 1

    @pytest.mark.asyncio
    async def test_relevance_score_combination(self):
        """Test that relevance scores are properly combined."""
        mock_post = MagicMock(spec=RedditPost)
        mock_post.post_id = "test123"
        mock_post.title = "Claude Code"  # High keyword match
        mock_post.content = "Tutorial content"

        mock_model = MagicMock()
        # Mock with higher similarity to ensure high relevance score
        mock_model.encode.side_effect = [
            np.array([[1.0, 0.0, 0.0]]),  # Text embedding (1, 3)
            np.array([[1.0, 0.0, 0.0]]),  # Topic embedding (1, 3) - perfect similarity
        ]

        with patch.object(FilterAgent, "_initialize_semantic_model"):
            agent = FilterAgent()
            agent._semantic_model = mock_model
            # Override the relevance threshold for this test
            agent.settings.relevance_threshold = 0.5

            result = await agent._process_single_post(
                mock_post, ["Claude Code"], use_semantic=True
            )

            # Should combine keyword (high) and semantic (high) scores
            assert result["relevance_score"] > 0.5  # Actual score is ~0.58
            assert (
                result["is_relevant"] is True
            )  # Should be relevant with lower threshold
            assert "Claude Code" in result["keywords_matched"]
            assert result["semantic_similarity"] > 0.5
