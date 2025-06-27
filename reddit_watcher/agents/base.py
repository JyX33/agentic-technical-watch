# ABOUTME: Base A2A Agent class implementing Google's Agent-to-Agent protocol
# ABOUTME: Provides abstract base class for all Reddit monitoring agents with Agent Card generation

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Protocol

from reddit_watcher.a2a_protocol import (
    AgentCapabilities,
    AgentCard,
    AgentExecutor,
    AgentProvider,
    AgentSkill,
    APIKeySecurityScheme,
    EventQueue,
    HTTPAuthSecurityScheme,
    In,
    RequestContext,
    new_agent_text_message,
)
from reddit_watcher.observability.health import create_health_monitor
from reddit_watcher.observability.logging import get_logger
from reddit_watcher.observability.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class ConfigProvider(Protocol):
    """
    Protocol for configuration providers.

    This allows dependency injection of configuration objects without
    tight coupling to the Settings class implementation.
    """

    @property
    def a2a_port(self) -> int: ...

    @property
    def a2a_host(self) -> str: ...

    @property
    def a2a_api_key(self) -> str: ...

    @property
    def a2a_bearer_token(self) -> str: ...

    @property
    def redis_url(self) -> str: ...

    @property
    def database_url(self) -> str: ...

    @property
    def processing_interval(self) -> int: ...


class BaseA2AAgent(ABC):
    """
    Abstract base class for all Reddit monitoring agents using Google's A2A protocol.

    This class provides the foundation for agent discovery, communication, and execution
    within the Reddit Technical Watcher system. Each agent must implement specific
    capabilities while maintaining A2A protocol compatibility.
    """

    def __init__(
        self,
        config: ConfigProvider,
        agent_type: str,
        name: str,
        description: str,
        version: str = "1.0.0",
    ):
        """
        Initialize the base A2A agent with dependency injection.

        Args:
            config: Configuration provider (injected dependency)
            agent_type: Type of agent (e.g., "retrieval", "filter", "summarise", "alert", "coordinator")
            name: Human-readable name of the agent
            description: Description of the agent's purpose and capabilities
            version: Agent version for compatibility tracking
        """
        self.config = config
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.version = version

        # Initialize observability components
        self.logger = get_logger(f"{__name__}.{agent_type}", agent_type)
        self.metrics = get_metrics_collector(agent_type)
        self.health_monitor = create_health_monitor(f"{agent_type}_agent", version)
        self.start_time = time.time()

    async def __aenter__(self):
        """Async context manager entry. Override in subclasses for resource initialization."""
        # Start health monitoring
        await self.health_monitor.start_monitoring()
        self.logger.info(f"Agent {self.agent_type} started and monitoring initialized")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit. Override in subclasses for resource cleanup."""
        # Stop health monitoring
        await self.health_monitor.stop_monitoring()
        await self.cleanup_resources()
        self.logger.info(f"Agent {self.agent_type} stopped and resources cleaned up")

    async def cleanup_resources(self):
        """Cleanup any resources held by this agent. Override in subclasses."""
        # Record uptime metrics before cleanup
        uptime = time.time() - self.start_time
        self.metrics.process_uptime_seconds = uptime
        # Default implementation does nothing - subclasses should override
        return

    async def get_health_status(self) -> dict[str, Any]:
        """
        Get comprehensive health status for this agent.

        Returns:
            Dictionary containing health status information
        """
        health = self.health_monitor.get_service_health()
        base_health = {
            "agent_type": self.agent_type,
            "status": health.overall_status.value,
            "uptime_seconds": time.time() - self.start_time,
            "version": self.version,
            "health_checks": health.to_dict(),
            "metrics_available": True,
        }

        # Add agent-specific health information
        try:
            agent_specific = await self.get_agent_specific_health()
            base_health.update(agent_specific)
        except Exception as e:
            base_health["agent_specific_error"] = str(e)

        return base_health

    @abstractmethod
    async def get_agent_specific_health(self) -> dict[str, Any]:
        """
        Get agent-specific health information.

        Each agent should implement this to provide specific health data
        such as API connectivity, processing queues, etc.

        Returns:
            Dictionary containing agent-specific health information
        """
        pass

    @abstractmethod
    def get_skills(self) -> list[AgentSkill]:
        """
        Define the specific skills this agent provides.

        Returns:
            List of AgentSkill objects describing agent capabilities
        """
        pass

    @abstractmethod
    async def execute_skill(
        self, skill_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a specific skill with given parameters.

        Args:
            skill_name: Name of the skill to execute
            parameters: Parameters for skill execution

        Returns:
            Dictionary containing execution results
        """
        pass

    def generate_agent_card(self) -> AgentCard:
        """
        Generate the Agent Card for service discovery.

        Returns:
            AgentCard object containing agent metadata and capabilities
        """
        # Provider information
        provider = AgentProvider(
            organization="Reddit Technical Watcher",
            url="https://github.com/reddit-technical-watcher",
        )

        # Security schemes
        security_schemes = []
        if self.config.a2a_api_key:
            security_schemes.append(
                APIKeySecurityScheme(
                    name="X-API-Key",
                    description="API key authentication",
                    in_=In.HEADER,
                )
            )

        if self.config.a2a_bearer_token:
            security_schemes.append(
                HTTPAuthSecurityScheme(
                    name="bearer_auth",
                    description="Bearer token authentication",
                    scheme="Bearer",
                )
            )

        # Capabilities - simplified for now
        capabilities = AgentCapabilities(
            input_modes=["text/plain", "application/json"],
            output_modes=["text/plain", "application/json"],
            streaming=True,
            authentication_required=bool(security_schemes),
        )

        # Create the agent card
        agent_card = AgentCard(
            name=self.name,
            description=self.description,
            version=self.version,
            provider=provider,
            url=f"http://localhost:{self.config.a2a_port}/a2a",
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=["application/json"],
            capabilities=capabilities,
            skills=self.get_skills(),
            securitySchemes=security_schemes if security_schemes else None,
        )

        return agent_card

    def get_agent_card_json(self) -> str:
        """
        Get the Agent Card as JSON string for /.well-known/agent.json endpoint.

        Returns:
            JSON string representation of the Agent Card
        """
        agent_card = self.generate_agent_card()
        return json.dumps(agent_card.model_dump(), indent=2)

    def get_common_health_status(self) -> dict[str, Any]:
        """
        Get common health status information shared by all agents.

        Returns:
            Dictionary containing common health status
        """
        return {
            "agent_type": self.agent_type,
            "name": self.name,
            "version": self.version,
            "status": "healthy",
            "uptime": "active",
            "settings": {
                "redis_url": self.config.redis_url,
                "database_url": "configured"
                if self.config.database_url
                else "not_configured",
                "processing_interval": self.config.processing_interval,
            },
        }


class BaseA2AAgentExecutor(AgentExecutor):
    """
    Base AgentExecutor implementation for Reddit monitoring agents.

    This class handles the A2A protocol execution layer, routing requests
    to the appropriate agent methods while maintaining protocol compliance.
    """

    def __init__(self, agent: BaseA2AAgent):
        """
        Initialize the agent executor.

        Args:
            agent: The BaseA2AAgent instance to execute
        """
        self.agent = agent
        self.logger = logging.getLogger(f"{__name__}.{agent.agent_type}_executor")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Execute an A2A request using the agent's capabilities.

        Args:
            context: Request context containing message and metadata
            event_queue: Queue for sending events back to the client
        """
        try:
            self.logger.info(f"Executing request for {self.agent.agent_type} agent")

            # Extract message content
            message = context.message
            if not message:
                await self._send_error(event_queue, "No message provided")
                return

            # Parse the request
            request_data = self._parse_request(message)
            skill_name = request_data.get("skill")
            parameters = request_data.get("parameters", {})

            if not skill_name:
                await self._send_error(event_queue, "No skill specified")
                return

            # Execute the skill
            result = await self.agent.execute_skill(skill_name, parameters)

            # Send the result
            await self._send_result(event_queue, result)

        except Exception as e:
            self.logger.error(f"Error executing agent request: {e}", exc_info=True)
            await self._send_error(event_queue, f"Execution error: {str(e)}")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Handle cancellation of an ongoing task.

        Args:
            context: Request context
            event_queue: Queue for sending cancellation events
        """
        self.logger.info(f"Cancelling task for {self.agent.agent_type} agent")
        await self._send_result(
            event_queue, {"status": "cancelled", "message": "Task cancelled"}
        )

    def _parse_request(self, message: str) -> dict[str, Any]:
        """
        Parse the incoming message to extract skill and parameters.

        Args:
            message: Raw message content

        Returns:
            Dictionary containing parsed request data
        """
        try:
            if message.startswith("{"):
                # JSON message
                return json.loads(message)
            else:
                # Text message - treat as health check or general query
                return {"skill": "health_check", "parameters": {"message": message}}
        except json.JSONDecodeError:
            # Fallback to health check for non-JSON messages
            return {"skill": "health_check", "parameters": {"message": message}}

    async def _send_result(
        self, event_queue: EventQueue, result: dict[str, Any]
    ) -> None:
        """
        Send a successful result back to the client.

        Args:
            event_queue: Queue for sending events
            result: Result data to send
        """
        result_text = json.dumps(result, indent=2)
        text_message = new_agent_text_message(result_text)
        await event_queue.enqueue_event(text_message)

    async def _send_error(self, event_queue: EventQueue, error_message: str) -> None:
        """
        Send an error message back to the client.

        Args:
            event_queue: Queue for sending events
            error_message: Error message to send
        """
        error_result = {"error": error_message, "status": "failed"}
        error_text = json.dumps(error_result, indent=2)
        text_message = new_agent_text_message(error_text)
        await event_queue.enqueue_event(text_message)


# Simple parameter type helpers for Reddit monitoring skills
def create_skill_parameter(
    name: str, param_type: str, description: str, required: bool = False
) -> dict[str, Any]:
    """
    Create a skill parameter dictionary.

    Args:
        name: Parameter name
        param_type: Parameter type (string, integer, boolean, etc.)
        description: Parameter description
        required: Whether the parameter is required

    Returns:
        Parameter dictionary
    """
    return {
        "name": name,
        "type": param_type,
        "description": description,
        "required": required,
    }


class RedditSkillParameters:
    """Common parameter definitions for Reddit monitoring skills."""

    @staticmethod
    def topic_parameter() -> dict[str, Any]:
        """Parameter for specifying Reddit topics to monitor."""
        return create_skill_parameter(
            name="topic",
            param_type="string",
            description="Topic or keyword to monitor on Reddit",
            required=True,
        )

    @staticmethod
    def subreddit_parameter() -> dict[str, Any]:
        """Parameter for specifying subreddits."""
        return create_skill_parameter(
            name="subreddit",
            param_type="string",
            description="Subreddit name to monitor",
            required=False,
        )

    @staticmethod
    def limit_parameter() -> dict[str, Any]:
        """Parameter for limiting result count."""
        return create_skill_parameter(
            name="limit",
            param_type="integer",
            description="Maximum number of results to return",
            required=False,
        )

    @staticmethod
    def time_range_parameter() -> dict[str, Any]:
        """Parameter for specifying time range."""
        return create_skill_parameter(
            name="time_range",
            param_type="string",
            description="Time range for content (hour, day, week, month, year, all)",
            required=False,
        )
