# ABOUTME: Database module exports for Reddit Technical Watcher A2A system
# ABOUTME: Provides migration utilities and database initialization functions

from reddit_watcher.database.utils import (
    check_database_health,
    cleanup_old_tasks,
    create_a2a_task,
    create_a2a_workflow,
    get_db_session,
    get_pending_tasks,
    get_task_by_id,
    update_task_status,
)

from .migrations import create_all_tables, run_migrations

__all__ = [
    "create_all_tables",
    "run_migrations",
    "check_database_health",
    "cleanup_old_tasks",
    "create_a2a_task",
    "create_a2a_workflow",
    "get_db_session",
    "get_pending_tasks",
    "get_task_by_id",
    "update_task_status",
]
