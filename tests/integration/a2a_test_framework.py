# ABOUTME: Base A2A testing framework for integration tests
# ABOUTME: Provides utilities for testing A2A agent communication, service discovery, and workflows

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiohttp


@dataclass
class AgentInfo:
    """Information about an A2A agent for testing"""

    name: str
    url: str
    port: int
    expected_skills: list[str]
    health_endpoint: str = "/health"
    agent_card_endpoint: str = "/.well-known/agent.json"


@dataclass
class A2ATestResult:
    """Result of an A2A test operation"""

    success: bool
    message: str
    data: dict[str, Any] | None = None
    response_time_ms: float | None = None
    error_details: str | None = None


class A2ATestFramework:
    """Framework for testing A2A agent communication and workflows"""

    def __init__(self):
        self.agents: dict[str, AgentInfo] = {}
        self.session: aiohttp.ClientSession | None = None
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.base_timeout = 30.0  # seconds

        # Default agent configuration from environment
        self._setup_default_agents()

    def _setup_default_agents(self):
        """Setup default agent configuration from environment variables"""
        agent_configs = [
            (
                "coordinator",
                "COORDINATOR_URL",
                8000,
                ["run_monitoring_cycle", "health_check"],
            ),
            (
                "retrieval",
                "RETRIEVAL_URL",
                8001,
                [
                    "fetch_posts_by_topic",
                    "fetch_comments_from_post",
                    "discover_subreddits",
                ],
            ),
            (
                "filter",
                "FILTER_URL",
                8002,
                ["filter_content_by_keywords", "filter_content_by_semantic_similarity"],
            ),
            ("summarise", "SUMMARISE_URL", 8003, ["summarizeContent"]),
            ("alert", "ALERT_URL", 8004, ["sendSlack", "sendEmail"]),
        ]

        for name, env_var, default_port, skills in agent_configs:
            url = os.getenv(env_var, f"http://localhost:{default_port}")
            self.agents[name] = AgentInfo(
                name=name, url=url, port=default_port, expected_skills=skills
            )

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.base_timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def wait_for_agent_health(
        self, agent_name: str, max_attempts: int = 30
    ) -> A2ATestResult:
        """Wait for an agent to become healthy"""
        if agent_name not in self.agents:
            return A2ATestResult(
                success=False, message=f"Agent '{agent_name}' not configured"
            )

        agent = self.agents[agent_name]
        health_url = f"{agent.url}{agent.health_endpoint}"

        for attempt in range(max_attempts):
            try:
                start_time = time.time()
                async with self.session.get(health_url) as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status == 200:
                        data = await response.json()
                        return A2ATestResult(
                            success=True,
                            message=f"Agent '{agent_name}' is healthy",
                            data=data,
                            response_time_ms=response_time,
                        )

            except Exception as e:
                if attempt == max_attempts - 1:  # Last attempt
                    return A2ATestResult(
                        success=False,
                        message=f"Agent '{agent_name}' failed health check after {max_attempts} attempts",
                        error_details=str(e),
                    )

                await asyncio.sleep(2)  # Wait before retry

        return A2ATestResult(
            success=False, message=f"Agent '{agent_name}' health check timeout"
        )

    async def get_agent_card(self, agent_name: str) -> A2ATestResult:
        """Retrieve and validate an agent's Agent Card"""
        if agent_name not in self.agents:
            return A2ATestResult(
                success=False, message=f"Agent '{agent_name}' not configured"
            )

        agent = self.agents[agent_name]
        card_url = f"{agent.url}{agent.agent_card_endpoint}"

        try:
            start_time = time.time()
            async with self.session.get(card_url) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status == 200:
                    card_data = await response.json()

                    # Validate Agent Card structure
                    validation_result = self._validate_agent_card(agent_name, card_data)

                    return A2ATestResult(
                        success=validation_result.success,
                        message=validation_result.message,
                        data=card_data,
                        response_time_ms=response_time,
                        error_details=validation_result.error_details,
                    )
                else:
                    return A2ATestResult(
                        success=False,
                        message=f"Failed to get agent card: HTTP {response.status}",
                        response_time_ms=response_time,
                    )

        except Exception as e:
            return A2ATestResult(
                success=False,
                message=f"Error retrieving agent card for '{agent_name}'",
                error_details=str(e),
            )

    def _validate_agent_card(
        self, agent_name: str, card_data: dict[str, Any]
    ) -> A2ATestResult:
        """Validate Agent Card structure and content"""
        required_fields = ["name", "description", "skills", "version"]
        missing_fields = [field for field in required_fields if field not in card_data]

        if missing_fields:
            return A2ATestResult(
                success=False,
                message=f"Agent card missing required fields: {missing_fields}",
                error_details=f"Missing: {', '.join(missing_fields)}",
            )

        # Validate skills
        agent_info = self.agents[agent_name]
        card_skills = [skill["name"] for skill in card_data.get("skills", [])]

        missing_skills = set(agent_info.expected_skills) - set(card_skills)
        if missing_skills:
            return A2ATestResult(
                success=False,
                message=f"Agent card missing expected skills: {missing_skills}",
                error_details=f"Expected skills: {agent_info.expected_skills}, Found: {card_skills}",
            )

        return A2ATestResult(success=True, message="Agent card validation passed")

    async def invoke_agent_skill(
        self, agent_name: str, skill_name: str, parameters: dict[str, Any] = None
    ) -> A2ATestResult:
        """Invoke a specific skill on an agent via A2A protocol"""
        if agent_name not in self.agents:
            return A2ATestResult(
                success=False, message=f"Agent '{agent_name}' not configured"
            )

        agent = self.agents[agent_name]
        skill_url = f"{agent.url}/skills/{skill_name}"

        payload = {
            "parameters": parameters or {},
            "context": {
                "correlation_id": f"test_{int(time.time())}",
                "timestamp": datetime.now(UTC).isoformat(),
                "test_mode": True,
            },
        }

        try:
            start_time = time.time()
            async with self.session.post(skill_url, json=payload) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status == 200:
                    result_data = await response.json()
                    return A2ATestResult(
                        success=True,
                        message=f"Skill '{skill_name}' executed successfully",
                        data=result_data,
                        response_time_ms=response_time,
                    )
                else:
                    error_text = await response.text()
                    return A2ATestResult(
                        success=False,
                        message=f"Skill execution failed: HTTP {response.status}",
                        response_time_ms=response_time,
                        error_details=error_text,
                    )

        except Exception as e:
            return A2ATestResult(
                success=False,
                message=f"Error invoking skill '{skill_name}' on '{agent_name}'",
                error_details=str(e),
            )

    async def test_agent_to_agent_communication(
        self,
        source_agent: str,
        target_agent: str,
        skill_name: str,
        parameters: dict[str, Any] = None,
    ) -> A2ATestResult:
        """Test communication between two agents"""

        # First, ensure both agents are healthy
        source_health = await self.wait_for_agent_health(source_agent)
        if not source_health.success:
            return A2ATestResult(
                success=False,
                message=f"Source agent '{source_agent}' is not healthy",
                error_details=source_health.error_details,
            )

        target_health = await self.wait_for_agent_health(target_agent)
        if not target_health.success:
            return A2ATestResult(
                success=False,
                message=f"Target agent '{target_agent}' is not healthy",
                error_details=target_health.error_details,
            )

        # Test the communication
        result = await self.invoke_agent_skill(target_agent, skill_name, parameters)

        if result.success:
            return A2ATestResult(
                success=True,
                message=f"A2A communication successful: {source_agent} -> {target_agent}",
                data={
                    "source_agent": source_agent,
                    "target_agent": target_agent,
                    "skill": skill_name,
                    "parameters": parameters,
                    "result": result.data,
                },
                response_time_ms=result.response_time_ms,
            )
        else:
            return A2ATestResult(
                success=False,
                message=f"A2A communication failed: {source_agent} -> {target_agent}",
                error_details=result.error_details,
            )

    async def discover_agents_via_redis(self) -> A2ATestResult:
        """Test agent discovery through Redis service registry"""
        try:
            import redis.asyncio as redis

            # Connect to Redis
            redis_client = redis.from_url(self.redis_url)

            # Get all agent registrations
            agent_keys = await redis_client.keys("agent:*")
            discovered_agents = {}

            for key in agent_keys:
                agent_data = await redis_client.hgetall(key)
                if agent_data:
                    # Decode bytes to strings
                    agent_info = {k.decode(): v.decode() for k, v in agent_data.items()}
                    agent_name = key.decode().split(":")[-1]
                    discovered_agents[agent_name] = agent_info

            await redis_client.close()

            return A2ATestResult(
                success=True,
                message=f"Discovered {len(discovered_agents)} agents via Redis",
                data={"agents": discovered_agents},
            )

        except Exception as e:
            return A2ATestResult(
                success=False,
                message="Failed to discover agents via Redis",
                error_details=str(e),
            )

    async def test_workflow_orchestration(
        self, workflow_name: str, parameters: dict[str, Any] = None
    ) -> A2ATestResult:
        """Test complete workflow orchestration through CoordinatorAgent"""

        coordinator_health = await self.wait_for_agent_health("coordinator")
        if not coordinator_health.success:
            return A2ATestResult(
                success=False,
                message="CoordinatorAgent is not healthy",
                error_details=coordinator_health.error_details,
            )

        # Invoke workflow on coordinator
        result = await self.invoke_agent_skill(
            "coordinator",
            "orchestrate_workflow",
            {"workflow_name": workflow_name, **(parameters or {})},
        )

        if result.success:
            return A2ATestResult(
                success=True,
                message=f"Workflow '{workflow_name}' orchestrated successfully",
                data=result.data,
                response_time_ms=result.response_time_ms,
            )
        else:
            return A2ATestResult(
                success=False,
                message=f"Workflow '{workflow_name}' orchestration failed",
                error_details=result.error_details,
            )

    async def validate_all_agents(self) -> dict[str, A2ATestResult]:
        """Validate all configured agents (health + agent cards)"""
        results = {}

        for agent_name in self.agents.keys():
            # Test health
            health_result = await self.wait_for_agent_health(agent_name)

            # Test agent card
            card_result = await self.get_agent_card(agent_name)

            # Combine results
            overall_success = health_result.success and card_result.success
            results[agent_name] = A2ATestResult(
                success=overall_success,
                message=f"Health: {health_result.message}, Card: {card_result.message}",
                data={"health": health_result.data, "agent_card": card_result.data},
                response_time_ms=(health_result.response_time_ms or 0)
                + (card_result.response_time_ms or 0),
                error_details=(health_result.error_details or "")
                + (card_result.error_details or ""),
            )

        return results
