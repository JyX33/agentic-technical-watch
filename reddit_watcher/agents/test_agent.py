# ABOUTME: Test A2A agent implementation for validating the base agent architecture
# ABOUTME: Provides health check and echo skills for testing A2A protocol functionality

import asyncio
from typing import Any

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import BaseA2AAgent
from reddit_watcher.agents.server import run_agent_server
from reddit_watcher.config import Settings, create_config


class MockA2AAgent(BaseA2AAgent):
    """
    Test A2A agent for validating the base agent architecture.

    Provides simple health check and echo capabilities to verify
    A2A protocol functionality and service discovery.
    """

    def __init__(self, config: Settings):
        super().__init__(
            config=config,
            agent_type="test",
            name="Test A2A Agent",
            description="Test agent for validating A2A protocol implementation",
            version="1.0.0",
        )

    def get_skills(self) -> list[AgentSkill]:
        """Define the skills provided by the test agent."""
        return [
            AgentSkill(
                id="health_check",
                name="health_check",
                description="Check the health status of the agent",
                tags=["health", "status"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="echo",
                name="echo",
                description="Echo back a message with additional metadata",
                tags=["utility", "test"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="reddit_topics",
                name="reddit_topics",
                description="Get the configured Reddit monitoring topics",
                tags=["reddit", "configuration"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
        ]

    async def execute_skill(
        self, skill_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a specific skill with the given parameters."""
        if skill_name == "health_check":
            return await self._handle_health_check(parameters)
        elif skill_name == "echo":
            return await self._handle_echo(parameters)
        elif skill_name == "reddit_topics":
            return await self._handle_reddit_topics(parameters)
        else:
            raise ValueError(f"Unknown skill: {skill_name}")

    async def _handle_health_check(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Handle health check requests."""
        health_status = self.get_health_status()
        return {"skill": "health_check", "status": "success", "result": health_status}

    async def _handle_echo(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Handle echo requests."""
        message = parameters.get("message", "No message provided")

        return {
            "skill": "echo",
            "status": "success",
            "result": {
                "original_message": message,
                "echoed_at": asyncio.get_event_loop().time(),
                "agent_type": self.agent_type,
                "agent_name": self.name,
                "message_length": len(message),
            },
        }

    async def _handle_reddit_topics(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Handle Reddit topics requests."""
        return {
            "skill": "reddit_topics",
            "status": "success",
            "result": {
                "topics": self.config.reddit_topics,
                "processing_interval": self.config.processing_interval,
                "relevance_threshold": self.config.relevance_threshold,
            },
        }

    async def get_agent_specific_health(self) -> dict[str, Any]:
        """Get test agent-specific health information."""
        test_health = {
            "skills": [skill.name for skill in self.get_skills()],
            "test_mode": True,
            "capabilities": {
                "echo": True,
                "health_check": True,
                "reddit_topics": True,
            },
        }

        # Test basic functionality
        test_health["basic_tests"] = {
            "skill_enumeration": "passed",
            "configuration_access": "passed"
            if hasattr(self.config, "reddit_topics")
            else "failed",
            "echo_functionality": "available",
            "health_check_functionality": "available",
        }

        # Test agent health status
        test_health["agent_status"] = {
            "initialized": True,
            "event_loop_accessible": True,
            "configuration_loaded": self.config is not None,
            "skills_registered": len(self.get_skills()) > 0,
        }

        return test_health


def main():
    """Main entry point for running the test agent."""
    import logging

    logging.basicConfig(level=logging.INFO)

    config = create_config()
    agent = MockA2AAgent(config)
    print(f"Starting {agent.name} on port {config.a2a_port}")
    print(
        f"Agent Card will be available at: http://localhost:{config.a2a_port}/.well-known/agent.json"
    )
    print(f"Health check at: http://localhost:{config.a2a_port}/health")

    run_agent_server(agent, config)


if __name__ == "__main__":
    main()
