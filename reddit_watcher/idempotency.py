# ABOUTME: Idempotency utilities for A2A task deduplication and state management
# ABOUTME: Provides functions for content hashing, task deduplication, and recovery operations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .models import (
    A2ATask,
    AgentState,
    ContentDeduplication,
    ContentType,
    TaskRecovery,
    TaskStatus,
)


def generate_content_hash(content: Any) -> str:
    """Generate SHA256 hash for content deduplication.

    Args:
        content: Content to hash (dict, string, or any JSON-serializable object)

    Returns:
        SHA256 hash as hex string
    """
    if isinstance(content, dict):
        # Sort keys for consistent hashing
        normalized = json.dumps(content, sort_keys=True, separators=(",", ":"))
    elif isinstance(content, str):
        normalized = content
    else:
        normalized = json.dumps(content, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_parameters_hash(parameters: dict[str, Any]) -> str:
    """Generate hash for task parameters to enable idempotency."""
    return generate_content_hash(parameters)


def check_content_duplication(
    session: Session,
    content_type: ContentType,
    external_id: str,
    content_hash: str | None = None,
) -> ContentDeduplication | None:
    """Check if content has already been processed.

    Args:
        session: Database session
        content_type: Type of content (post, comment, subreddit)
        external_id: External ID (Reddit ID, etc.)
        content_hash: Optional content hash for additional verification

    Returns:
        ContentDeduplication record if found, None otherwise
    """
    query = select(ContentDeduplication).where(
        and_(
            ContentDeduplication.content_type == content_type,
            ContentDeduplication.external_id == external_id,
        )
    )

    if content_hash:
        query = query.where(ContentDeduplication.content_hash == content_hash)

    return session.execute(query).scalar_one_or_none()


def register_content_processing(
    session: Session,
    content_type: ContentType,
    external_id: str,
    content_hash: str,
    source_agent: str,
    workflow_id: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> ContentDeduplication:
    """Register content for deduplication tracking.

    Args:
        session: Database session
        content_type: Type of content
        external_id: External ID
        content_hash: Content hash
        source_agent: Agent that first processed this content
        workflow_id: Optional workflow ID
        extra_data: Optional extra_data

    Returns:
        ContentDeduplication record
    """
    dedup_record = ContentDeduplication(
        content_hash=content_hash,
        content_type=content_type,
        external_id=external_id,
        processing_status="processing",
        source_agent=source_agent,
        workflow_id=workflow_id,
        extra_data=extra_data or {},
    )

    session.add(dedup_record)
    session.flush()
    return dedup_record


def find_duplicate_task(
    session: Session,
    agent_type: str,
    skill_name: str,
    parameters_hash: str,
    workflow_id: str | None = None,
) -> A2ATask | None:
    """Find existing task with same parameters for idempotency.

    Args:
        session: Database session
        agent_type: Type of agent
        skill_name: Skill being executed
        parameters_hash: Hash of task parameters
        workflow_id: Optional workflow ID

    Returns:
        Existing A2ATask if found, None otherwise
    """
    query = select(A2ATask).where(
        and_(
            A2ATask.agent_type == agent_type,
            A2ATask.skill_name == skill_name,
            A2ATask.parameters_hash == parameters_hash,
        )
    )

    if workflow_id:
        query = query.where(A2ATask.workflow_id == workflow_id)

    # Only consider tasks that are not failed or cancelled
    query = query.where(
        A2ATask.status.in_(
            [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.COMPLETED]
        )
    )

    return session.execute(query).scalar_one_or_none()


def create_idempotent_task(
    session: Session,
    agent_type: str,
    skill_name: str,
    parameters: dict[str, Any],
    workflow_id: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    priority: int = 5,
) -> tuple[A2ATask, bool]:
    """Create A2A task with idempotency checking.

    Args:
        session: Database session
        agent_type: Type of agent
        skill_name: Skill to execute
        parameters: Task parameters
        workflow_id: Optional workflow ID
        idempotency_key: Optional custom idempotency key
        correlation_id: Optional correlation ID
        priority: Task priority (1=highest, 10=lowest)

    Returns:
        Tuple of (A2ATask, is_new) where is_new indicates if task was created
    """
    parameters_hash = generate_parameters_hash(parameters)

    # Check for existing task
    existing_task = find_duplicate_task(
        session, agent_type, skill_name, parameters_hash, workflow_id
    )

    if existing_task:
        return existing_task, False

    # Create new task
    task = A2ATask(
        task_id=str(uuid.uuid4()),
        agent_type=agent_type,
        skill_name=skill_name,
        parameters=parameters,
        parameters_hash=parameters_hash,
        workflow_id=workflow_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        priority=priority,
    )

    session.add(task)
    session.flush()
    return task, True


def update_agent_state(
    session: Session,
    agent_id: str,
    agent_type: str,
    status: str,
    state_data: dict[str, Any] | None = None,
    current_task_id: str | None = None,
) -> AgentState:
    """Update agent state for synchronization.

    Args:
        session: Database session
        agent_id: Unique agent identifier
        agent_type: Type of agent
        status: Agent status (idle, busy, error, offline)
        state_data: Optional state data
        current_task_id: Optional current task ID

    Returns:
        Updated AgentState record
    """
    # Try to find existing state
    query = select(AgentState).where(AgentState.agent_id == agent_id)
    agent_state = session.execute(query).scalar_one_or_none()

    if agent_state:
        # Update existing state
        agent_state.status = status
        agent_state.heartbeat_at = datetime.utcnow()
        if state_data is not None:
            agent_state.state_data = state_data
        if current_task_id:
            agent_state.current_task_id = current_task_id
        agent_state.last_updated = datetime.utcnow()
    else:
        # Create new state
        agent_state = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            status=status,
            state_data=state_data or {},
            current_task_id=current_task_id,
        )
        session.add(agent_state)

    session.flush()
    return agent_state


def get_agent_states(
    session: Session, agent_type: str | None = None, status: str | None = None
) -> list[AgentState]:
    """Get agent states for synchronization monitoring.

    Args:
        session: Database session
        agent_type: Optional filter by agent type
        status: Optional filter by status

    Returns:
        List of AgentState records
    """
    query = select(AgentState)

    if agent_type:
        query = query.where(AgentState.agent_type == agent_type)

    if status:
        query = query.where(AgentState.status == status)

    query = query.order_by(AgentState.last_updated.desc())

    return list(session.execute(query).scalars().all())


def create_task_recovery(
    session: Session,
    original_task_id: str,
    recovery_strategy: str,
    checkpoint_data: dict[str, Any] | None = None,
    failure_reason: str | None = None,
    max_attempts: int = 3,
) -> TaskRecovery:
    """Create task recovery record for interrupted operations.

    Args:
        session: Database session
        original_task_id: ID of the failed/interrupted task
        recovery_strategy: Strategy (retry, rollback, skip, manual)
        checkpoint_data: Optional checkpoint data
        failure_reason: Optional failure reason
        max_attempts: Maximum recovery attempts

    Returns:
        TaskRecovery record
    """
    recovery = TaskRecovery(
        task_id=str(uuid.uuid4()),
        original_task_id=original_task_id,
        recovery_strategy=recovery_strategy,
        checkpoint_data=checkpoint_data,
        failure_reason=failure_reason,
        max_recovery_attempts=max_attempts,
    )

    session.add(recovery)
    session.flush()
    return recovery


def get_pending_recoveries(
    session: Session, recovery_strategy: str | None = None
) -> list[TaskRecovery]:
    """Get pending task recoveries.

    Args:
        session: Database session
        recovery_strategy: Optional filter by recovery strategy

    Returns:
        List of pending TaskRecovery records
    """
    query = select(TaskRecovery).where(TaskRecovery.recovery_status == "pending")

    if recovery_strategy:
        query = query.where(TaskRecovery.recovery_strategy == recovery_strategy)

    query = query.order_by(TaskRecovery.created_at.asc())

    return list(session.execute(query).scalars().all())


def cleanup_expired_locks(session: Session) -> int:
    """Clean up expired task locks.

    Args:
        session: Database session

    Returns:
        Number of locks cleaned up
    """
    now = datetime.utcnow()

    # Find tasks with expired locks
    query = select(A2ATask).where(
        and_(A2ATask.lock_token.isnot(None), A2ATask.lock_expires_at < now)
    )

    expired_tasks = list(session.execute(query).scalars().all())

    # Clear expired locks
    for task in expired_tasks:
        task.lock_token = None
        task.lock_expires_at = None

    if expired_tasks:
        session.flush()

    return len(expired_tasks)


def acquire_task_lock(
    session: Session, task_id: str, lock_token: str, lock_duration_minutes: int = 30
) -> bool:
    """Acquire distributed lock for task execution.

    Args:
        session: Database session
        task_id: Task ID to lock
        lock_token: Unique lock token
        lock_duration_minutes: Lock duration in minutes

    Returns:
        True if lock acquired, False if already locked
    """
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=lock_duration_minutes)

    # Try to find the task
    query = select(A2ATask).where(A2ATask.task_id == task_id)
    task = session.execute(query).scalar_one_or_none()

    if not task:
        return False

    # Check if already locked and not expired
    if task.lock_token and task.lock_expires_at and task.lock_expires_at > now:
        return False

    # Acquire lock
    task.lock_token = lock_token
    task.lock_expires_at = expires_at
    session.flush()

    return True


def release_task_lock(session: Session, task_id: str, lock_token: str) -> bool:
    """Release distributed lock for task execution.

    Args:
        session: Database session
        task_id: Task ID to unlock
        lock_token: Lock token that was used to acquire

    Returns:
        True if lock released, False if lock not found or token mismatch
    """
    query = select(A2ATask).where(A2ATask.task_id == task_id)
    task = session.execute(query).scalar_one_or_none()

    if not task or task.lock_token != lock_token:
        return False

    # Release lock
    task.lock_token = None
    task.lock_expires_at = None
    session.flush()

    return True
