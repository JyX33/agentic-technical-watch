# ABOUTME: Database connection management and A2A state utilities
# ABOUTME: Provides session management, connection pooling, and workflow state operations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from reddit_watcher.config import get_settings
from reddit_watcher.models import (
    A2ATask,
    A2AWorkflow,
    Base,
    TaskStatus,
    create_database_engine,
    create_session_maker,
)

logger = logging.getLogger(__name__)

# Global database connection state
_engine = None
_async_engine = None
_session_maker = None
_async_session_maker = None


def get_database_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_database_engine(settings.database_url)
        logger.info("Database engine created")
    return _engine


def get_async_database_engine():
    """Get or create async database engine."""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        # Convert sync URL to async URL
        async_url = settings.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        _async_engine = create_async_engine(
            async_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        logger.info("Async database engine created")
    return _async_engine


def get_session_maker():
    """Get or create session maker."""
    global _session_maker
    if _session_maker is None:
        engine = get_database_engine()
        _session_maker = create_session_maker(engine)
        logger.info("Session maker created")
    return _session_maker


def get_async_session_maker():
    """Get or create async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_async_database_engine()
        _async_session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Async session maker created")
    return _async_session_maker


@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session_maker = get_session_maker()
    session = session_maker()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_db_session():
    """Async context manager for database sessions."""
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Async database session error: {e}")
            raise


def initialize_database():
    """Initialize database tables and schema."""
    try:
        engine = get_database_engine()
        Base.metadata.create_all(engine)
        logger.info("Database initialized successfully")
    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def initialize_async_database():
    """Initialize database tables and schema (async)."""
    try:
        engine = get_async_database_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Async database initialized successfully")
    except SQLAlchemyError as e:
        logger.error(f"Async database initialization failed: {e}")
        raise


# A2A Task Management


def create_a2a_task(
    agent_type: str,
    skill_name: str,
    parameters: dict,
    workflow_id: str | None = None,
    parent_task_id: str | None = None,
    priority: int = 5,
) -> str:
    """Create a new A2A task and return its ID."""
    task_id = str(uuid4())

    with get_db_session() as session:
        task = A2ATask(
            task_id=task_id,
            agent_type=agent_type,
            skill_name=skill_name,
            parameters=parameters,
            workflow_id=workflow_id,
            parent_task_id=parent_task_id,
            priority=priority,
        )
        session.add(task)
        session.commit()
        logger.info(f"Created A2A task {task_id} for {agent_type}.{skill_name}")

    return task_id


def get_pending_tasks(agent_type: str | None = None, limit: int = 10) -> list[A2ATask]:
    """Get pending tasks for processing."""
    with get_db_session() as session:
        query = select(A2ATask).where(A2ATask.status == TaskStatus.PENDING)

        if agent_type:
            query = query.where(A2ATask.agent_type == agent_type)

        query = query.order_by(A2ATask.priority.asc(), A2ATask.created_at.asc()).limit(
            limit
        )

        result = session.execute(query)
        return result.scalars().all()


def update_task_status(
    task_id: str,
    status: TaskStatus,
    error_message: str | None = None,
) -> bool:
    """Update task status and execution details."""
    with get_db_session() as session:
        query = select(A2ATask).where(A2ATask.task_id == task_id)
        result = session.execute(query)
        task = result.scalar_one_or_none()

        if not task:
            logger.warning(f"Task {task_id} not found for status update")
            return False

        task.status = status

        if status == TaskStatus.RUNNING and not task.started_at:
            task.started_at = func.now()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task.completed_at = func.now()

        if error_message:
            task.error_message = error_message
            task.retry_count += 1

        session.commit()
        logger.info(f"Updated task {task_id} status to {status.value}")
        return True


def get_task_by_id(task_id: str) -> A2ATask | None:
    """Get task by ID."""
    with get_db_session() as session:
        query = select(A2ATask).where(A2ATask.task_id == task_id)
        result = session.execute(query)
        return result.scalar_one_or_none()


# A2A Workflow Management


def create_a2a_workflow(
    workflow_type: str,
    config: dict,
    schedule: str | None = None,
) -> str:
    """Create a new A2A workflow."""
    workflow_id = f"{workflow_type}_{uuid4().hex[:8]}"

    with get_db_session() as session:
        workflow = A2AWorkflow(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            config=config,
            schedule=schedule,
        )
        session.add(workflow)
        session.commit()
        logger.info(f"Created A2A workflow {workflow_id} of type {workflow_type}")

    return workflow_id


def get_active_workflows() -> list[A2AWorkflow]:
    """Get all active workflows."""
    with get_db_session() as session:
        query = select(A2AWorkflow).where(
            A2AWorkflow.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        )
        result = session.execute(query)
        return result.scalars().all()


def update_workflow_status(
    workflow_id: str,
    status: TaskStatus,
    error_count_increment: int = 0,
) -> bool:
    """Update workflow status."""
    with get_db_session() as session:
        query = select(A2AWorkflow).where(A2AWorkflow.workflow_id == workflow_id)
        result = session.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            logger.warning(f"Workflow {workflow_id} not found for status update")
            return False

        workflow.status = status
        workflow.error_count += error_count_increment

        if status == TaskStatus.RUNNING:
            workflow.last_run = func.now()
            workflow.run_count += 1

        session.commit()
        logger.info(f"Updated workflow {workflow_id} status to {status.value}")
        return True


# Database Health and Monitoring


def check_database_health() -> dict[str, Any]:
    """Check database connection health."""
    try:
        with get_db_session() as session:
            # Simple query to test connection
            result = session.execute(select(func.now()))
            current_time = result.scalar()

            # Get some basic stats
            pending_tasks = session.execute(
                select(func.count(A2ATask.id)).where(
                    A2ATask.status == TaskStatus.PENDING
                )
            ).scalar()

            active_workflows = session.execute(
                select(func.count(A2AWorkflow.id)).where(
                    A2AWorkflow.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
                )
            ).scalar()

            return {
                "status": "healthy",
                "current_time": current_time,
                "pending_tasks": pending_tasks,
                "active_workflows": active_workflows,
                "connection": "ok",
            }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": "failed",
        }


def cleanup_old_tasks(days_old: int = 30) -> int:
    """Clean up old completed/failed tasks."""
    with get_db_session() as session:
        cutoff_date = func.now() - func.interval(f"{days_old} days")

        query = select(A2ATask).where(
            and_(
                A2ATask.status.in_(
                    [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                ),
                A2ATask.completed_at < cutoff_date,
            )
        )

        result = session.execute(query)
        old_tasks = result.scalars().all()

        for task in old_tasks:
            session.delete(task)

        session.commit()

        count = len(old_tasks)
        logger.info(f"Cleaned up {count} old tasks")
        return count


# Connection lifecycle


def close_database_connections():
    """Close all database connections."""
    global _engine, _async_engine, _session_maker, _async_session_maker

    if _engine:
        _engine.dispose()
        _engine = None

    if _async_engine:
        _async_engine.dispose()
        _async_engine = None

    _session_maker = None
    _async_session_maker = None

    logger.info("Database connections closed")
