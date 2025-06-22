# ABOUTME: Comprehensive tests for A2A idempotency and state management features
# ABOUTME: Tests task deduplication, agent coordination, and recovery procedures

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from reddit_watcher.agent_coordination import (
    AgentCoordinator,
    WorkflowCoordinator,
)
from reddit_watcher.idempotency import (
    acquire_task_lock,
    check_content_duplication,
    cleanup_expired_locks,
    create_idempotent_task,
    create_task_recovery,
    find_duplicate_task,
    generate_content_hash,
    generate_parameters_hash,
    get_agent_states,
    get_pending_recoveries,
    register_content_processing,
    release_task_lock,
    update_agent_state,
)
from reddit_watcher.models import (
    Base,
    ContentType,
    TaskStatus,
)
from reddit_watcher.task_recovery import (
    RecoveryStrategy,
    TaskRecoveryManager,
)


@pytest.fixture
def db_session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestContentHashing:
    """Test content hashing functionality."""

    def test_generate_content_hash_dict(self):
        """Test hashing dictionary content."""
        content = {"key": "value", "number": 42}
        hash1 = generate_content_hash(content)
        hash2 = generate_content_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_generate_content_hash_string(self):
        """Test hashing string content."""
        content = "test string"
        hash1 = generate_content_hash(content)
        hash2 = generate_content_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_generate_content_hash_order_independence(self):
        """Test that dict key order doesn't affect hash."""
        content1 = {"a": 1, "b": 2}
        content2 = {"b": 2, "a": 1}
        assert generate_content_hash(content1) == generate_content_hash(content2)

    def test_generate_parameters_hash(self):
        """Test parameters hash generation."""
        params = {"agent_type": "test", "skill": "test_skill"}
        hash_val = generate_parameters_hash(params)
        assert len(hash_val) == 64


class TestContentDeduplication:
    """Test content deduplication functionality."""

    def test_check_content_duplication_not_found(self, db_session):
        """Test checking for non-existent content."""
        result = check_content_duplication(db_session, ContentType.POST, "test_id_123")
        assert result is None

    def test_register_and_check_content_processing(self, db_session):
        """Test registering and checking content processing."""
        content_hash = "abcd1234" * 8  # 64 chars

        # Register content
        dedup_record = register_content_processing(
            db_session,
            ContentType.POST,
            "test_post_123",
            content_hash,
            "retrieval_agent",
            "workflow_456",
            {"source": "reddit"},
        )

        assert dedup_record.content_type == ContentType.POST
        assert dedup_record.external_id == "test_post_123"
        assert dedup_record.content_hash == content_hash
        assert dedup_record.processing_status == "processing"

        # Check for duplicate
        found_record = check_content_duplication(
            db_session, ContentType.POST, "test_post_123", content_hash
        )

        assert found_record is not None
        assert found_record.id == dedup_record.id

    def test_register_content_processing_duplicate_prevention(self, db_session):
        """Test that duplicate content registration is prevented."""
        content_hash = "efgh5678" * 8

        # Register first time
        register_content_processing(
            db_session, ContentType.COMMENT, "comment_123", content_hash, "agent1"
        )
        db_session.commit()

        # Try to register again - should be handled by unique constraints
        with pytest.raises(Exception):  # IntegrityError expected  # noqa: B017
            register_content_processing(
                db_session, ContentType.COMMENT, "comment_123", content_hash, "agent2"
            )
            db_session.commit()


class TestTaskIdempotency:
    """Test A2A task idempotency functionality."""

    def test_find_duplicate_task_not_found(self, db_session):
        """Test finding non-existent duplicate task."""
        result = find_duplicate_task(db_session, "test_agent", "test_skill", "hash123")
        assert result is None

    def test_create_idempotent_task_new(self, db_session):
        """Test creating new idempotent task."""
        parameters = {"param1": "value1", "param2": 42}

        task, is_new = create_idempotent_task(
            db_session,
            "retrieval_agent",
            "fetch_posts",
            parameters,
            "workflow_123",
            priority=3,
        )

        assert is_new is True
        assert task.agent_type == "retrieval_agent"
        assert task.skill_name == "fetch_posts"
        assert task.parameters == parameters
        assert task.workflow_id == "workflow_123"
        assert task.priority == 3
        assert task.status == TaskStatus.PENDING
        assert len(task.task_id) == 36  # UUID length

    def test_create_idempotent_task_duplicate(self, db_session):
        """Test creating duplicate idempotent task returns existing."""
        parameters = {"param1": "value1"}

        # Create first task
        task1, is_new1 = create_idempotent_task(
            db_session, "test_agent", "test_skill", parameters, "workflow_123"
        )
        db_session.commit()

        # Try to create duplicate
        task2, is_new2 = create_idempotent_task(
            db_session, "test_agent", "test_skill", parameters, "workflow_123"
        )

        assert is_new1 is True
        assert is_new2 is False
        assert task1.id == task2.id

    def test_find_duplicate_task_different_workflows(self, db_session):
        """Test that tasks with different workflows are not considered duplicates."""
        parameters = {"param1": "value1"}

        # Create task in workflow A
        create_idempotent_task(
            db_session, "test_agent", "test_skill", parameters, "workflow_A"
        )
        db_session.commit()

        # Try to find duplicate in workflow B
        duplicate = find_duplicate_task(
            db_session,
            "test_agent",
            "test_skill",
            generate_parameters_hash(parameters),
            "workflow_B",
        )

        assert duplicate is None


class TestAgentStateManagement:
    """Test agent state management functionality."""

    def test_update_agent_state_new(self, db_session):
        """Test updating agent state for new agent."""
        state_data = {"current_operation": "fetching", "progress": 0.5}

        agent_state = update_agent_state(
            db_session, "agent_123", "retrieval_agent", "busy", state_data, "task_456"
        )

        assert agent_state.agent_id == "agent_123"
        assert agent_state.agent_type == "retrieval_agent"
        assert agent_state.status == "busy"
        assert agent_state.state_data == state_data
        assert agent_state.current_task_id == "task_456"

    def test_update_agent_state_existing(self, db_session):
        """Test updating existing agent state."""
        # Create initial state
        agent_state = update_agent_state(
            db_session, "agent_456", "filter_agent", "idle", {"ready": True}
        )
        initial_id = agent_state.id
        db_session.commit()

        # Update state
        updated_state = update_agent_state(
            db_session,
            "agent_456",
            "filter_agent",
            "busy",
            {"filtering": True},
            "task_789",
        )

        assert updated_state.id == initial_id  # Same record
        assert updated_state.status == "busy"
        assert updated_state.state_data == {"filtering": True}
        assert updated_state.current_task_id == "task_789"

    def test_get_agent_states_all(self, db_session):
        """Test getting all agent states."""
        # Create multiple agent states
        update_agent_state(db_session, "agent1", "type1", "idle", {})
        update_agent_state(db_session, "agent2", "type2", "busy", {})
        update_agent_state(db_session, "agent3", "type1", "error", {})
        db_session.commit()

        all_states = get_agent_states(db_session)
        assert len(all_states) == 3

    def test_get_agent_states_filtered(self, db_session):
        """Test getting filtered agent states."""
        # Create multiple agent states
        update_agent_state(db_session, "agent1", "retrieval", "idle", {})
        update_agent_state(db_session, "agent2", "filter", "busy", {})
        update_agent_state(db_session, "agent3", "retrieval", "idle", {})
        db_session.commit()

        # Filter by type
        retrieval_agents = get_agent_states(db_session, agent_type="retrieval")
        assert len(retrieval_agents) == 2

        # Filter by status
        idle_agents = get_agent_states(db_session, status="idle")
        assert len(idle_agents) == 2


class TestTaskLocking:
    """Test distributed task locking functionality."""

    def test_acquire_task_lock_success(self, db_session):
        """Test successful task lock acquisition."""
        # Create a task
        task, _ = create_idempotent_task(
            db_session, "test_agent", "test_skill", {}, "workflow_123"
        )
        db_session.commit()

        # Acquire lock
        success = acquire_task_lock(db_session, task.task_id, "lock_token_123", 30)
        assert success is True

        # Verify lock is set
        db_session.refresh(task)
        assert task.lock_token == "lock_token_123"
        assert task.lock_expires_at is not None

    def test_acquire_task_lock_already_locked(self, db_session):
        """Test acquiring lock on already locked task."""
        # Create and lock a task
        task, _ = create_idempotent_task(
            db_session, "test_agent", "test_skill", {}, "workflow_123"
        )
        db_session.commit()

        acquire_task_lock(db_session, task.task_id, "lock_token_1", 30)
        db_session.commit()

        # Try to acquire with different token
        success = acquire_task_lock(db_session, task.task_id, "lock_token_2", 30)
        assert success is False

    def test_release_task_lock_success(self, db_session):
        """Test successful task lock release."""
        # Create and lock a task
        task, _ = create_idempotent_task(
            db_session, "test_agent", "test_skill", {}, "workflow_123"
        )
        db_session.commit()

        acquire_task_lock(db_session, task.task_id, "lock_token_123", 30)
        db_session.commit()

        # Release lock
        success = release_task_lock(db_session, task.task_id, "lock_token_123")
        assert success is True

        # Verify lock is cleared
        db_session.refresh(task)
        assert task.lock_token is None
        assert task.lock_expires_at is None

    def test_release_task_lock_wrong_token(self, db_session):
        """Test releasing lock with wrong token."""
        # Create and lock a task
        task, _ = create_idempotent_task(
            db_session, "test_agent", "test_skill", {}, "workflow_123"
        )
        db_session.commit()

        acquire_task_lock(db_session, task.task_id, "lock_token_123", 30)
        db_session.commit()

        # Try to release with wrong token
        success = release_task_lock(db_session, task.task_id, "wrong_token")
        assert success is False

        # Verify lock is still there
        db_session.refresh(task)
        assert task.lock_token == "lock_token_123"

    def test_cleanup_expired_locks(self, db_session):
        """Test cleanup of expired locks."""
        # Create task with expired lock
        task, _ = create_idempotent_task(
            db_session, "test_agent", "test_skill", {}, "workflow_123"
        )
        task.lock_token = "expired_token"
        task.lock_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        # Cleanup expired locks
        cleaned_count = cleanup_expired_locks(db_session)
        assert cleaned_count == 1

        # Verify lock is cleared
        db_session.refresh(task)
        assert task.lock_token is None
        assert task.lock_expires_at is None


class TestTaskRecovery:
    """Test task recovery functionality."""

    def test_create_task_recovery(self, db_session):
        """Test creating task recovery record."""
        recovery = create_task_recovery(
            db_session,
            "original_task_123",
            "retry",
            {"checkpoint": "data"},
            "Network timeout",
            5,
        )

        assert recovery.original_task_id == "original_task_123"
        assert recovery.recovery_strategy == "retry"
        assert recovery.checkpoint_data == {"checkpoint": "data"}
        assert recovery.failure_reason == "Network timeout"
        assert recovery.max_recovery_attempts == 5
        assert recovery.recovery_status == "pending"

    def test_get_pending_recoveries(self, db_session):
        """Test getting pending recovery records."""
        # Create multiple recovery records
        create_task_recovery(db_session, "task1", "retry", {}, "Error 1")
        create_task_recovery(db_session, "task2", "rollback", {}, "Error 2")
        recovery3 = create_task_recovery(db_session, "task3", "retry", {}, "Error 3")
        recovery3.recovery_status = "completed"
        db_session.commit()

        # Get pending recoveries
        pending = get_pending_recoveries(db_session)
        assert len(pending) == 2

        # Filter by strategy
        retry_recoveries = get_pending_recoveries(db_session, "retry")
        assert len(retry_recoveries) == 1


class TestAgentCoordination:
    """Test agent coordination functionality."""

    @pytest.fixture
    def agent_coordinator(self, db_session):
        """Create agent coordinator for testing."""
        return AgentCoordinator(db_session, "test_agent_123", "test_agent")

    def test_agent_coordinator_register(self, agent_coordinator, db_session):
        """Test agent registration."""
        capabilities = ["skill1", "skill2", "skill3"]
        initial_state = {"initialized": True}

        # Mock asyncio.create_task to avoid actual async execution
        with patch("asyncio.create_task"):
            agent_coordinator.register_agent(capabilities, initial_state)

        # Verify agent state was created
        agent_states = get_agent_states(db_session)
        assert len(agent_states) == 1

        agent_state = agent_states[0]
        assert agent_state.agent_id == "test_agent_123"
        assert agent_state.agent_type == "test_agent"
        assert agent_state.status == "idle"
        assert agent_state.capabilities == capabilities
        assert agent_state.state_data == initial_state

    def test_agent_coordinator_update_state(self, agent_coordinator, db_session):
        """Test agent state updates."""
        # Initialize agent
        with patch("asyncio.create_task"):
            agent_coordinator.register_agent(["skill1"])

        # Update state
        new_state = {"current_operation": "processing", "progress": 0.75}
        agent_coordinator.update_state(new_state)

        # Verify state was updated
        agent_states = get_agent_states(db_session)
        assert len(agent_states) == 1
        assert agent_states[0].state_data == new_state

    def test_agent_coordinator_task_lifecycle(self, agent_coordinator, db_session):
        """Test agent task lifecycle management."""
        # Initialize agent
        with patch("asyncio.create_task"):
            agent_coordinator.register_agent(["skill1"])

        task_id = str(uuid.uuid4())

        # Start task
        agent_coordinator.start_task(task_id)
        agent_state = get_agent_states(db_session)[0]
        assert agent_state.status == "busy"
        assert agent_state.current_task_id == task_id

        # Complete task successfully
        agent_coordinator.complete_task(task_id, success=True)
        agent_state = get_agent_states(db_session)[0]
        assert agent_state.status == "idle"
        assert agent_state.current_task_id is None
        assert agent_state.tasks_completed == 1
        assert agent_state.tasks_failed == 0


class TestWorkflowCoordination:
    """Test workflow coordination functionality."""

    @pytest.fixture
    def workflow_coordinator(self, db_session):
        """Create workflow coordinator for testing."""
        return WorkflowCoordinator(db_session)

    def test_get_available_agents(self, workflow_coordinator, db_session):
        """Test getting available agents."""
        # Create test agents
        update_agent_state(db_session, "agent1", "retrieval", "idle", {})
        update_agent_state(db_session, "agent2", "filter", "busy", {})
        update_agent_state(db_session, "agent3", "retrieval", "idle", {})

        # Update heartbeats to recent times
        recent_time = datetime.utcnow()
        for agent in get_agent_states(db_session):
            agent.heartbeat_at = recent_time
        db_session.commit()

        # Get available retrieval agents
        available = workflow_coordinator.get_available_agents("retrieval")
        assert len(available) == 2

        # Get available agents with capabilities
        agent1 = get_agent_states(db_session, agent_type="retrieval")[0]
        agent1.capabilities = ["fetch_posts", "fetch_comments"]
        db_session.commit()

        available_with_caps = workflow_coordinator.get_available_agents(
            "retrieval", ["fetch_posts"]
        )
        assert len(available_with_caps) == 1

    def test_assign_task_to_agent(self, workflow_coordinator, db_session):
        """Test task assignment to agents."""
        # Create available agent
        update_agent_state(db_session, "agent_123", "test_agent", "idle", {})
        agent_state = get_agent_states(db_session)[0]
        agent_state.heartbeat_at = datetime.utcnow()
        agent_state.tasks_completed = 10
        agent_state.error_count = 1
        db_session.commit()

        # Create task
        task, _ = create_idempotent_task(
            db_session, "test_agent", "test_skill", {}, "workflow_123"
        )
        db_session.commit()

        # Assign task
        assigned_agent = workflow_coordinator.assign_task_to_agent(task)
        assert assigned_agent == "agent_123"


@pytest.mark.asyncio
class TestTaskRecoveryManager:
    """Test task recovery manager functionality."""

    @pytest.fixture
    def recovery_manager(self, db_session):
        """Create task recovery manager for testing."""
        return TaskRecoveryManager(db_session)

    async def test_scan_for_failed_tasks(self, recovery_manager, db_session):
        """Test scanning for failed tasks."""
        # Create various tasks
        failed_task, _ = create_idempotent_task(
            db_session, "test_agent", "skill1", {}, "workflow_123"
        )
        failed_task.status = TaskStatus.FAILED

        stuck_task, _ = create_idempotent_task(
            db_session, "test_agent", "skill2", {}, "workflow_123"
        )
        stuck_task.status = TaskStatus.RUNNING
        stuck_task.started_at = datetime.utcnow() - timedelta(hours=2)

        old_pending_task, _ = create_idempotent_task(
            db_session, "test_agent", "skill3", {}, "workflow_123"
        )
        old_pending_task.status = TaskStatus.PENDING
        old_pending_task.created_at = datetime.utcnow() - timedelta(hours=1)

        normal_task, _ = create_idempotent_task(
            db_session, "test_agent", "skill4", {}, "workflow_123"
        )
        normal_task.status = TaskStatus.COMPLETED

        db_session.commit()

        # Scan for failed tasks
        failed_tasks = await recovery_manager.scan_for_failed_tasks()
        failed_task_ids = [t.task_id for t in failed_tasks]

        assert failed_task.task_id in failed_task_ids
        assert stuck_task.task_id in failed_task_ids
        assert old_pending_task.task_id in failed_task_ids
        assert normal_task.task_id not in failed_task_ids

    def test_determine_recovery_strategy(self, recovery_manager, db_session):
        """Test recovery strategy determination."""
        # Failed task with retries left
        task1, _ = create_idempotent_task(
            db_session, "test_agent", "skill1", {}, "workflow_123"
        )
        task1.status = TaskStatus.FAILED
        task1.retry_count = 1
        task1.max_retries = 3

        strategy1 = recovery_manager.determine_recovery_strategy(task1)
        assert strategy1 == RecoveryStrategy.RETRY

        # Failed task with no retries left
        task2, _ = create_idempotent_task(
            db_session, "test_agent", "skill2", {}, "workflow_123"
        )
        task2.status = TaskStatus.FAILED
        task2.retry_count = 3
        task2.max_retries = 3

        strategy2 = recovery_manager.determine_recovery_strategy(task2)
        assert strategy2 == RecoveryStrategy.ROLLBACK

        # Long-running task
        task3, _ = create_idempotent_task(
            db_session, "test_agent", "skill3", {}, "workflow_123"
        )
        task3.status = TaskStatus.RUNNING
        task3.started_at = datetime.utcnow() - timedelta(hours=3)

        strategy3 = recovery_manager.determine_recovery_strategy(task3)
        assert strategy3 == RecoveryStrategy.RETRY

    async def test_create_recovery_plan(self, recovery_manager, db_session):
        """Test recovery plan creation."""
        # Create failed task
        task, _ = create_idempotent_task(
            db_session, "test_agent", "skill1", {}, "workflow_123"
        )
        task.status = TaskStatus.FAILED
        task.error_message = "Network timeout"
        db_session.commit()

        # Create recovery plan
        recovery = await recovery_manager.create_recovery_plan(
            task, RecoveryStrategy.RETRY, {"checkpoint": "data"}
        )

        assert recovery.original_task_id == task.task_id
        assert recovery.recovery_strategy == "retry"
        assert recovery.checkpoint_data == {"checkpoint": "data"}
        assert recovery.failure_reason == "Network timeout"
        assert recovery.recovery_status == "pending"


if __name__ == "__main__":
    pytest.main([__file__])
