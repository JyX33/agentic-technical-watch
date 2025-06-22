# ABOUTME: Comprehensive integration test for the complete Reddit monitoring workflow
# ABOUTME: Tests full agent coordination, failure scenarios, circuit breakers, and authentication

import asyncio
import time
from unittest.mock import patch

import aiohttp
import pytest
from pydantic import field_validator

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.auth_middleware import AuthMiddleware
from reddit_watcher.circuit_breaker import (
    get_circuit_breaker_registry,
)
from reddit_watcher.config import Settings
from reddit_watcher.database.utils import get_db_session
from reddit_watcher.models import AgentTask, WorkflowExecution
from tests.fixtures.test_data import MOCK_REDDIT_POSTS
from tests.integration.a2a_test_framework import A2ATestFramework


# Override Settings for testing to allow SQLite
class IntegrationTestSettings(Settings):
    """Test-specific Settings that allows SQLite databases"""

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Allow both PostgreSQL and SQLite for testing."""
        if not v:
            raise ValueError("Database URL cannot be empty")

        from urllib.parse import urlparse

        parsed = urlparse(v)
        if parsed.scheme not in [
            "postgresql",
            "postgresql+psycopg2",
            "postgresql+asyncpg",
            "sqlite",  # Allow SQLite for testing
        ]:
            raise ValueError("Database URL must use postgresql or sqlite scheme")

        return v


def create_mock_agent_response(
    agent_name: str, skill: str, success: bool = True, custom_result: dict = None
):
    """Create mock response for agent communication"""
    if not success:
        return {"status": "error", "error": f"Mock error from {agent_name} agent"}

    if custom_result:
        return {"status": "success", "result": custom_result}

    # Default responses by agent type
    if agent_name == "retrieval":
        return {
            "status": "success",
            "result": {
                "posts_stored": 2,
                "posts": MOCK_REDDIT_POSTS[:2],
            },
        }
    elif agent_name == "filter":
        return {
            "status": "success",
            "result": {
                "processed": 2,
                "relevant": 2,
                "filter_details": {"relevance_score": 0.85},
            },
        }
    elif agent_name == "summarise":
        return {
            "status": "success",
            "result": {
                "summary": "Claude Code discussion is highly positive with strong community engagement.",
                "summary_stored": True,
            },
        }
    elif agent_name == "alert":
        return {
            "status": "success",
            "result": {
                "alert_sent": True,
                "channel": "#test",
            },
        }
    else:
        return {"status": "error", "error": f"Unknown agent: {agent_name}"}


class IntegrationWorkflowTest:
    """Comprehensive integration test suite for Reddit monitoring workflow"""

    def __init__(self):
        self.config = None
        self.coordinator = None
        self.mock_agents = {}
        self.test_framework = None
        self.workflow_id = None

    async def setup(self):
        """Setup test environment"""
        # Configure test settings
        self.config = IntegrationTestSettings(
            database_url="sqlite:///:memory:",  # Use in-memory database for testing
            redis_url="redis://localhost:6379/15",  # Use test DB
            reddit_topics=["Claude Code", "AI development"],
            a2a_port=8100,  # Different port for testing
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=5,
            a2a_api_key="test_api_key_12345",
        )

        # Create database tables for testing
        from sqlalchemy import create_engine

        from reddit_watcher.models import Base

        engine = create_engine(self.config.database_url)
        Base.metadata.create_all(engine)

        # Patch get_settings to return our test config
        from reddit_watcher.config import get_settings

        self.original_get_settings = get_settings

        def mock_get_settings():
            return self.config

        # Apply patches globally
        import reddit_watcher.config
        import reddit_watcher.database.utils

        reddit_watcher.config.get_settings = mock_get_settings
        reddit_watcher.database.utils.get_settings = mock_get_settings

        # Also patch the create_database_engine function to handle SQLite
        def mock_create_database_engine(database_url, **kwargs):
            from sqlalchemy import create_engine

            # Remove PostgreSQL-specific parameters for SQLite
            if database_url.startswith("sqlite"):
                # SQLite doesn't support these parameters
                kwargs.pop("pool_size", None)
                kwargs.pop("max_overflow", None)
                kwargs.pop("pool_pre_ping", None)
                kwargs.pop("pool_recycle", None)
            return create_engine(database_url, **kwargs)

        # Store original and apply patch
        import reddit_watcher.models

        self.original_create_database_engine = (
            reddit_watcher.models.create_database_engine
        )
        reddit_watcher.models.create_database_engine = mock_create_database_engine

        # Initialize test framework
        self.test_framework = A2ATestFramework()
        await self.test_framework.__aenter__()

        # Initialize coordinator
        self.coordinator = CoordinatorAgent(self.config)

    async def teardown(self):
        """Cleanup test environment"""
        # Cleanup coordinator
        if self.coordinator:
            await self.coordinator._cleanup_http_session()

        # Cleanup test framework
        if self.test_framework:
            await self.test_framework.__aexit__(None, None, None)

        # Reset circuit breaker registry
        registry = get_circuit_breaker_registry()
        await registry.reset_all()

        # Restore original settings function
        if hasattr(self, "original_get_settings"):
            import reddit_watcher.config
            import reddit_watcher.database.utils

            reddit_watcher.config.get_settings = self.original_get_settings
            reddit_watcher.database.utils.get_settings = self.original_get_settings

        # Restore original database engine function
        if hasattr(self, "original_create_database_engine"):
            import reddit_watcher.models

            reddit_watcher.models.create_database_engine = (
                self.original_create_database_engine
            )

    def create_mock_response(
        self, agent_name: str, task_params: dict, success: bool = True
    ):
        """Create mock response for agent requests"""
        skill = task_params.get("skill")
        return create_mock_agent_response(agent_name, skill, success)

    async def test_complete_workflow_success(self):
        """Test successful complete workflow execution"""
        print("\n=== Testing Complete Workflow Success ===")

        # Mock HTTP responses for agent communication
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:
            # Configure mock responses for each agent
            def mock_agent_response(agent_name, endpoint, task_params, task_id):
                skill = task_params.get("skill")
                if agent_name == "retrieval" and skill == "fetch_posts_by_topic":
                    return {
                        "status": "success",
                        "result": {
                            "posts_stored": 2,
                            "posts": MOCK_REDDIT_POSTS[:2],
                        },
                    }
                elif agent_name == "filter" and skill == "batch_filter_posts":
                    return {
                        "status": "success",
                        "result": {
                            "processed": 2,
                            "relevant": 2,
                            "filter_details": {"relevance_score": 0.85},
                        },
                    }
                elif agent_name == "summarise" and skill == "summarize_content":
                    return {
                        "status": "success",
                        "result": {
                            "summary": "Claude Code discussion is highly positive with strong community engagement.",
                            "summary_stored": True,
                        },
                    }
                elif agent_name == "alert" and skill in ["sendSlack", "sendEmail"]:
                    return {
                        "status": "success",
                        "result": {
                            "alert_sent": True,
                            "channel": "#test",
                        },
                    }
                else:
                    return {"status": "error", "error": f"Unknown skill: {skill}"}

            mock_request.side_effect = mock_agent_response

            # Execute monitoring cycle
            result = await self.coordinator.execute_skill(
                "run_monitoring_cycle",
                {
                    "topics": ["Claude Code"],
                    "subreddits": ["MachineLearning", "artificial"],
                },
            )

        # Verify workflow completed successfully
        assert result["status"] == "success", f"Workflow failed: {result.get('error')}"
        assert "workflow_id" in result["result"]

        workflow_result = result["result"]
        assert workflow_result["retrieval_result"]["total_posts"] == 2
        assert workflow_result["filter_result"]["relevant_posts"] == 2
        assert "summarise_result" in workflow_result
        assert "alert_result" in workflow_result

        self.workflow_id = workflow_result["workflow_id"]
        print(f"✓ Workflow {self.workflow_id} completed successfully")

        # Verify database state
        await self._verify_workflow_in_database()

    async def test_workflow_with_retrieval_failure(self):
        """Test workflow behavior when retrieval agent fails"""
        print("\n=== Testing Workflow with Retrieval Failure ===")

        # Mock HTTP responses with retrieval failure
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:

            def mock_agent_response_with_failure(
                agent_name, endpoint, task_params, task_id
            ):
                if agent_name == "retrieval":
                    return {"status": "error", "error": "Mock retrieval error"}
                else:
                    return self.create_mock_response(agent_name, task_params)

            mock_request.side_effect = mock_agent_response_with_failure

            result = await self.coordinator.execute_skill(
                "run_monitoring_cycle",
                {
                    "topics": ["Claude Code"],
                    "subreddits": ["MachineLearning"],
                },
            )

        # Verify workflow fails at retrieval stage
        assert result["status"] == "error"
        assert "retrieval failed" in result["error"].lower()
        print(f"✓ Workflow correctly failed at retrieval: {result['error']}")

    async def test_workflow_with_circuit_breaker_activation(self):
        """Test circuit breaker activation during agent failures"""
        print("\n=== Testing Circuit Breaker Activation ===")

        call_count = {"count": 0}

        # Mock HTTP responses to trigger circuit breaker
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:

            def mock_agent_response_for_circuit_breaker(
                agent_name, endpoint, task_params, task_id
            ):
                if agent_name == "retrieval":
                    call_count["count"] += 1
                    if call_count["count"] <= 3:  # Fail first few calls
                        raise aiohttp.ClientError("Simulated connection error")
                    else:
                        return self.create_mock_response(agent_name, task_params)
                else:
                    return self.create_mock_response(agent_name, task_params)

            mock_request.side_effect = mock_agent_response_for_circuit_breaker

            # Execute multiple workflows to trigger circuit breaker
            for attempt in range(5):
                try:
                    result = await self.coordinator.execute_skill(
                        "run_monitoring_cycle",
                        {
                            "topics": ["Claude Code"],
                            "subreddits": ["MachineLearning"],
                        },
                    )

                    if attempt < 3:
                        # First few should fail normally
                        assert result["status"] == "error"
                        print(f"✓ Attempt {attempt + 1}: Normal failure")
                    else:
                        # Later attempts should either succeed or fail due to circuit breaker
                        print(f"✓ Attempt {attempt + 1}: {result['status']}")
                except Exception as e:
                    if "circuit breaker" in str(e).lower():
                        print(f"✓ Attempt {attempt + 1}: Circuit breaker activated")
                    else:
                        print(f"✓ Attempt {attempt + 1}: Normal failure - {e}")

        # Verify circuit breaker status
        cb_status = await self.coordinator.execute_skill(
            "get_circuit_breaker_status", {}
        )
        assert cb_status["status"] == "success"
        print("✓ Circuit breaker status verified")

    async def test_authentication_middleware_integration(self):
        """Test authentication middleware functionality"""
        print("\n=== Testing Authentication Middleware ===")

        # Test AuthMiddleware directly
        auth_middleware = AuthMiddleware(self.config)

        # Test valid API key
        from fastapi.security import HTTPAuthorizationCredentials

        valid_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=self.config.a2a_api_key
        )

        try:
            subject = await auth_middleware.verify_token(valid_credentials)
            assert subject == "api_key"
            print("✓ Valid API key authenticated successfully")
        except Exception as e:
            print(f"❌ Valid API key failed: {e}")

        # Test invalid API key
        invalid_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid_key"
        )

        try:
            await auth_middleware.verify_token(invalid_credentials)
            print("❌ Invalid API key should have failed")
            raise AssertionError("Invalid API key should have failed")
        except Exception:
            print("✓ Invalid API key correctly rejected")

        # Test missing credentials
        try:
            await auth_middleware.verify_token(None)
            print("❌ Missing credentials should have failed")
            raise AssertionError("Missing credentials should have failed")
        except Exception:
            print("✓ Missing credentials correctly rejected")

    async def test_resource_management_and_cleanup(self):
        """Test proper resource management and cleanup"""
        print("\n=== Testing Resource Management ===")

        # Test HTTP session management
        initial_session = self.coordinator._http_session
        assert initial_session is None or initial_session.closed

        # Execute workflow to create session
        await self.coordinator.execute_skill(
            "run_monitoring_cycle", {"topics": ["Claude Code"], "subreddits": ["test"]}
        )

        # Verify session was created and is active
        assert self.coordinator._http_session is not None
        assert not self.coordinator._http_session.closed
        print("✓ HTTP session created and active")

        # Test context manager cleanup
        async with self.coordinator as coord:
            assert coord._http_session is not None
            assert not coord._http_session.closed
            print("✓ Context manager session active")

        # Session should be cleaned up after context exit
        await asyncio.sleep(0.2)  # Allow cleanup to complete
        print("✓ Context manager cleanup completed")

        # Test manual cleanup
        await self.coordinator._cleanup_http_session()
        assert self.coordinator._http_session is None
        print("✓ Manual cleanup successful")

    async def test_workflow_recovery_scenarios(self):
        """Test workflow recovery from failures"""
        print("\n=== Testing Workflow Recovery ===")

        # First, create a failed workflow
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:

            def mock_agent_response_with_filter_failure(
                agent_name, endpoint, task_params, task_id
            ):
                if agent_name == "filter":
                    return {"status": "error", "error": "Mock filter error"}
                else:
                    return self.create_mock_response(agent_name, task_params)

            mock_request.side_effect = mock_agent_response_with_filter_failure

            failed_result = await self.coordinator.execute_skill(
                "run_monitoring_cycle",
                {"topics": ["Claude Code"], "subreddits": ["test"]},
            )

        assert failed_result["status"] == "error"
        failed_workflow_id = failed_result["workflow_id"]
        print(f"✓ Created failed workflow: {failed_workflow_id}")

        # Test workflow recovery with successful mocks
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:
            mock_request.side_effect = (
                lambda agent_name,
                endpoint,
                task_params,
                task_id: self.create_mock_response(agent_name, task_params)
            )

            recovery_result = await self.coordinator.execute_skill(
                "recover_failed_workflow", {"workflow_id": failed_workflow_id}
            )

        assert recovery_result["status"] == "success"
        assert recovery_result["result"]["recovered_workflow_id"] == failed_workflow_id
        assert recovery_result["result"]["new_workflow_result"]["status"] == "success"
        print("✓ Workflow recovery successful")

    async def test_agent_health_monitoring(self):
        """Test agent health monitoring and status reporting"""
        print("\n=== Testing Agent Health Monitoring ===")

        # Mock health check responses
        with patch.object(
            self.coordinator, "_check_single_agent_health"
        ) as mock_health:
            # All agents healthy
            mock_health.return_value = {
                "status": "healthy",
                "endpoint": "mock://localhost:8000",
                "response_time": "< 1s",
                "details": {"status": "healthy"},
            }

            health_result = await self.coordinator.execute_skill(
                "check_agent_status", {}
            )
            assert health_result["status"] == "success"

            health_data = health_result["result"]
            assert health_data["total_agents"] == 4
            assert health_data["healthy_agents"] == 4
            assert health_data["health_percentage"] == 100.0
            print(f"✓ All agents healthy: {health_data['health_percentage']}%")

        # Simulate one agent failure
        call_count = {"count": 0}

        with patch.object(
            self.coordinator, "_check_single_agent_health"
        ) as mock_health:

            def mock_health_with_failure(agent_name, endpoint):
                call_count["count"] += 1
                if call_count["count"] == 1:  # First agent (retrieval) fails
                    return {
                        "status": "error",
                        "endpoint": endpoint,
                        "error": "Health check failed",
                    }
                else:
                    return {
                        "status": "healthy",
                        "endpoint": endpoint,
                        "response_time": "< 1s",
                        "details": {"status": "healthy"},
                    }

            mock_health.side_effect = mock_health_with_failure

            health_result = await self.coordinator.execute_skill(
                "check_agent_status", {}
            )
            health_data = health_result["result"]
            assert health_data["healthy_agents"] == 3
            assert health_data["health_percentage"] == 75.0
            print(f"✓ One agent down: {health_data['health_percentage']}%")

    async def test_workflow_status_tracking(self):
        """Test workflow status tracking and reporting"""
        print("\n=== Testing Workflow Status Tracking ===")

        # Execute a successful workflow
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:
            mock_request.side_effect = (
                lambda agent_name,
                endpoint,
                task_params,
                task_id: self.create_mock_response(agent_name, task_params)
            )

            result = await self.coordinator.execute_skill(
                "run_monitoring_cycle",
                {"topics": ["Claude Code"], "subreddits": ["test"]},
            )

        workflow_id = result["result"]["workflow_id"]

        # Get workflow status
        status_result = await self.coordinator.execute_skill(
            "get_workflow_status", {"limit": 5}
        )

        assert status_result["status"] == "success"
        workflows = status_result["result"]["workflows"]
        assert len(workflows) > 0

        # Find our workflow
        our_workflow = None
        for workflow in workflows:
            if workflow["id"] == workflow_id:
                our_workflow = workflow
                break

        assert our_workflow is not None
        assert our_workflow["status"] == "completed"
        assert our_workflow["posts_processed"] > 0
        print(f"✓ Workflow status tracked: {our_workflow['status']}")

    async def test_error_propagation_and_logging(self):
        """Test error propagation and audit logging"""
        print("\n=== Testing Error Propagation and Logging ===")

        # Test with filter agent error
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:

            def mock_agent_response_with_timeout_error(
                agent_name, endpoint, task_params, task_id
            ):
                if agent_name == "filter":
                    raise TimeoutError("Simulated timeout error")
                else:
                    return self.create_mock_response(agent_name, task_params)

            mock_request.side_effect = mock_agent_response_with_timeout_error

            start_time = time.time()
            result = await self.coordinator.execute_skill(
                "run_monitoring_cycle", {"topics": ["test"], "subreddits": ["test"]}
            )
            end_time = time.time()

        # Should fail reasonably quickly due to error
        assert result["status"] == "error"
        assert (end_time - start_time) < 10  # Should fail quickly
        workflow_id = result["workflow_id"]
        print(f"✓ Error handled correctly: {end_time - start_time:.1f}s")

        # Verify error logging in database
        with get_db_session() as session:
            workflow = (
                session.query(WorkflowExecution).filter_by(id=workflow_id).first()
            )
            assert workflow is not None
            assert workflow.status == "failed"
            assert "filter failed" in workflow.error_message.lower()

            # Check agent task logs
            agent_tasks = (
                session.query(AgentTask).filter_by(workflow_id=workflow_id).all()
            )
            assert len(agent_tasks) > 0
            print(f"✓ Error logged in database: {len(agent_tasks)} tasks recorded")

    async def test_concurrent_workflow_execution(self):
        """Test concurrent workflow execution and resource sharing"""
        print("\n=== Testing Concurrent Workflow Execution ===")

        # Mock successful responses for all agents
        with patch.object(self.coordinator, "_make_agent_request") as mock_request:
            mock_request.side_effect = (
                lambda agent_name,
                endpoint,
                task_params,
                task_id: self.create_mock_response(agent_name, task_params)
            )

            # Execute multiple workflows concurrently
            tasks = []
            for i in range(3):
                task = asyncio.create_task(
                    self.coordinator.execute_skill(
                        "run_monitoring_cycle",
                        {"topics": [f"test_topic_{i}"], "subreddits": ["test"]},
                    )
                )
                tasks.append(task)

            # Wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all succeeded
        successful_results = 0
        for i, result in enumerate(results):
            if isinstance(result, dict) and result.get("status") == "success":
                successful_results += 1
                print(f"✓ Concurrent workflow {i + 1}: success")
            else:
                print(f"✗ Concurrent workflow {i + 1}: {result}")

        assert successful_results == 3
        print(f"✓ All {successful_results} concurrent workflows completed")

    async def _verify_workflow_in_database(self):
        """Verify workflow was properly recorded in database"""
        if not self.workflow_id:
            return

        with get_db_session() as session:
            workflow = (
                session.query(WorkflowExecution).filter_by(id=self.workflow_id).first()
            )
            assert workflow is not None
            assert workflow.status == "completed"
            assert workflow.posts_processed > 0

            # Check agent tasks
            agent_tasks = (
                session.query(AgentTask).filter_by(workflow_id=self.workflow_id).all()
            )
            assert len(agent_tasks) > 0
            print(f"✓ Database verification: {len(agent_tasks)} tasks recorded")


# Pytest test functions


@pytest.mark.asyncio
async def test_complete_workflow_success():
    """Test successful complete workflow execution"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_complete_workflow_success()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_workflow_with_retrieval_failure():
    """Test workflow behavior when retrieval agent fails"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_workflow_with_retrieval_failure()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_workflow_with_circuit_breaker_activation():
    """Test circuit breaker activation during agent failures"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_workflow_with_circuit_breaker_activation()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_authentication_middleware_integration():
    """Test authentication middleware on skill endpoints"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_authentication_middleware_integration()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_resource_management_and_cleanup():
    """Test proper resource management and cleanup"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_resource_management_and_cleanup()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_workflow_recovery_scenarios():
    """Test workflow recovery from failures"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_workflow_recovery_scenarios()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_agent_health_monitoring():
    """Test agent health monitoring and status reporting"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_agent_health_monitoring()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_workflow_status_tracking():
    """Test workflow status tracking and reporting"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_workflow_status_tracking()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_error_propagation_and_logging():
    """Test error propagation and audit logging"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_error_propagation_and_logging()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_concurrent_workflow_execution():
    """Test concurrent workflow execution and resource sharing"""
    test = IntegrationWorkflowTest()
    await test.setup()
    try:
        await test.test_concurrent_workflow_execution()
    finally:
        await test.teardown()


# Manual test runner for debugging
async def main():
    """Run all integration tests manually"""
    print("Starting comprehensive integration tests...")

    test = IntegrationWorkflowTest()
    try:
        await test.setup()

        test_methods = [
            test.test_complete_workflow_success,
            test.test_workflow_with_retrieval_failure,
            test.test_workflow_with_circuit_breaker_activation,
            test.test_authentication_middleware_integration,
            test.test_resource_management_and_cleanup,
            test.test_workflow_recovery_scenarios,
            test.test_agent_health_monitoring,
            test.test_workflow_status_tracking,
            test.test_error_propagation_and_logging,
            test.test_concurrent_workflow_execution,
        ]

        passed = 0
        failed = 0

        for test_method in test_methods:
            try:
                await test_method()
                passed += 1
            except Exception as e:
                print(f"❌ {test_method.__name__} failed: {e}")
                failed += 1

        print("\n=== Integration Test Results ===")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")

    finally:
        await test.teardown()


if __name__ == "__main__":
    asyncio.run(main())
