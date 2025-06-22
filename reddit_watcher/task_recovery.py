# ABOUTME: Task recovery procedures for interrupted and failed A2A operations
# ABOUTME: Handles task recovery strategies, checkpoint management, and failure recovery

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .idempotency import (
    cleanup_expired_locks,
    create_task_recovery,
    get_pending_recoveries,
)
from .models import A2ATask, TaskRecovery, TaskStatus

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategies for failed tasks."""

    RETRY = "retry"  # Retry the task with same parameters
    ROLLBACK = "rollback"  # Rollback changes and mark as failed
    SKIP = "skip"  # Skip the task and continue workflow
    MANUAL = "manual"  # Requires manual intervention
    CHECKPOINT = "checkpoint"  # Resume from checkpoint


class TaskRecoveryManager:
    """Manages task recovery operations and strategies."""

    def __init__(self, session: Session):
        self.session = session
        self.recovery_handlers: dict[RecoveryStrategy, Callable] = {
            RecoveryStrategy.RETRY: self._handle_retry_recovery,
            RecoveryStrategy.ROLLBACK: self._handle_rollback_recovery,
            RecoveryStrategy.SKIP: self._handle_skip_recovery,
            RecoveryStrategy.CHECKPOINT: self._handle_checkpoint_recovery,
            RecoveryStrategy.MANUAL: self._handle_manual_recovery,
        }

    async def scan_for_failed_tasks(self, max_age_hours: int = 24) -> list[A2ATask]:
        """Scan for tasks that need recovery.

        Args:
            max_age_hours: Maximum age of tasks to consider for recovery

        Returns:
            List of tasks needing recovery
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        # Find tasks that are stuck or failed
        query = select(A2ATask).where(
            and_(
                A2ATask.created_at > cutoff_time,
                or_(
                    # Explicitly failed tasks
                    A2ATask.status == TaskStatus.FAILED,
                    # Tasks running too long (more than 1 hour)
                    and_(
                        A2ATask.status == TaskStatus.RUNNING,
                        A2ATask.started_at < datetime.utcnow() - timedelta(hours=1),
                    ),
                    # Tasks pending too long (more than 30 minutes)
                    and_(
                        A2ATask.status == TaskStatus.PENDING,
                        A2ATask.created_at < datetime.utcnow() - timedelta(minutes=30),
                    ),
                ),
            )
        )

        failed_tasks = list(self.session.execute(query).scalars().all())

        logger.info(f"Found {len(failed_tasks)} tasks needing recovery")
        return failed_tasks

    def determine_recovery_strategy(self, task: A2ATask) -> RecoveryStrategy:
        """Determine appropriate recovery strategy for a task.

        Args:
            task: Task to determine recovery strategy for

        Returns:
            Recommended recovery strategy
        """
        # Check if task has been retried too many times
        if task.retry_count >= task.max_retries:
            if task.status == TaskStatus.FAILED:
                return RecoveryStrategy.ROLLBACK
            else:
                return RecoveryStrategy.MANUAL

        # Check if task is stuck in running state
        if task.status == TaskStatus.RUNNING:
            if task.started_at and task.started_at < datetime.utcnow() - timedelta(
                hours=2
            ):
                return RecoveryStrategy.RETRY  # Likely crashed
            else:
                return RecoveryStrategy.MANUAL  # Might still be running

        # Check if task is pending too long
        if task.status == TaskStatus.PENDING:
            return RecoveryStrategy.RETRY

        # Default to retry for failed tasks
        if task.status == TaskStatus.FAILED:
            return RecoveryStrategy.RETRY

        return RecoveryStrategy.MANUAL

    async def create_recovery_plan(
        self,
        task: A2ATask,
        strategy: RecoveryStrategy | None = None,
        checkpoint_data: dict[str, Any] | None = None,
    ) -> TaskRecovery:
        """Create recovery plan for a failed task.

        Args:
            task: Task to create recovery plan for
            strategy: Recovery strategy to use (auto-determined if None)
            checkpoint_data: Optional checkpoint data

        Returns:
            Created TaskRecovery record
        """
        if strategy is None:
            strategy = self.determine_recovery_strategy(task)

        # Create recovery record
        recovery = create_task_recovery(
            self.session,
            task.task_id,
            strategy.value,
            checkpoint_data,
            task.error_message,
            max_attempts=3,
        )

        self.session.commit()

        logger.info(
            f"Created recovery plan for task {task.task_id} with strategy {strategy.value}"
        )
        return recovery

    async def execute_recovery(self, recovery: TaskRecovery) -> bool:
        """Execute recovery procedure.

        Args:
            recovery: Recovery record to execute

        Returns:
            True if recovery successful, False otherwise
        """
        strategy = RecoveryStrategy(recovery.recovery_strategy)

        try:
            # Mark recovery as started
            recovery.recovery_status = "recovering"
            recovery.recovery_started_at = datetime.utcnow()
            recovery.recovery_attempt += 1
            self.session.commit()

            # Execute recovery handler
            handler = self.recovery_handlers.get(strategy)
            if not handler:
                logger.error(f"No handler for recovery strategy {strategy.value}")
                return False

            success = await handler(recovery)

            # Update recovery status
            if success:
                recovery.recovery_status = "completed"
                recovery.recovery_completed_at = datetime.utcnow()
                logger.info(
                    f"Recovery completed successfully for task {recovery.original_task_id}"
                )
            else:
                recovery.recovery_status = "failed"
                recovery.recovery_error = "Recovery handler returned False"
                logger.error(f"Recovery failed for task {recovery.original_task_id}")

            self.session.commit()
            return success

        except Exception as e:
            recovery.recovery_status = "failed"
            recovery.recovery_error = str(e)
            self.session.commit()

            logger.error(
                f"Recovery execution failed for task {recovery.original_task_id}: {e}"
            )
            return False

    async def _handle_retry_recovery(self, recovery: TaskRecovery) -> bool:
        """Handle retry recovery strategy.

        Args:
            recovery: Recovery record

        Returns:
            True if retry successful, False otherwise
        """
        # Find original task
        query = select(A2ATask).where(A2ATask.task_id == recovery.original_task_id)
        original_task = self.session.execute(query).scalar_one_or_none()

        if not original_task:
            logger.error(
                f"Original task {recovery.original_task_id} not found for retry"
            )
            return False

        # Reset task for retry
        original_task.status = TaskStatus.PENDING
        original_task.started_at = None
        original_task.completed_at = None
        original_task.retry_count += 1
        original_task.error_message = None

        # Set next retry time with exponential backoff
        backoff_minutes = min(2**original_task.retry_count, 60)  # Max 1 hour
        original_task.next_retry_at = datetime.utcnow() + timedelta(
            minutes=backoff_minutes
        )

        # Clear any existing locks
        original_task.lock_token = None
        original_task.lock_expires_at = None

        self.session.commit()

        logger.info(
            f"Task {recovery.original_task_id} reset for retry #{original_task.retry_count}"
        )
        return True

    async def _handle_rollback_recovery(self, recovery: TaskRecovery) -> bool:
        """Handle rollback recovery strategy.

        Args:
            recovery: Recovery record

        Returns:
            True if rollback successful, False otherwise
        """
        # Find original task
        query = select(A2ATask).where(A2ATask.task_id == recovery.original_task_id)
        original_task = self.session.execute(query).scalar_one_or_none()

        if not original_task:
            logger.error(
                f"Original task {recovery.original_task_id} not found for rollback"
            )
            return False

        # Mark task as failed permanently
        original_task.status = TaskStatus.FAILED
        original_task.completed_at = datetime.utcnow()
        original_task.error_message = (
            f"Rolled back after {original_task.retry_count} retries"
        )

        # Clear locks
        original_task.lock_token = None
        original_task.lock_expires_at = None

        self.session.commit()

        logger.info(
            f"Task {recovery.original_task_id} rolled back and marked as failed"
        )
        return True

    async def _handle_skip_recovery(self, recovery: TaskRecovery) -> bool:
        """Handle skip recovery strategy.

        Args:
            recovery: Recovery record

        Returns:
            True if skip successful, False otherwise
        """
        # Find original task
        query = select(A2ATask).where(A2ATask.task_id == recovery.original_task_id)
        original_task = self.session.execute(query).scalar_one_or_none()

        if not original_task:
            logger.error(
                f"Original task {recovery.original_task_id} not found for skip"
            )
            return False

        # Mark task as cancelled
        original_task.status = TaskStatus.CANCELLED
        original_task.completed_at = datetime.utcnow()
        original_task.error_message = "Skipped during recovery"

        # Clear locks
        original_task.lock_token = None
        original_task.lock_expires_at = None

        self.session.commit()

        logger.info(f"Task {recovery.original_task_id} skipped during recovery")
        return True

    async def _handle_checkpoint_recovery(self, recovery: TaskRecovery) -> bool:
        """Handle checkpoint recovery strategy.

        Args:
            recovery: Recovery record

        Returns:
            True if checkpoint recovery successful, False otherwise
        """
        # Find original task
        query = select(A2ATask).where(A2ATask.task_id == recovery.original_task_id)
        original_task = self.session.execute(query).scalar_one_or_none()

        if not original_task:
            logger.error(
                f"Original task {recovery.original_task_id} not found for checkpoint recovery"
            )
            return False

        # Restore from checkpoint
        if recovery.checkpoint_data:
            # Merge checkpoint data with original parameters
            original_task.parameters = {
                **original_task.parameters,
                **recovery.checkpoint_data,
                "_checkpoint_recovery": True,
            }

        # Reset task for retry from checkpoint
        original_task.status = TaskStatus.PENDING
        original_task.started_at = None
        original_task.completed_at = None
        original_task.retry_count += 1
        original_task.error_message = None

        # Clear locks
        original_task.lock_token = None
        original_task.lock_expires_at = None

        self.session.commit()

        logger.info(f"Task {recovery.original_task_id} restored from checkpoint")
        return True

    async def _handle_manual_recovery(self, recovery: TaskRecovery) -> bool:
        """Handle manual recovery strategy.

        Args:
            recovery: Recovery record

        Returns:
            True (manual recovery just marks the need for intervention)
        """
        # Find original task
        query = select(A2ATask).where(A2ATask.task_id == recovery.original_task_id)
        original_task = self.session.execute(query).scalar_one_or_none()

        if original_task:
            original_task.error_message = (
                f"Requires manual intervention: {original_task.error_message}"
            )
            self.session.commit()

        logger.warning(
            f"Task {recovery.original_task_id} requires manual recovery intervention"
        )
        return True

    async def process_pending_recoveries(self, max_recoveries: int = 10) -> int:
        """Process pending recovery operations.

        Args:
            max_recoveries: Maximum number of recoveries to process

        Returns:
            Number of recoveries processed
        """
        pending_recoveries = get_pending_recoveries(self.session)

        # Limit to max_recoveries
        pending_recoveries = pending_recoveries[:max_recoveries]

        processed_count = 0

        for recovery in pending_recoveries:
            # Check if we've exceeded max attempts
            if recovery.recovery_attempt >= recovery.max_recovery_attempts:
                recovery.recovery_status = "failed"
                recovery.recovery_error = "Maximum recovery attempts exceeded"
                self.session.commit()
                continue

            # Execute recovery
            success = await self.execute_recovery(recovery)
            if success:
                processed_count += 1

        logger.info(f"Processed {processed_count} recovery operations")
        return processed_count

    async def cleanup_completed_recoveries(self, max_age_days: int = 7) -> int:
        """Clean up old completed recovery records.

        Args:
            max_age_days: Maximum age in days for completed recoveries

        Returns:
            Number of records cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)

        # Find completed recoveries older than cutoff
        query = select(TaskRecovery).where(
            and_(
                TaskRecovery.recovery_status.in_(["completed", "failed"]),
                TaskRecovery.created_at < cutoff_time,
            )
        )

        old_recoveries = list(self.session.execute(query).scalars().all())

        # Delete old records
        for recovery in old_recoveries:
            self.session.delete(recovery)

        if old_recoveries:
            self.session.commit()

        logger.info(f"Cleaned up {len(old_recoveries)} old recovery records")
        return len(old_recoveries)


class RecoveryDaemon:
    """Background daemon for automatic task recovery."""

    def __init__(self, session: Session, check_interval_minutes: int = 5):
        self.session = session
        self.check_interval_minutes = check_interval_minutes
        self.recovery_manager = TaskRecoveryManager(session)
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the recovery daemon."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._recovery_loop())
        logger.info("Recovery daemon started")

    async def stop(self) -> None:
        """Stop the recovery daemon."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Recovery daemon stopped")

    async def _recovery_loop(self) -> None:
        """Main recovery loop."""
        while self._running:
            try:
                # Clean up expired locks
                cleanup_expired_locks(self.session)

                # Scan for failed tasks
                failed_tasks = await self.recovery_manager.scan_for_failed_tasks()

                # Create recovery plans for new failures
                for task in failed_tasks:
                    # Check if recovery already exists
                    existing_recovery = self.session.execute(
                        select(TaskRecovery).where(
                            TaskRecovery.original_task_id == task.task_id
                        )
                    ).scalar_one_or_none()

                    if not existing_recovery:
                        await self.recovery_manager.create_recovery_plan(task)

                # Process pending recoveries
                await self.recovery_manager.process_pending_recoveries()

                # Cleanup old recovery records
                await self.recovery_manager.cleanup_completed_recoveries()

                # Wait before next check
                await asyncio.sleep(self.check_interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in recovery daemon: {e}")
                await asyncio.sleep(60)  # Wait before retrying


# Utility functions for checkpoint management


def create_checkpoint(task_id: str, checkpoint_data: dict[str, Any]) -> dict[str, Any]:
    """Create checkpoint data for task recovery.

    Args:
        task_id: Task ID
        checkpoint_data: Data to checkpoint

    Returns:
        Formatted checkpoint data
    """
    return {
        "task_id": task_id,
        "checkpoint_timestamp": datetime.utcnow().isoformat(),
        "data": checkpoint_data,
    }


def restore_from_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Restore data from checkpoint.

    Args:
        checkpoint: Checkpoint data

    Returns:
        Restored data
    """
    return checkpoint.get("data", {})
