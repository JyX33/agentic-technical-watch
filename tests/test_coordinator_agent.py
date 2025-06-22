# ABOUTME: Comprehensive tests for CoordinatorAgent workflow orchestration
# ABOUTME: Tests A2A delegation, error handling, retries, and workflow state management

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from aioresponses import aioresponses

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.models import (
    WorkflowExecution,
)


class TestCoordinatorAgent:
    """Test suite for CoordinatorAgent functionality."""

    @pytest.fixture
    def coordinator_agent(self):
        """Create a CoordinatorAgent instance for testing."""
        agent = CoordinatorAgent()
        return agent

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch("reddit_watcher.agents.coordinator_agent.get_db_session") as mock:
            session_mock = MagicMock()
            mock.return_value.__enter__.return_value = session_mock
            mock.return_value.__exit__.return_value = None
            yield session_mock

    @pytest.fixture
    def sample_workflow_execution(self):
        """Sample workflow execution for testing."""
        return WorkflowExecution(
            id=1,
            topics=["Claude Code", "AI"],
            subreddits=["all"],
            status="running",
            started_at=datetime.now(UTC),
            posts_processed=0,
            comments_processed=0,
        )

    @pytest.fixture
    def sample_reddit_posts(self):
        """Sample Reddit posts for testing."""
        # Create mock objects for testing instead of real SQLAlchemy objects
        post1 = MagicMock()
        post1.id = 1
        post1.post_id = "test_post_1"
        post1.title = "Test Post 1"
        post1.content = "Content about Claude Code"
        post1.subreddit = "test"
        post1.author = "testuser1"
        post1.created_at = datetime.now(UTC)

        post2 = MagicMock()
        post2.id = 2
        post2.post_id = "test_post_2"
        post2.title = "Test Post 2"
        post2.content = "Another test post"
        post2.subreddit = "test"
        post2.author = "testuser2"
        post2.created_at = datetime.now(UTC)

        return [post1, post2]

    def test_agent_initialization(self, coordinator_agent):
        """Test proper agent initialization."""
        assert coordinator_agent.agent_type == "coordinator"
        assert coordinator_agent.name == "Workflow Coordinator Agent"
        assert coordinator_agent.version == "1.0.0"
        assert len(coordinator_agent._agent_endpoints) == 4
        assert "retrieval" in coordinator_agent._agent_endpoints
        assert "filter" in coordinator_agent._agent_endpoints
        assert "summarise" in coordinator_agent._agent_endpoints
        assert "alert" in coordinator_agent._agent_endpoints

    def test_get_skills(self, coordinator_agent):
        """Test that agent returns correct skills."""
        skills = coordinator_agent.get_skills()
        skill_names = [skill.name for skill in skills]

        expected_skills = [
            "health_check",
            "run_monitoring_cycle",
            "check_agent_status",
            "recover_failed_workflow",
            "get_workflow_status",
        ]

        for expected_skill in expected_skills:
            assert expected_skill in skill_names

        # Check skill structure
        for skill in skills:
            assert hasattr(skill, "id")
            assert hasattr(skill, "name")
            assert hasattr(skill, "description")
            assert hasattr(skill, "tags")

    @pytest.mark.asyncio
    async def test_health_check_basic(self, coordinator_agent, mock_db_session):
        """Test basic health check functionality."""
        # Mock recent workflow query
        mock_db_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        with aioresponses() as m:
            # Mock agent health endpoints
            for agent_name, endpoint in coordinator_agent._agent_endpoints.items():
                m.get(
                    f"{endpoint}/health",
                    payload={"status": "healthy", "agent": agent_name},
                )

            result = await coordinator_agent.execute_skill("health_check", {})

            assert result["status"] == "success"
            assert "result" in result
            assert "coordinator_specific" in result["result"]
            assert "agent_status" in result["result"]["coordinator_specific"]

    @pytest.mark.asyncio
    async def test_health_check_agent_failures(
        self, coordinator_agent, mock_db_session
    ):
        """Test health check with agent failures."""
        # Mock recent workflow query
        mock_db_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        with aioresponses() as m:
            # Mock healthy agents
            m.get(
                f"{coordinator_agent._agent_endpoints['retrieval']}/health",
                payload={"status": "healthy"},
            )
            m.get(
                f"{coordinator_agent._agent_endpoints['filter']}/health",
                payload={"status": "healthy"},
            )

            # Mock failing agents
            m.get(
                f"{coordinator_agent._agent_endpoints['summarise']}/health",
                status=500,
            )
            m.get(
                f"{coordinator_agent._agent_endpoints['alert']}/health",
                exception=TimeoutError(),
            )

            result = await coordinator_agent.execute_skill("health_check", {})

            assert result["status"] == "success"
            agent_status = result["result"]["coordinator_specific"]["agent_status"]

            assert agent_status["retrieval"]["status"] == "healthy"
            assert agent_status["filter"]["status"] == "healthy"
            assert agent_status["summarise"]["status"] == "unhealthy"
            assert agent_status["alert"]["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_check_agent_status(self, coordinator_agent):
        """Test agent status checking skill."""
        with aioresponses() as m:
            # Mock all agents as healthy
            for endpoint in coordinator_agent._agent_endpoints.values():
                m.get(f"{endpoint}/health", payload={"status": "healthy"})

            result = await coordinator_agent.execute_skill("check_agent_status", {})

            assert result["status"] == "success"
            assert result["result"]["total_agents"] == 4
            assert result["result"]["healthy_agents"] == 4
            assert result["result"]["health_percentage"] == 100.0

    @pytest.mark.asyncio
    async def test_create_workflow_execution(self, coordinator_agent, mock_db_session):
        """Test workflow execution creation."""
        # Mock workflow creation
        mock_workflow = MagicMock()
        mock_workflow.id = 123
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        # Mock the WorkflowExecution constructor to return our mock
        with patch(
            "reddit_watcher.agents.coordinator_agent.WorkflowExecution"
        ) as mock_wf_class:
            mock_wf_class.return_value = mock_workflow

            workflow_id = await coordinator_agent._create_workflow_execution(
                ["Claude Code"], ["all"]
            )

            assert workflow_id == 123
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_workflow_event(self, coordinator_agent, mock_db_session):
        """Test workflow event logging."""
        # Mock agent task creation
        mock_task = MagicMock()
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        with patch(
            "reddit_watcher.agents.coordinator_agent.AgentTask"
        ) as mock_task_class:
            mock_task_class.return_value = mock_task

            await coordinator_agent._log_workflow_event(
                1, "test_event", {"test": "data"}
            )

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegate_to_agent_success(self, coordinator_agent, mock_db_session):
        """Test successful agent delegation."""
        # Mock task creation
        mock_task = MagicMock()
        mock_task.id = 456
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        with patch(
            "reddit_watcher.agents.coordinator_agent.AgentTask"
        ) as mock_task_class:
            mock_task_class.return_value = mock_task

            with aioresponses() as m:
                # Mock successful agent response
                m.post(
                    f"{coordinator_agent._agent_endpoints['retrieval']}/execute",
                    payload={"status": "success", "result": {"posts_found": 5}},
                )

                # Mock task update query
                mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_task

                task_params = {
                    "skill": "fetch_posts_by_topic",
                    "parameters": {"topic": "test"},
                }

                result = await coordinator_agent._delegate_to_agent(
                    "retrieval", task_params, 1
                )

                assert result["status"] == "success"
                assert result["result"]["posts_found"] == 5

    @pytest.mark.asyncio
    async def test_delegate_to_agent_with_retries(
        self, coordinator_agent, mock_db_session
    ):
        """Test agent delegation with retry logic."""
        # Mock task creation and updates
        mock_task = MagicMock()
        mock_task.id = 456
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            mock_task
        )

        with patch(
            "reddit_watcher.agents.coordinator_agent.AgentTask"
        ) as mock_task_class:
            mock_task_class.return_value = mock_task

            with aioresponses() as m:
                endpoint = f"{coordinator_agent._agent_endpoints['retrieval']}/execute"

                # First two attempts fail, third succeeds
                m.post(endpoint, status=500)
                m.post(endpoint, status=500)
                m.post(
                    endpoint,
                    payload={"status": "success", "result": {"posts_found": 3}},
                )

                # Reduce retry delay for testing
                coordinator_agent._retry_delay = 0.1

                task_params = {
                    "skill": "fetch_posts_by_topic",
                    "parameters": {"topic": "test"},
                }

                result = await coordinator_agent._delegate_to_agent(
                    "retrieval", task_params, 1
                )

                assert result["status"] == "success"
                assert result["result"]["posts_found"] == 3

    @pytest.mark.asyncio
    async def test_delegate_to_agent_max_retries_exceeded(
        self, coordinator_agent, mock_db_session
    ):
        """Test agent delegation when max retries are exceeded."""
        # Mock task creation and updates
        mock_task = MagicMock()
        mock_task.id = 456
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            mock_task
        )

        with patch(
            "reddit_watcher.agents.coordinator_agent.AgentTask"
        ) as mock_task_class:
            mock_task_class.return_value = mock_task

            with aioresponses() as m:
                endpoint = f"{coordinator_agent._agent_endpoints['retrieval']}/execute"

                # All attempts fail
                for _ in range(coordinator_agent._max_retries + 1):
                    m.post(endpoint, status=500)

                # Reduce retry delay for testing
                coordinator_agent._retry_delay = 0.1

                task_params = {
                    "skill": "fetch_posts_by_topic",
                    "parameters": {"topic": "test"},
                }

                result = await coordinator_agent._delegate_to_agent(
                    "retrieval", task_params, 1
                )

                assert result["status"] == "error"
                assert "HTTP 500" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_retrieval_tasks(self, coordinator_agent, mock_db_session):
        """Test retrieval task execution."""
        with aioresponses() as m:
            # Mock successful retrieval responses
            endpoint = f"{coordinator_agent._agent_endpoints['retrieval']}/execute"
            m.post(
                endpoint,
                payload={
                    "status": "success",
                    "result": {
                        "posts_found": 5,
                        "posts_stored": 5,
                        "posts": [{"id": "post1"}, {"id": "post2"}],
                    },
                },
            )

            # Mock task creation
            with patch("reddit_watcher.agents.coordinator_agent.AgentTask"):
                mock_db_session.add.return_value = None
                mock_db_session.commit.return_value = None

                result = await coordinator_agent._execute_retrieval_tasks(
                    1, ["Claude Code"], ["all"]
                )

                assert result["status"] == "success"
                assert result["result"]["total_posts"] == 5

    @pytest.mark.asyncio
    async def test_execute_filter_tasks(
        self, coordinator_agent, mock_db_session, sample_reddit_posts
    ):
        """Test filter task execution."""
        # Mock database query for recent posts
        mock_db_session.query.return_value.filter.return_value.all.return_value = (
            sample_reddit_posts
        )

        with aioresponses() as m:
            # Mock successful filter response
            endpoint = f"{coordinator_agent._agent_endpoints['filter']}/execute"
            m.post(
                endpoint,
                payload={
                    "status": "success",
                    "result": {
                        "processed": 2,
                        "relevant": 1,
                        "details": {"relevant_posts": 1},
                    },
                },
            )

            # Mock task creation
            with patch("reddit_watcher.agents.coordinator_agent.AgentTask"):
                mock_db_session.add.return_value = None
                mock_db_session.commit.return_value = None

                retrieval_result = {"total_posts": 2}
                result = await coordinator_agent._execute_filter_tasks(
                    1, retrieval_result
                )

                assert result["status"] == "success"
                assert result["result"]["relevant_posts"] == 1

    @pytest.mark.asyncio
    async def test_execute_filter_tasks_no_posts(self, coordinator_agent):
        """Test filter task execution with no posts."""
        retrieval_result = {"total_posts": 0}
        result = await coordinator_agent._execute_filter_tasks(1, retrieval_result)

        assert result["status"] == "success"
        assert result["result"]["relevant_posts"] == 0
        assert result["result"]["relevant_comments"] == 0

    @pytest.mark.asyncio
    async def test_run_monitoring_cycle_success(
        self, coordinator_agent, mock_db_session
    ):
        """Test successful complete monitoring cycle."""
        # Mock workflow creation
        mock_workflow = MagicMock()
        mock_workflow.id = 100

        with patch(
            "reddit_watcher.agents.coordinator_agent.WorkflowExecution"
        ) as mock_wf_class:
            mock_wf_class.return_value = mock_workflow
            mock_db_session.add.return_value = None
            mock_db_session.commit.return_value = None

            # Mock database queries
            mock_db_session.query.return_value.filter.return_value.all.return_value = []
            mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_workflow

            with aioresponses() as m:
                # Mock all agent responses
                retrieval_endpoint = (
                    f"{coordinator_agent._agent_endpoints['retrieval']}/execute"
                )
                filter_endpoint = (
                    f"{coordinator_agent._agent_endpoints['filter']}/execute"
                )
                summarise_endpoint = (
                    f"{coordinator_agent._agent_endpoints['summarise']}/execute"
                )
                alert_endpoint = (
                    f"{coordinator_agent._agent_endpoints['alert']}/execute"
                )

                m.post(
                    retrieval_endpoint,
                    payload={
                        "status": "success",
                        "result": {"posts_found": 3, "posts_stored": 3, "posts": []},
                    },
                )
                m.post(
                    filter_endpoint,
                    payload={
                        "status": "success",
                        "result": {"relevant": 1, "processed": 3},
                    },
                )
                m.post(
                    summarise_endpoint,
                    payload={"status": "success", "result": {"summaries_created": 1}},
                )
                m.post(
                    alert_endpoint,
                    payload={"status": "success", "result": {"alerts_sent": 1}},
                )

                # Mock task creation for all delegation calls
                with patch(
                    "reddit_watcher.agents.coordinator_agent.AgentTask"
                ) as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = 789
                    mock_task_class.return_value = mock_task
                    mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_task

                    result = await coordinator_agent.execute_skill(
                        "run_monitoring_cycle", {"topics": ["Claude Code"]}
                    )

                    # Debug output
                    if result["status"] != "success":
                        print(f"Result: {result}")

                    assert result["status"] == "success"
                    assert "workflow_id" in result["result"]
                    assert result["result"]["topics"] == ["Claude Code"]

    @pytest.mark.asyncio
    async def test_run_monitoring_cycle_retrieval_failure(
        self, coordinator_agent, mock_db_session
    ):
        """Test monitoring cycle with retrieval failure."""
        # Mock workflow creation
        mock_workflow = MagicMock()
        mock_workflow.id = 100

        with patch(
            "reddit_watcher.agents.coordinator_agent.WorkflowExecution"
        ) as mock_wf_class:
            mock_wf_class.return_value = mock_workflow
            mock_db_session.add.return_value = None
            mock_db_session.commit.return_value = None
            mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_workflow

            with aioresponses() as m:
                # Mock failed retrieval response
                retrieval_endpoint = (
                    f"{coordinator_agent._agent_endpoints['retrieval']}/execute"
                )
                m.post(retrieval_endpoint, status=500)

                # Mock task creation
                with patch(
                    "reddit_watcher.agents.coordinator_agent.AgentTask"
                ) as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = 789
                    mock_task_class.return_value = mock_task
                    mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_task

                    # Reduce retry delay for testing
                    coordinator_agent._retry_delay = 0.1

                    result = await coordinator_agent.execute_skill(
                        "run_monitoring_cycle", {"topics": ["Claude Code"]}
                    )

                    # Debug output
                    if result["status"] != "error":
                        print(f"Result: {result}")

                    assert result["status"] == "error"
                    assert "Retrieval failed" in result["error"]
                    assert "workflow_id" in result

    @pytest.mark.asyncio
    async def test_get_workflow_status(
        self, coordinator_agent, mock_db_session, sample_workflow_execution
    ):
        """Test getting workflow status."""
        # Mock workflow query
        sample_workflow_execution.completed_at = datetime.now(UTC)
        mock_db_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_workflow_execution
        ]

        result = await coordinator_agent.execute_skill("get_workflow_status", {})

        assert result["status"] == "success"
        assert "workflows" in result["result"]
        assert len(result["result"]["workflows"]) == 1
        assert result["result"]["workflows"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_recover_failed_workflow(self, coordinator_agent, mock_db_session):
        """Test workflow recovery."""
        # Mock failed workflow
        failed_workflow = MagicMock()
        failed_workflow.id = 1
        failed_workflow.status = "failed"
        failed_workflow.topics = ["Claude Code"]
        failed_workflow.subreddits = ["all"]

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            failed_workflow
        )
        mock_db_session.commit.return_value = None

        # Mock the run_monitoring_cycle call
        with patch.object(coordinator_agent, "_run_monitoring_cycle") as mock_run:
            mock_run.return_value = {
                "status": "success",
                "result": {"workflow_id": 2, "completed_at": "2023-01-01T00:00:00Z"},
            }

            result = await coordinator_agent.execute_skill(
                "recover_failed_workflow", {"workflow_id": 1}
            )

            assert result["status"] == "success"
            assert result["result"]["recovered_workflow_id"] == 1
            assert "new_workflow_result" in result["result"]
            assert failed_workflow.status == "recovered"

    @pytest.mark.asyncio
    async def test_recover_failed_workflow_not_found(
        self, coordinator_agent, mock_db_session
    ):
        """Test workflow recovery with non-existent workflow."""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            None
        )

        result = await coordinator_agent.execute_skill(
            "recover_failed_workflow", {"workflow_id": 999}
        )

        assert result["status"] == "error"
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_recover_workflow_not_failed(
        self, coordinator_agent, mock_db_session
    ):
        """Test workflow recovery with non-failed workflow."""
        successful_workflow = MagicMock()
        successful_workflow.status = "completed"

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            successful_workflow
        )

        result = await coordinator_agent.execute_skill(
            "recover_failed_workflow", {"workflow_id": 1}
        )

        assert result["status"] == "error"
        assert "not in failed state" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_skill_unknown_skill(self, coordinator_agent):
        """Test execution of unknown skill."""
        with pytest.raises(ValueError, match="Unknown skill"):
            await coordinator_agent.execute_skill("unknown_skill", {})

    def test_get_health_status(self, coordinator_agent):
        """Test health status retrieval."""
        health_status = coordinator_agent.get_health_status()

        assert "coordinator_specific" in health_status
        coordinator_health = health_status["coordinator_specific"]

        assert "managed_agents" in coordinator_health
        assert "http_session_active" in coordinator_health
        assert "retry_configuration" in coordinator_health

        retry_config = coordinator_health["retry_configuration"]
        assert "max_retries" in retry_config
        assert "retry_delay" in retry_config
        assert "timeout" in retry_config

    @pytest.mark.asyncio
    async def test_context_manager(self, coordinator_agent):
        """Test async context manager functionality."""
        async with coordinator_agent as agent:
            assert agent is coordinator_agent
            assert coordinator_agent._http_session is not None

        # Session should be cleaned up after context exit
        # Note: In real usage, this would close the session
        # For testing, we just verify the context manager works

    @pytest.mark.asyncio
    async def test_run_monitoring_cycle_no_topics(self, coordinator_agent):
        """Test monitoring cycle with no topics configured."""
        result = await coordinator_agent.execute_skill(
            "run_monitoring_cycle", {"topics": []}
        )

        assert result["status"] == "error"
        assert "No topics configured" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_summarise_tasks_no_relevant_posts(self, coordinator_agent):
        """Test summarisation with no relevant posts."""
        filter_result = {"relevant_posts": 0}
        result = await coordinator_agent._execute_summarise_tasks(1, filter_result)

        assert result["status"] == "success"
        assert result["result"]["summaries_created"] == 0

    @pytest.mark.asyncio
    async def test_execute_alert_tasks_no_relevant_posts(self, coordinator_agent):
        """Test alerts with no relevant posts."""
        filter_result = {"relevant_posts": 0}
        result = await coordinator_agent._execute_alert_tasks(1, filter_result, None)

        assert result["status"] == "success"
        assert result["result"]["alerts_sent"] == 0
