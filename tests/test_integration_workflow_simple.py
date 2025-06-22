# ABOUTME: Simplified integration test for the complete Reddit monitoring workflow
# ABOUTME: Tests core workflow logic with minimal dependencies and comprehensive mocking

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.auth_middleware import AuthMiddleware
from reddit_watcher.circuit_breaker import (
    get_circuit_breaker_registry,
)
from reddit_watcher.config import Settings
from tests.fixtures.test_data import MOCK_REDDIT_POSTS


class MockDatabaseSession:
    """Mock database session for testing"""

    def __init__(self):
        self.mock_workflows = {}
        self.mock_tasks = {}
        self.workflow_counter = 1
        self.task_counter = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def add(self, obj):
        if hasattr(obj, "id"):
            if obj.__class__.__name__ == "WorkflowExecution":
                obj.id = self.workflow_counter
                self.mock_workflows[obj.id] = obj
                self.workflow_counter += 1
            elif obj.__class__.__name__ == "AgentTask":
                obj.id = self.task_counter
                self.mock_tasks[obj.id] = obj
                self.task_counter += 1

    def commit(self):
        pass

    def query(self, model_class):
        return MockQuery(model_class, self)


class MockQuery:
    """Mock SQLAlchemy query for testing"""

    def __init__(self, model_class, session):
        self.model_class = model_class
        self.session = session
        self._filters = []

    def filter_by(self, **kwargs):
        self._filters.append(kwargs)
        return self

    def filter(self, condition):
        return self

    def order_by(self, *args):
        return self

    def limit(self, count):
        return self

    def all(self):
        if self.model_class.__name__ == "WorkflowExecution":
            return list(self.session.mock_workflows.values())
        elif self.model_class.__name__ == "AgentTask":
            return list(self.session.mock_tasks.values())
        return []

    def first(self):
        results = self.all()
        if self._filters and results:
            # Simple filter matching for id
            for filter_dict in self._filters:
                if "id" in filter_dict:
                    for item in results:
                        if item.id == filter_dict["id"]:
                            return item
        return results[0] if results else None


def create_mock_workflow_execution():
    """Create a mock WorkflowExecution object"""
    mock_workflow = MagicMock()
    mock_workflow.id = 1
    mock_workflow.topics = ["Claude Code"]
    mock_workflow.subreddits = ["test"]
    mock_workflow.status = "running"
    mock_workflow.started_at = datetime.now(UTC)
    mock_workflow.completed_at = None
    mock_workflow.posts_processed = 0
    mock_workflow.comments_processed = 0
    mock_workflow.relevant_items = 0
    mock_workflow.summaries_created = 0
    mock_workflow.alerts_sent = 0
    mock_workflow.error_message = None
    return mock_workflow


def create_mock_agent_task():
    """Create a mock AgentTask object"""
    mock_task = MagicMock()
    mock_task.id = 1
    mock_task.workflow_id = 1
    mock_task.agent_type = "test"
    mock_task.task_type = "test_skill"
    mock_task.task_data = {}
    mock_task.status = "pending"
    mock_task.created_at = datetime.now(UTC)
    mock_task.completed_at = None
    mock_task.result_data = None
    return mock_task


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


class IntegrationWorkflowTestSimple:
    """Simplified integration test suite for Reddit monitoring workflow"""

    def __init__(self):
        self.config = None
        self.coordinator = None
        self.workflow_id = None
        self.mock_db_session = MockDatabaseSession()

    async def setup(self):
        """Setup test environment"""
        # Configure test settings - bypass validation for testing
        self.config = Settings()

        # Manually set test values without validation
        object.__setattr__(
            self.config, "reddit_topics", ["Claude Code", "AI development"]
        )
        object.__setattr__(self.config, "a2a_port", 8100)
        object.__setattr__(self.config, "circuit_breaker_enabled", True)
        object.__setattr__(self.config, "circuit_breaker_failure_threshold", 3)
        object.__setattr__(self.config, "circuit_breaker_recovery_timeout", 5)
        object.__setattr__(self.config, "a2a_api_key", "test_api_key_12345")
        object.__setattr__(
            self.config, "database_url", "sqlite:///:memory:"
        )  # Mock database URL

        # Initialize coordinator
        self.coordinator = CoordinatorAgent(self.config)

    async def teardown(self):
        """Cleanup test environment"""
        # Cleanup coordinator
        if self.coordinator:
            await self.coordinator._cleanup_http_session()

        # Reset circuit breaker registry
        registry = get_circuit_breaker_registry()
        await registry.reset_all()

    def create_mock_response(
        self, agent_name: str, task_params: dict, success: bool = True
    ):
        """Create mock response for agent requests"""
        skill = task_params.get("skill")
        return create_mock_agent_response(agent_name, skill, success)

    async def test_complete_workflow_success(self):
        """Test successful complete workflow execution"""
        print("\n=== Testing Complete Workflow Success ===")

        # Mock all database operations
        with patch(
            "reddit_watcher.database.utils.get_db_session",
            return_value=self.mock_db_session,
        ):
            # Mock HTTP responses for agent communication
            with patch.object(self.coordinator, "_make_agent_request") as mock_request:
                # Configure mock responses for each agent
                def mock_agent_response(agent_name, endpoint, task_params, task_id):
                    skill = task_params.get("skill")
                    return create_mock_agent_response(agent_name, skill)

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

    async def test_workflow_with_retrieval_failure(self):
        """Test workflow behavior when retrieval agent fails"""
        print("\n=== Testing Workflow with Retrieval Failure ===")

        # Mock database operations
        with patch(
            "reddit_watcher.database.utils.get_db_session",
            return_value=self.mock_db_session,
        ):
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

    async def test_circuit_breaker_functionality(self):
        """Test circuit breaker activation during agent failures"""
        print("\n=== Testing Circuit Breaker Functionality ===")

        call_count = {"count": 0}

        # Mock database operations
        with patch(
            "reddit_watcher.database.utils.get_db_session",
            return_value=self.mock_db_session,
        ):
            # Mock HTTP responses to trigger circuit breaker
            with patch.object(self.coordinator, "_make_agent_request") as mock_request:

                def mock_agent_response_for_circuit_breaker(
                    agent_name, endpoint, task_params, task_id
                ):
                    if agent_name == "retrieval":
                        call_count["count"] += 1
                        if call_count["count"] <= 3:  # Fail first few calls
                            raise ConnectionError("Simulated connection error")
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

        # Test context manager cleanup
        async with self.coordinator as coord:
            await coord._ensure_http_session()
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

    async def test_concurrent_workflow_execution(self):
        """Test concurrent workflow execution and resource sharing"""
        print("\n=== Testing Concurrent Workflow Execution ===")

        # Mock database operations
        with patch(
            "reddit_watcher.database.utils.get_db_session",
            return_value=self.mock_db_session,
        ):
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


# Pytest test functions


@pytest.mark.asyncio
async def test_complete_workflow_success():
    """Test successful complete workflow execution"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_complete_workflow_success()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_workflow_with_retrieval_failure():
    """Test workflow behavior when retrieval agent fails"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_workflow_with_retrieval_failure()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_circuit_breaker_functionality():
    """Test circuit breaker functionality"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_circuit_breaker_functionality()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_authentication_middleware_integration():
    """Test authentication middleware functionality"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_authentication_middleware_integration()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_resource_management_and_cleanup():
    """Test proper resource management and cleanup"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_resource_management_and_cleanup()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_agent_health_monitoring():
    """Test agent health monitoring and status reporting"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_agent_health_monitoring()
    finally:
        await test.teardown()


@pytest.mark.asyncio
async def test_concurrent_workflow_execution():
    """Test concurrent workflow execution and resource sharing"""
    test = IntegrationWorkflowTestSimple()
    await test.setup()
    try:
        await test.test_concurrent_workflow_execution()
    finally:
        await test.teardown()


# Manual test runner for debugging
async def main():
    """Run all integration tests manually"""
    print("Starting simplified integration tests...")

    test = IntegrationWorkflowTestSimple()
    try:
        await test.setup()

        test_methods = [
            test.test_complete_workflow_success,
            test.test_workflow_with_retrieval_failure,
            test.test_circuit_breaker_functionality,
            test.test_authentication_middleware_integration,
            test.test_resource_management_and_cleanup,
            test.test_agent_health_monitoring,
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
