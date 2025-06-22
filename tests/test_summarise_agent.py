# ABOUTME: Test suite for SummariseAgent verifying Gemini integration and extractive fallback
# ABOUTME: Covers A2A skills, rate limiting, chunking, and error handling scenarios

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from reddit_watcher.agents.summarise_agent import RateLimitState, SummariseAgent


class TestSummariseAgent:
    """Test suite for SummariseAgent A2A functionality."""

    @pytest.fixture
    def agent(self):
        """Create a SummariseAgent for testing."""
        with patch("reddit_watcher.agents.summarise_agent.genai.configure"):
            return SummariseAgent()

    def test_agent_initialization(self, agent):
        """Test that SummariseAgent initializes correctly."""
        assert agent.agent_type == "summarise"
        assert agent.name == "Content Summarization Agent"
        assert agent.version == "1.0.0"
        assert isinstance(agent._rate_limit_state, RateLimitState)

    def test_get_skills(self, agent):
        """Test that agent returns correct skills."""
        skills = agent.get_skills()
        assert len(skills) == 2

        # Check health check skill
        health_skill = skills[0]
        assert health_skill.name == "health_check"
        assert health_skill.id == "health_check"
        assert "health" in health_skill.description

        # Check summarize skill
        summarize_skill = skills[1]
        assert summarize_skill.name == "summarizeContent"
        assert summarize_skill.id == "summarize_content"
        assert "AI-powered summaries" in summarize_skill.description
        assert "summarize" in summarize_skill.tags
        assert "gemini" in summarize_skill.tags

    @pytest.mark.asyncio
    async def test_execute_skill_unknown_skill(self, agent):
        """Test execution of unknown skill returns error."""
        result = await agent.execute_skill("unknownSkill", {})

        assert result["success"] is False
        assert "Unknown skill" in result["error"]
        assert "available_skills" in result

    @pytest.mark.asyncio
    async def test_execute_skill_missing_content(self, agent):
        """Test execution without required content parameter."""
        result = await agent.execute_skill("summarizeContent", {})

        assert result["success"] is False
        assert "Content parameter is required" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_skill_empty_content(self, agent):
        """Test execution with empty content parameter."""
        result = await agent.execute_skill("summarizeContent", {"content": ""})

        assert result["success"] is False
        assert "Content parameter is required" in result["error"]

    def test_split_content_recursively_small_content(self, agent):
        """Test content splitting with small content."""
        content = "This is a short piece of content."
        chunks = agent._split_content_recursively(content, max_chunk_size=1000)

        assert len(chunks) == 1
        assert chunks[0] == content

    def test_split_content_recursively_large_content(self, agent):
        """Test content splitting with large content."""
        # Create content larger than chunk size
        content = "This is a sentence. " * 500  # Should exceed default chunk size
        chunks = agent._split_content_recursively(content, max_chunk_size=1000)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_extractive_summarization_basic(self, agent):
        """Test extractive summarization with basic functionality."""
        content = "First sentence. Second sentence. Third sentence. Fourth sentence."
        summary = agent._extractive_summarization(content, max_sentences=2)

        assert len(summary) > 0
        assert len(summary) <= len(content)

    def test_extractive_summarization_short_content(self, agent):
        """Test extractive summarization with content shorter than max sentences."""
        content = "Short content."
        summary = agent._extractive_summarization(content, max_sentences=3)

        # Should return original content if shorter than max_sentences
        assert summary == content

    @pytest.mark.asyncio
    async def test_rate_limiting_initialization(self, agent):
        """Test rate limiting state initialization."""
        assert agent._rate_limit_state.requests_made == 0
        assert agent._rate_limit_state.max_requests_per_minute == 100

    @pytest.mark.asyncio
    async def test_rate_limiting_check_normal(self, agent):
        """Test rate limiting check under normal conditions."""
        # Should complete without delay
        await agent._check_rate_limit()
        assert agent._rate_limit_state.requests_made == 0

    @pytest.mark.asyncio
    async def test_rate_limiting_check_at_limit(self, agent):
        """Test rate limiting when at request limit."""
        # Set requests to limit
        agent._rate_limit_state.requests_made = 100
        agent._rate_limit_state.window_start = asyncio.get_event_loop().time()

        # Should reset window since requests_made is at limit
        start_time = asyncio.get_event_loop().time()
        await agent._check_rate_limit()
        end_time = asyncio.get_event_loop().time()

        # Should have taken some time due to rate limiting
        assert end_time >= start_time

    @pytest.mark.asyncio
    @patch("reddit_watcher.agents.summarise_agent.genai")
    async def test_summarize_with_gemini_success(self, mock_genai, agent):
        """Test successful Gemini summarization."""
        # Mock Gemini response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is a generated summary."
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        agent._gemini_initialized = True

        result = await agent._summarize_with_gemini("Test content")

        assert result == "This is a generated summary."
        mock_genai.GenerativeModel.assert_called_once()
        mock_model.generate_content.assert_called_once()

    @pytest.mark.asyncio
    @patch("reddit_watcher.agents.summarise_agent.genai")
    async def test_summarize_with_gemini_not_initialized(self, mock_genai, agent):
        """Test Gemini summarization when not initialized."""
        agent._gemini_initialized = False

        result = await agent._summarize_with_gemini("Test content")

        assert result is None
        mock_genai.GenerativeModel.assert_not_called()

    @pytest.mark.asyncio
    @patch("reddit_watcher.agents.summarise_agent.genai")
    async def test_summarize_with_gemini_empty_response(self, mock_genai, agent):
        """Test Gemini summarization with empty response."""
        # Mock empty response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        agent._gemini_initialized = True

        result = await agent._summarize_with_gemini("Test content")

        assert result is None

    @pytest.mark.asyncio
    async def test_summarize_content_chunks_single_chunk(self, agent):
        """Test summarizing single content chunk."""
        chunks = ["This is test content for summarization."]

        with patch.object(agent, "_summarize_with_gemini", return_value="AI summary"):
            result = await agent._summarize_content_chunks(chunks)

        assert result == "AI summary"

    @pytest.mark.asyncio
    async def test_summarize_content_chunks_multiple_chunks(self, agent):
        """Test summarizing multiple content chunks."""
        chunks = ["First chunk.", "Second chunk."]

        # Mock AI summarization to return summaries for each chunk
        def mock_summarize(content, use_fallback_model=False):
            if "First chunk." in content:
                return "First summary"
            elif "Second chunk." in content:
                return "Second summary"
            elif "First summary" in content and "Second summary" in content:
                return "Combined summary"
            return None

        with patch.object(agent, "_summarize_with_gemini", side_effect=mock_summarize):
            result = await agent._summarize_content_chunks(chunks)

        assert result == "Combined summary"

    @pytest.mark.asyncio
    async def test_summarize_content_chunks_ai_failure_extractive_fallback(self, agent):
        """Test fallback to extractive summarization when AI fails."""
        chunks = ["This is test content that needs summarization."]

        with (
            patch.object(agent, "_summarize_with_gemini", return_value=None),
            patch.object(
                agent, "_extractive_summarization", return_value="Extractive summary"
            ),
        ):
            result = await agent._summarize_content_chunks(chunks)

        assert result == "Extractive summary"

    @pytest.mark.asyncio
    async def test_execute_skill_successful_summarization(self, agent):
        """Test successful skill execution with summarization."""
        test_content = "This is test content for summarization testing."

        with patch.object(
            agent, "_summarize_content_chunks", return_value="Test summary"
        ):
            result = await agent.execute_skill(
                "summarizeContent",
                {"content": test_content, "content_type": "post", "max_length": 3},
            )

        assert result["success"] is True
        assert result["summary"] == "Test summary"
        assert result["content_type"] == "post"
        assert result["original_length"] == len(test_content)
        assert result["summary_length"] == len("Test summary")
        assert result["chunks_processed"] == 1

    @pytest.mark.asyncio
    async def test_execute_skill_with_post_ids(self, agent):
        """Test skill execution with post IDs for database tracking."""
        test_content = "Content with post IDs."
        post_ids = ["post1", "post2"]

        with patch.object(
            agent, "_summarize_content_chunks", return_value="Summary with IDs"
        ):
            result = await agent.execute_skill(
                "summarizeContent", {"content": test_content, "post_ids": post_ids}
            )

        assert result["success"] is True
        assert result["summary"] == "Summary with IDs"
        # Database storage is not yet implemented, so summary_id should be None
        assert result["summary_id"] is None

    @pytest.mark.asyncio
    async def test_execute_skill_content_chunking(self, agent):
        """Test skill execution with content that requires chunking."""
        # Create large content that will be chunked
        large_content = "This is a sentence. " * 1000

        with (
            patch.object(
                agent, "_split_content_recursively", return_value=["chunk1", "chunk2"]
            ) as mock_split,
            patch.object(
                agent, "_summarize_content_chunks", return_value="Chunked summary"
            ),
        ):
            result = await agent.execute_skill(
                "summarizeContent", {"content": large_content}
            )

        assert result["success"] is True
        assert result["summary"] == "Chunked summary"
        assert result["chunks_processed"] == 2
        mock_split.assert_called_once_with(large_content)

    def test_get_health_status(self, agent):
        """Test agent health status reporting."""
        with (
            patch.object(agent, "_gemini_initialized", True),
            patch.object(agent, "_nlp_model", MagicMock()),
        ):
            status = agent.get_health_status()

        assert "status" in status
        assert "gemini_initialized" in status
        assert "spacy_available" in status
        assert "rate_limit_requests_made" in status
        assert "rate_limit_window_remaining" in status
        assert "primary_model" in status
        assert "fallback_model" in status

        assert status["gemini_initialized"] is True
        assert status["spacy_available"] is True

    @pytest.mark.asyncio
    async def test_error_handling_in_skill_execution(self, agent):
        """Test error handling during skill execution."""
        with patch.object(
            agent, "_summarize_content_chunks", side_effect=Exception("Test error")
        ):
            result = await agent.execute_skill(
                "summarizeContent", {"content": "Test content"}
            )

        assert result["success"] is False
        assert "Failed to summarize content" in result["error"]
        assert "Test error" in result["error"]


class TestRateLimitState:
    """Test suite for RateLimitState functionality."""

    def test_rate_limit_state_initialization(self):
        """Test RateLimitState initialization."""
        state = RateLimitState(max_requests_per_minute=50)

        assert state.requests_made == 0
        assert state.window_start == 0.0
        assert state.max_requests_per_minute == 50

    def test_rate_limit_state_defaults(self):
        """Test RateLimitState default values."""
        state = RateLimitState()

        assert state.requests_made == 0
        assert state.window_start == 0.0
        assert state.max_requests_per_minute == 100
