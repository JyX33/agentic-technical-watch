# Tests for A2A base agent functionality
import json
from unittest.mock import patch

import pytest

from reddit_watcher.agents.base import (
    BaseA2AAgentExecutor,
    RedditSkillParameters,
)
from reddit_watcher.agents.test_agent import MockA2AAgent
from reddit_watcher.config import create_config, reset_settings
from tests.test_utils import create_test_context, create_test_event_queue


class TestBaseA2AAgent:
    """Test cases for BaseA2AAgent abstract class."""

    def setup_method(self):
        """Set up test environment."""
        reset_settings()

    def teardown_method(self):
        """Clean up after tests."""
        reset_settings()

    def test_agent_initialization(self):
        """Test basic agent initialization."""
        config = create_config()
        agent = MockA2AAgent(config)

        assert agent.agent_type == "test"
        assert agent.name == "Test A2A Agent"
        assert (
            agent.description == "Test agent for validating A2A protocol implementation"
        )
        assert agent.version == "1.0.0"
        assert agent.config is not None

    def test_agent_skills(self):
        """Test agent skills definition."""
        config = create_config()
        agent = MockA2AAgent(config)
        skills = agent.get_skills()

        assert len(skills) == 3
        skill_names = [skill.name for skill in skills]
        assert "health_check" in skill_names
        assert "echo" in skill_names
        assert "reddit_topics" in skill_names

    def test_agent_card_generation(self):
        """Test Agent Card generation."""
        config = create_config()
        agent = MockA2AAgent(config)
        agent_card = agent.generate_agent_card()

        assert agent_card.name == agent.name
        assert agent_card.description == agent.description
        assert agent_card.version == agent.version
        assert agent_card.provider is not None
        assert agent_card.capabilities is not None
        assert len(agent_card.skills) == 3

    def test_agent_card_json(self):
        """Test Agent Card JSON serialization."""
        config = create_config()
        agent = MockA2AAgent(config)
        agent_card_json = agent.get_agent_card_json()

        # Should be valid JSON
        agent_card_dict = json.loads(agent_card_json)
        assert agent_card_dict["name"] == agent.name
        assert agent_card_dict["description"] == agent.description
        assert "skills" in agent_card_dict
        assert len(agent_card_dict["skills"]) == 3

    def test_common_health_status(self):
        """Test common health status."""
        config = create_config()
        agent = MockA2AAgent(config)
        health = agent.get_common_health_status()

        assert health["agent_type"] == "test"
        assert health["name"] == agent.name
        assert health["version"] == agent.version
        assert health["status"] == "healthy"
        assert "settings" in health

    def test_agent_with_security_schemes(self):
        """Test agent with security schemes configured."""
        with patch.dict(
            "os.environ",
            {"A2A_API_KEY": "test-api-key", "A2A_BEARER_TOKEN": "test-bearer-token"},
        ):
            reset_settings()
            config = create_config()
            agent = MockA2AAgent(config)
            agent_card = agent.generate_agent_card()

            # Should have security schemes
            assert agent_card.securitySchemes is not None
            assert len(agent_card.securitySchemes) == 2

            # Check security scheme types
            scheme_types = [scheme.type for scheme in agent_card.securitySchemes]
            assert "apiKey" in scheme_types
            assert "http" in scheme_types

    @pytest.mark.asyncio
    async def test_execute_health_check_skill(self):
        """Test executing health check skill."""
        config = create_config()
        agent = MockA2AAgent(config)
        result = await agent.execute_skill("health_check", {})

        assert result["skill"] == "health_check"
        assert result["status"] == "success"
        assert "result" in result
        assert result["result"]["agent_type"] == "test"

    @pytest.mark.asyncio
    async def test_execute_echo_skill(self):
        """Test executing echo skill."""
        config = create_config()
        agent = MockA2AAgent(config)
        test_message = "Hello, A2A!"
        result = await agent.execute_skill("echo", {"message": test_message})

        assert result["skill"] == "echo"
        assert result["status"] == "success"
        assert result["result"]["original_message"] == test_message
        assert result["result"]["agent_type"] == "test"
        assert result["result"]["message_length"] == len(test_message)

    @pytest.mark.asyncio
    async def test_execute_reddit_topics_skill(self):
        """Test executing reddit topics skill."""
        config = create_config()
        agent = MockA2AAgent(config)
        result = await agent.execute_skill("reddit_topics", {})

        assert result["skill"] == "reddit_topics"
        assert result["status"] == "success"
        assert "topics" in result["result"]
        assert isinstance(result["result"]["topics"], list)

    @pytest.mark.asyncio
    async def test_execute_unknown_skill(self):
        """Test executing unknown skill raises error."""
        config = create_config()
        agent = MockA2AAgent(config)

        with pytest.raises(ValueError, match="Unknown skill"):
            await agent.execute_skill("unknown_skill", {})


class TestBaseA2AAgentExecutor:
    """Test cases for BaseA2AAgentExecutor."""

    def setup_method(self):
        """Set up test environment."""
        reset_settings()

    def teardown_method(self):
        """Clean up after tests."""
        reset_settings()

    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """Test executor initialization."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        assert executor.agent == agent
        assert executor.logger is not None

    @pytest.mark.asyncio
    async def test_execute_with_json_message(self):
        """Test executor with JSON message."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        # Create test context and event queue
        context = create_test_context(
            message=json.dumps({"skill": "health_check", "parameters": {}})
        )
        event_queue = create_test_event_queue()

        await executor.execute(context, event_queue)

        # Should have enqueued an event
        event_queue.assert_event_enqueued()

        # Check the event content
        events = event_queue.get_events()
        assert len(events) == 1
        assert events[0]["type"] == "agent_message"

    @pytest.mark.asyncio
    async def test_execute_with_text_message(self):
        """Test executor with text message."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        # Create test context and event queue
        context = create_test_context(message="Hello, test agent!")
        event_queue = create_test_event_queue()

        await executor.execute(context, event_queue)

        # Should have enqueued an event (health check fallback)
        event_queue.assert_event_enqueued()

        # Verify it executed health_check as fallback
        events = event_queue.get_events()
        assert len(events) == 1
        event_content = json.loads(events[0]["content"])
        assert event_content["skill"] == "health_check"

    @pytest.mark.asyncio
    async def test_execute_with_no_message(self):
        """Test executor with no message."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        # Create test context with no message
        context = create_test_context(message=None)
        event_queue = create_test_event_queue()

        await executor.execute(context, event_queue)

        # Should have enqueued an error event
        event_queue.assert_event_enqueued("No message provided")

    @pytest.mark.asyncio
    async def test_execute_with_no_skill(self):
        """Test executor with message but no skill."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        # Create test context with message but no skill
        context = create_test_context(
            message=json.dumps({"parameters": {}})  # No skill field
        )
        event_queue = create_test_event_queue()

        await executor.execute(context, event_queue)

        # Should have enqueued an error event
        event_queue.assert_event_enqueued("No skill specified")

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test task cancellation."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        # Create test context and event queue
        context = create_test_context(message="cancel")
        event_queue = create_test_event_queue()

        await executor.cancel(context, event_queue)

        # Should have enqueued a cancellation event
        event_queue.assert_event_enqueued("cancelled")

    def test_parse_json_request(self):
        """Test parsing JSON request."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        json_message = json.dumps({"skill": "echo", "parameters": {"message": "test"}})
        result = executor._parse_request(json_message)

        assert result["skill"] == "echo"
        assert result["parameters"]["message"] == "test"

    def test_parse_text_request(self):
        """Test parsing text request."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        text_message = "Hello, agent!"
        result = executor._parse_request(text_message)

        assert result["skill"] == "health_check"
        assert result["parameters"]["message"] == text_message

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        config = create_config()
        agent = MockA2AAgent(config)
        executor = BaseA2AAgentExecutor(agent)

        invalid_json = '{"skill": "echo", "parameters":'  # Incomplete JSON
        result = executor._parse_request(invalid_json)

        # Should fallback to health check
        assert result["skill"] == "health_check"
        assert result["parameters"]["message"] == invalid_json


class TestRedditSkillParameters:
    """Test cases for RedditSkillParameters helper class."""

    def test_topic_parameter(self):
        """Test topic parameter creation."""
        param = RedditSkillParameters.topic_parameter()

        assert param["name"] == "topic"
        assert param["type"] == "string"
        assert param["description"] is not None
        assert param["required"] is True

    def test_subreddit_parameter(self):
        """Test subreddit parameter creation."""
        param = RedditSkillParameters.subreddit_parameter()

        assert param["name"] == "subreddit"
        assert param["type"] == "string"
        assert param["description"] is not None
        assert param["required"] is False

    def test_limit_parameter(self):
        """Test limit parameter creation."""
        param = RedditSkillParameters.limit_parameter()

        assert param["name"] == "limit"
        assert param["type"] == "integer"
        assert param["description"] is not None
        assert param["required"] is False

    def test_time_range_parameter(self):
        """Test time range parameter creation."""
        param = RedditSkillParameters.time_range_parameter()

        assert param["name"] == "time_range"
        assert param["type"] == "string"
        assert param["description"] is not None
        assert param["required"] is False
