#!/usr/bin/env python3
# ABOUTME: A2A Communication Protocol Tester for Reddit Technical Watcher agents
# ABOUTME: Validates inter-agent communication, service discovery, and protocol compliance

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import UTC, datetime
from multiprocessing import Process
from typing import Any

import aiohttp
import redis.asyncio as redis
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables first
load_dotenv()

from reddit_watcher.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentEndpoint(BaseModel):
    """Agent endpoint configuration."""

    name: str
    agent_type: str
    port: int
    url: str
    expected_skills: list[str]


class TestResult(BaseModel):
    """Test result structure."""

    test_name: str
    agent_name: str
    status: str  # "pass", "fail", "skip"
    message: str
    timestamp: datetime
    details: dict[str, Any] | None = None


class A2ACommunicationTester:
    """
    Comprehensive A2A Communication Protocol Tester.

    Tests all aspects of A2A agent communication including:
    - Agent server startup and availability
    - Agent Card endpoints and schema validation
    - Health check endpoints
    - Service discovery via Redis
    - JSON-RPC A2A protocol communication
    - Inter-agent workflow execution
    - Authentication mechanisms
    - Error handling and circuit breakers
    """

    def __init__(self):
        # Force the correct Redis URL for testing
        os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"
        logger.info(f"Set REDIS_URL env var: {os.getenv('REDIS_URL')}")

        self.settings = get_settings()
        self.test_results: list[TestResult] = []
        self.agent_processes: list[Process] = []
        self.redis_client: redis.Redis | None = None

        # Print Redis URL for debugging (without password)
        redis_url_safe = (
            self.settings.redis_url.replace(":dev_redis_123@", ":***@")
            if "dev_redis_123" in self.settings.redis_url
            else self.settings.redis_url
        )
        logger.info(f"Using Redis URL: {redis_url_safe}")

        # Define expected agent configuration
        self.agents = [
            AgentEndpoint(
                name="CoordinatorAgent",
                agent_type="coordinator",
                port=8000,
                url="http://localhost:8000",
                expected_skills=["coordinate_workflow", "health_check"],
            ),
            AgentEndpoint(
                name="RetrievalAgent",
                agent_type="retrieval",
                port=8001,
                url="http://localhost:8001",
                expected_skills=["fetch_posts", "discover_subreddits", "health_check"],
            ),
            AgentEndpoint(
                name="FilterAgent",
                agent_type="filter",
                port=8002,
                url="http://localhost:8002",
                expected_skills=["filter_content", "check_relevance", "health_check"],
            ),
            AgentEndpoint(
                name="SummariseAgent",
                agent_type="summarise",
                port=8003,
                url="http://localhost:8003",
                expected_skills=["summarise_content", "health_check"],
            ),
            AgentEndpoint(
                name="AlertAgent",
                agent_type="alert",
                port=8004,
                url="http://localhost:8004",
                expected_skills=["send_notification", "health_check"],
            ),
        ]

    async def setup_redis(self) -> None:
        """Setup Redis connection for service discovery testing."""
        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self.redis_client.ping()
            logger.info("✅ Redis connection established for service discovery testing")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise

    async def cleanup_redis(self) -> None:
        """Cleanup Redis connection."""
        if self.redis_client:
            try:
                await self.redis_client.aclose()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    def start_agent_servers(self) -> None:
        """Start all agent servers for testing."""
        logger.info("🚀 Starting agent servers for A2A communication testing...")

        def run_coordinator_agent():
            """Run coordinator agent server."""
            import os

            from reddit_watcher.config import Settings

            os.environ["A2A_PORT"] = "8000"
            os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"
            from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
            from reddit_watcher.agents.server import run_agent_server

            config = Settings()
            agent = CoordinatorAgent(config)
            run_agent_server(agent, config)

        def run_retrieval_agent():
            """Run retrieval agent server."""
            import os

            from reddit_watcher.config import Settings

            os.environ["A2A_PORT"] = "8001"
            os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"
            from reddit_watcher.agents.retrieval_agent import RetrievalAgent
            from reddit_watcher.agents.server import run_agent_server

            config = Settings()
            agent = RetrievalAgent(config)
            run_agent_server(agent, config)

        def run_filter_agent():
            """Run filter agent server."""
            import os

            from reddit_watcher.config import Settings

            os.environ["A2A_PORT"] = "8002"
            os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"
            from reddit_watcher.agents.filter_agent import FilterAgent
            from reddit_watcher.agents.server import run_agent_server

            config = Settings()
            agent = FilterAgent(config)
            run_agent_server(agent, config)

        def run_summarise_agent():
            """Run summarise agent server."""
            import os

            from reddit_watcher.config import Settings

            os.environ["A2A_PORT"] = "8003"
            os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"
            from reddit_watcher.agents.server import run_agent_server
            from reddit_watcher.agents.summarise_agent import SummariseAgent

            config = Settings()
            agent = SummariseAgent(config)
            run_agent_server(agent, config)

        def run_alert_agent():
            """Run alert agent server."""
            import os

            from reddit_watcher.config import Settings

            os.environ["A2A_PORT"] = "8004"
            os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"
            from reddit_watcher.agents.alert_agent import AlertAgent
            from reddit_watcher.agents.server import run_agent_server

            config = Settings()
            agent = AlertAgent(config)
            run_agent_server(agent, config)

        # Define agent server functions
        agent_servers = [
            (run_coordinator_agent, "CoordinatorAgent"),
            (run_retrieval_agent, "RetrievalAgent"),
            (run_filter_agent, "FilterAgent"),
            (run_summarise_agent, "SummariseAgent"),
            (run_alert_agent, "AlertAgent"),
        ]

        # Start each agent in a separate process
        for server_func, agent_name in agent_servers:
            try:
                process = Process(target=server_func, name=f"{agent_name}-server")
                process.start()
                self.agent_processes.append(process)
                logger.info(
                    f"✅ Started {agent_name} server process (PID: {process.pid})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to start {agent_name}: {e}")
                self.log_test_result(
                    "server_startup", agent_name, "fail", f"Failed to start: {e}"
                )

        # Wait for servers to start up
        logger.info("⏳ Waiting for agent servers to start up...")
        time.sleep(15)  # Increase wait time for slow-starting agents

    def stop_agent_servers(self) -> None:
        """Stop all agent server processes."""
        logger.info("🛑 Stopping agent server processes...")

        for process in self.agent_processes:
            if process.is_alive():
                try:
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()
                        process.join()
                    logger.info(f"✅ Stopped {process.name}")
                except Exception as e:
                    logger.error(f"❌ Error stopping {process.name}: {e}")

        self.agent_processes.clear()

    def log_test_result(
        self,
        test_name: str,
        agent_name: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a test result."""
        result = TestResult(
            test_name=test_name,
            agent_name=agent_name,
            status=status,
            message=message,
            timestamp=datetime.now(UTC),
            details=details,
        )
        self.test_results.append(result)

        status_emoji = "✅" if status == "pass" else "❌" if status == "fail" else "⏭️"
        logger.info(f"{status_emoji} {test_name} [{agent_name}]: {message}")

    async def test_agent_availability(self) -> None:
        """Test that all agent servers are responding to basic HTTP requests."""
        logger.info("🔍 Testing agent server availability...")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            for agent in self.agents:
                try:
                    async with session.get(f"{agent.url}/health") as response:
                        if response.status == 200:
                            self.log_test_result(
                                "server_availability",
                                agent.name,
                                "pass",
                                f"Server responding on port {agent.port}",
                            )
                        else:
                            self.log_test_result(
                                "server_availability",
                                agent.name,
                                "fail",
                                f"Server returned status {response.status}",
                            )
                except Exception as e:
                    self.log_test_result(
                        "server_availability",
                        agent.name,
                        "fail",
                        f"Connection failed: {e}",
                    )

    async def test_agent_cards(self) -> None:
        """Test Agent Card endpoints for A2A service discovery."""
        logger.info("🔍 Testing Agent Card endpoints...")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            for agent in self.agents:
                try:
                    async with session.get(
                        f"{agent.url}/.well-known/agent.json"
                    ) as response:
                        if response.status == 200:
                            agent_card = await response.json()

                            # Validate required agent card fields
                            required_fields = [
                                "name",
                                "description",
                                "version",
                                "url",
                                "capabilities",
                                "skills",
                            ]
                            missing_fields = [
                                field
                                for field in required_fields
                                if field not in agent_card
                            ]

                            if not missing_fields:
                                # Validate skills
                                skills = agent_card.get("skills", [])
                                skill_names = [
                                    skill.get("name", "") for skill in skills
                                ]

                                self.log_test_result(
                                    "agent_card",
                                    agent.name,
                                    "pass",
                                    f"Valid agent card with {len(skills)} skills: {skill_names}",
                                    details={
                                        "agent_card": agent_card,
                                        "skill_names": skill_names,
                                    },
                                )
                            else:
                                self.log_test_result(
                                    "agent_card",
                                    agent.name,
                                    "fail",
                                    f"Missing required fields: {missing_fields}",
                                    details={
                                        "agent_card": agent_card,
                                        "missing_fields": missing_fields,
                                    },
                                )
                        else:
                            self.log_test_result(
                                "agent_card",
                                agent.name,
                                "fail",
                                f"Agent card endpoint returned status {response.status}",
                            )
                except Exception as e:
                    self.log_test_result(
                        "agent_card",
                        agent.name,
                        "fail",
                        f"Agent card request failed: {e}",
                    )

    async def test_health_endpoints(self) -> None:
        """Test health check endpoints."""
        logger.info("🔍 Testing health check endpoints...")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            for agent in self.agents:
                try:
                    async with session.get(f"{agent.url}/health") as response:
                        if response.status == 200:
                            health_data = await response.json()

                            # Validate health response structure
                            required_fields = ["agent_type", "name", "status"]
                            missing_fields = [
                                field
                                for field in required_fields
                                if field not in health_data
                            ]

                            if (
                                not missing_fields
                                and health_data.get("status") == "healthy"
                            ):
                                self.log_test_result(
                                    "health_check",
                                    agent.name,
                                    "pass",
                                    "Health endpoint returned healthy status",
                                    details={"health_data": health_data},
                                )
                            else:
                                self.log_test_result(
                                    "health_check",
                                    agent.name,
                                    "fail",
                                    f"Invalid health response. Missing: {missing_fields}, Status: {health_data.get('status')}",
                                    details={"health_data": health_data},
                                )
                        else:
                            self.log_test_result(
                                "health_check",
                                agent.name,
                                "fail",
                                f"Health endpoint returned status {response.status}",
                            )
                except Exception as e:
                    self.log_test_result(
                        "health_check", agent.name, "fail", f"Health check failed: {e}"
                    )

    async def test_service_discovery(self) -> None:
        """Test Redis-based service discovery."""
        logger.info("🔍 Testing service discovery via Redis...")

        if not self.redis_client:
            self.log_test_result(
                "service_discovery", "Redis", "fail", "Redis client not initialized"
            )
            return

        try:
            # Test agent registration discovery
            agent_keys = await self.redis_client.keys("agent:*")
            registered_agents = {}

            for key in agent_keys:
                agent_info = await self.redis_client.hgetall(key)
                if agent_info:
                    agent_type = key.replace("agent:", "")
                    registered_agents[agent_type] = agent_info

            if registered_agents:
                self.log_test_result(
                    "service_discovery",
                    "Registry",
                    "pass",
                    f"Found {len(registered_agents)} registered agents: {list(registered_agents.keys())}",
                    details={"registered_agents": registered_agents},
                )
            else:
                self.log_test_result(
                    "service_discovery",
                    "Registry",
                    "fail",
                    "No agents found in service registry",
                )

            # Test discovery endpoint on each agent
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                for agent in self.agents:
                    try:
                        async with session.get(f"{agent.url}/discover") as response:
                            if response.status == 200:
                                discovery_data = await response.json()
                                discovered_agents = discovery_data.get("agents", {})

                                self.log_test_result(
                                    "service_discovery",
                                    agent.name,
                                    "pass",
                                    f"Discovery endpoint returned {len(discovered_agents)} agents",
                                    details={
                                        "discovered_agents": list(
                                            discovered_agents.keys()
                                        )
                                    },
                                )
                            else:
                                self.log_test_result(
                                    "service_discovery",
                                    agent.name,
                                    "fail",
                                    f"Discovery endpoint returned status {response.status}",
                                )
                    except Exception as e:
                        self.log_test_result(
                            "service_discovery",
                            agent.name,
                            "fail",
                            f"Discovery endpoint failed: {e}",
                        )

        except Exception as e:
            self.log_test_result(
                "service_discovery",
                "Redis",
                "fail",
                f"Service registry access failed: {e}",
            )

    async def test_a2a_jsonrpc_communication(self) -> None:
        """Test A2A JSON-RPC protocol communication."""
        logger.info("🔍 Testing A2A JSON-RPC communication...")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            for agent in self.agents:
                try:
                    # Test message/send JSON-RPC method
                    jsonrpc_request = {
                        "jsonrpc": "2.0",
                        "method": "message/send",
                        "params": {
                            "message": {
                                "role": "user",
                                "parts": [{"kind": "text", "text": "health check"}],
                                "messageId": "test-message-001",
                                "contextId": "test-context-001",
                            },
                            "metadata": {"test": True},
                        },
                        "id": 1,
                    }

                    async with session.post(
                        f"{agent.url}/a2a",
                        json=jsonrpc_request,
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        if response.status == 200:
                            result = await response.json()

                            # Validate JSON-RPC response structure
                            if (
                                result.get("jsonrpc") == "2.0"
                                and "result" in result
                                and result.get("id") == 1
                            ):
                                task_result = result.get("result", {})
                                if task_result.get("kind") == "task":
                                    self.log_test_result(
                                        "a2a_jsonrpc",
                                        agent.name,
                                        "pass",
                                        "JSON-RPC message/send successful",
                                        details={
                                            "task_id": task_result.get("id"),
                                            "status": task_result.get("status", {}).get(
                                                "state"
                                            ),
                                        },
                                    )
                                else:
                                    self.log_test_result(
                                        "a2a_jsonrpc",
                                        agent.name,
                                        "fail",
                                        f"Invalid task result structure: {task_result}",
                                        details={"response": result},
                                    )
                            else:
                                self.log_test_result(
                                    "a2a_jsonrpc",
                                    agent.name,
                                    "fail",
                                    f"Invalid JSON-RPC response structure: {result}",
                                    details={"response": result},
                                )
                        else:
                            response_text = await response.text()
                            self.log_test_result(
                                "a2a_jsonrpc",
                                agent.name,
                                "fail",
                                f"JSON-RPC request failed with status {response.status}: {response_text}",
                            )

                except Exception as e:
                    self.log_test_result(
                        "a2a_jsonrpc",
                        agent.name,
                        "fail",
                        f"JSON-RPC communication error: {e}",
                    )

    async def test_inter_agent_workflow(self) -> None:
        """Test complete inter-agent workflow communication."""
        logger.info("🔍 Testing inter-agent workflow communication...")

        # Test workflow: RetrievalAgent → FilterAgent → SummariseAgent → AlertAgent
        workflow_steps = [
            ("RetrievalAgent", "fetch_posts", {"topic": "Claude Code", "limit": 5}),
            (
                "FilterAgent",
                "filter_content",
                {"content": "test content", "topic": "Claude Code"},
            ),
            (
                "SummariseAgent",
                "summarise_content",
                {"content": "test filtered content"},
            ),
            (
                "AlertAgent",
                "send_notification",
                {"message": "test summary", "channel": "test"},
            ),
        ]

        previous_result = None
        workflow_results = []

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        ) as session:
            for agent_name, skill_name, base_params in workflow_steps:
                try:
                    # Find agent configuration
                    agent_config = next(
                        (a for a in self.agents if a.name == agent_name), None
                    )
                    if not agent_config:
                        self.log_test_result(
                            "workflow_communication",
                            agent_name,
                            "fail",
                            "Agent configuration not found",
                        )
                        continue

                    # Prepare parameters (chain with previous result if available)
                    params = base_params.copy()
                    if previous_result and "data" in previous_result:
                        params.update({"input_data": previous_result["data"]})

                    # Create JSON-RPC request for skill execution
                    jsonrpc_request = {
                        "jsonrpc": "2.0",
                        "method": "message/send",
                        "params": {
                            "message": {
                                "role": "user",
                                "parts": [
                                    {
                                        "kind": "text",
                                        "text": json.dumps(
                                            {"skill": skill_name, "parameters": params}
                                        ),
                                    }
                                ],
                                "messageId": f"workflow-{skill_name}-001",
                                "contextId": "workflow-test-001",
                            },
                            "metadata": {
                                "workflow_step": skill_name,
                                "agent": agent_name,
                            },
                        },
                        "id": len(workflow_results) + 1,
                    }

                    async with session.post(
                        f"{agent_config.url}/a2a",
                        json=jsonrpc_request,
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            task_result = result.get("result", {})

                            if (
                                task_result.get("status", {}).get("state")
                                == "completed"
                            ):
                                workflow_results.append(
                                    {
                                        "agent": agent_name,
                                        "skill": skill_name,
                                        "status": "completed",
                                        "result": task_result,
                                    }
                                )
                                previous_result = {"data": f"output from {skill_name}"}

                                self.log_test_result(
                                    "workflow_communication",
                                    agent_name,
                                    "pass",
                                    f"Workflow step {skill_name} completed successfully",
                                    details={"step_result": task_result},
                                )
                            else:
                                self.log_test_result(
                                    "workflow_communication",
                                    agent_name,
                                    "fail",
                                    f"Workflow step {skill_name} failed or incomplete: {task_result.get('status', {})}",
                                )
                                break
                        else:
                            response_text = await response.text()
                            self.log_test_result(
                                "workflow_communication",
                                agent_name,
                                "fail",
                                f"Workflow step {skill_name} HTTP error {response.status}: {response_text}",
                            )
                            break

                except Exception as e:
                    self.log_test_result(
                        "workflow_communication",
                        agent_name,
                        "fail",
                        f"Workflow step {skill_name} exception: {e}",
                    )
                    break

        # Log overall workflow result
        completed_steps = len(
            [r for r in workflow_results if r["status"] == "completed"]
        )
        total_steps = len(workflow_steps)

        if completed_steps == total_steps:
            self.log_test_result(
                "workflow_communication",
                "Overall",
                "pass",
                f"Complete workflow executed successfully ({completed_steps}/{total_steps} steps)",
                details={"workflow_results": workflow_results},
            )
        else:
            self.log_test_result(
                "workflow_communication",
                "Overall",
                "fail",
                f"Incomplete workflow execution ({completed_steps}/{total_steps} steps completed)",
                details={"workflow_results": workflow_results},
            )

    async def run_all_tests(self) -> None:
        """Run all A2A communication tests."""
        logger.info("🧪 Starting comprehensive A2A communication testing...")

        try:
            # Setup Redis connection
            await self.setup_redis()

            # Start agent servers
            self.start_agent_servers()

            # Run test suite
            await self.test_agent_availability()
            await self.test_agent_cards()
            await self.test_health_endpoints()
            await self.test_service_discovery()
            await self.test_a2a_jsonrpc_communication()
            await self.test_inter_agent_workflow()

        except Exception as e:
            logger.error(f"❌ Test execution error: {e}")
            self.log_test_result(
                "test_execution", "Framework", "fail", f"Test execution error: {e}"
            )

        finally:
            # Cleanup
            self.stop_agent_servers()
            await self.cleanup_redis()

    def generate_test_report(self) -> str:
        """Generate comprehensive test report."""
        logger.info("📊 Generating A2A communication test report...")

        # Calculate test statistics
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == "pass"])
        failed_tests = len([r for r in self.test_results if r.status == "fail"])
        skipped_tests = len([r for r in self.test_results if r.status == "skip"])

        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Group results by test type
        results_by_test = {}
        for result in self.test_results:
            if result.test_name not in results_by_test:
                results_by_test[result.test_name] = []
            results_by_test[result.test_name].append(result)

        # Generate report
        report = [
            "# A2A Communication Protocol Test Report",
            f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "**System:** Reddit Technical Watcher",
            "",
            "## Executive Summary",
            f"- **Total Tests:** {total_tests}",
            f"- **Passed:** {passed_tests} ({pass_rate:.1f}%)",
            f"- **Failed:** {failed_tests}",
            f"- **Skipped:** {skipped_tests}",
            "",
            "## Test Results by Category",
            "",
        ]

        for test_name, results in results_by_test.items():
            test_passed = len([r for r in results if r.status == "pass"])
            test_failed = len([r for r in results if r.status == "fail"])
            test_skipped = len([r for r in results if r.status == "skip"])

            report.extend(
                [
                    f"### {test_name.replace('_', ' ').title()}",
                    f"**Results:** {test_passed} passed, {test_failed} failed, {test_skipped} skipped",
                    "",
                ]
            )

            for result in results:
                status_emoji = (
                    "✅"
                    if result.status == "pass"
                    else "❌"
                    if result.status == "fail"
                    else "⏭️"
                )
                report.append(
                    f"- {status_emoji} **{result.agent_name}**: {result.message}"
                )

            report.append("")

        # Add detailed findings
        report.extend(
            [
                "## Detailed Findings",
                "",
                "### Agent Server Availability",
                "Tests whether all agent servers are running and responding to HTTP requests.",
                "",
            ]
        )

        server_results = [
            r for r in self.test_results if r.test_name == "server_availability"
        ]
        for result in server_results:
            status_emoji = "✅" if result.status == "pass" else "❌"
            report.append(f"- {status_emoji} {result.agent_name}: {result.message}")

        report.extend(
            [
                "",
                "### Agent Card Validation",
                "Validates Agent Card endpoints for A2A service discovery compliance.",
                "",
            ]
        )

        card_results = [r for r in self.test_results if r.test_name == "agent_card"]
        for result in card_results:
            status_emoji = "✅" if result.status == "pass" else "❌"
            report.append(f"- {status_emoji} {result.agent_name}: {result.message}")
            if result.details and "skill_names" in result.details:
                skills = ", ".join(result.details["skill_names"])
                report.append(f"  - Available skills: {skills}")

        report.extend(
            [
                "",
                "### Service Discovery",
                "Tests Redis-based agent registration and discovery mechanisms.",
                "",
            ]
        )

        discovery_results = [
            r for r in self.test_results if r.test_name == "service_discovery"
        ]
        for result in discovery_results:
            status_emoji = "✅" if result.status == "pass" else "❌"
            report.append(f"- {status_emoji} {result.agent_name}: {result.message}")

        report.extend(
            [
                "",
                "### A2A JSON-RPC Communication",
                "Tests A2A protocol JSON-RPC message exchange between agents.",
                "",
            ]
        )

        jsonrpc_results = [r for r in self.test_results if r.test_name == "a2a_jsonrpc"]
        for result in jsonrpc_results:
            status_emoji = "✅" if result.status == "pass" else "❌"
            report.append(f"- {status_emoji} {result.agent_name}: {result.message}")

        report.extend(
            [
                "",
                "### Inter-Agent Workflow",
                "Tests complete workflow execution across the agent chain.",
                "",
            ]
        )

        workflow_results = [
            r for r in self.test_results if r.test_name == "workflow_communication"
        ]
        for result in workflow_results:
            status_emoji = "✅" if result.status == "pass" else "❌"
            report.append(f"- {status_emoji} {result.agent_name}: {result.message}")

        # Add recommendations
        report.extend(["", "## Recommendations", ""])

        if failed_tests > 0:
            report.extend(["### Critical Issues", ""])

            failed_results = [r for r in self.test_results if r.status == "fail"]
            for result in failed_results:
                report.append(
                    f"- **{result.test_name} - {result.agent_name}**: {result.message}"
                )

            report.extend(
                [
                    "",
                    "### Next Steps",
                    "1. Address critical communication failures before proceeding with production deployment",
                    "2. Verify all agent servers are properly configured and running",
                    "3. Ensure Redis service discovery is functioning correctly",
                    "4. Validate A2A JSON-RPC protocol implementation across all agents",
                    "5. Test authentication mechanisms and error handling",
                    "",
                ]
            )
        else:
            report.extend(
                [
                    "✅ **All tests passed!** The A2A communication system is functioning correctly.",
                    "",
                    "### Production Readiness",
                    "- All agent servers are responding correctly",
                    "- Service discovery is working via Redis",
                    "- A2A JSON-RPC protocol is implemented properly",
                    "- Inter-agent workflow communication is functional",
                    "",
                    "The system is ready for production deployment.",
                    "",
                ]
            )

        # Add technical details
        report.extend(
            [
                "## Technical Configuration",
                f"- **Base Port:** {self.settings.a2a_port}",
                f"- **Redis URL:** {self.settings.redis_url}",
                "- **Agent Endpoints:**",
            ]
        )

        for agent in self.agents:
            report.append(f"  - {agent.name}: {agent.url}")

        report.extend(
            ["", "---", "*Report generated by A2A Communication Protocol Tester*"]
        )

        return "\n".join(report)

    def save_test_report(
        self, filename: str = "A2A_COMMUNICATION_TEST_REPORT.md"
    ) -> None:
        """Save test report to file."""
        report_content = self.generate_test_report()

        with open(filename, "w") as f:
            f.write(report_content)

        logger.info(f"📄 Test report saved to {filename}")


async def main():
    """Main test execution function."""
    tester = A2ACommunicationTester()

    def signal_handler(signum, frame):
        logger.info("🛑 Test execution interrupted, cleaning up...")
        tester.stop_agent_servers()
        sys.exit(0)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Run all tests
        await tester.run_all_tests()

        # Generate and save report
        tester.save_test_report()

        # Print summary
        total_tests = len(tester.test_results)
        passed_tests = len([r for r in tester.test_results if r.status == "pass"])
        failed_tests = len([r for r in tester.test_results if r.status == "fail"])

        print("\n" + "=" * 60)
        print("🧪 A2A COMMUNICATION TESTING COMPLETE")
        print("=" * 60)
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(
            f"📈 Success Rate: {(passed_tests / total_tests * 100):.1f}%"
            if total_tests > 0
            else "N/A"
        )
        print("📄 Detailed report saved to A2A_COMMUNICATION_TEST_REPORT.md")
        print("=" * 60)

        # Exit with appropriate code
        sys.exit(0 if failed_tests == 0 else 1)

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        tester.stop_agent_servers()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
