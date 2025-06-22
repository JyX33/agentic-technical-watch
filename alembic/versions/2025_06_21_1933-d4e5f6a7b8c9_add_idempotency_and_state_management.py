"""Add idempotency and state management

Revision ID: d4e5f6a7b8c9
Revises: ca668e63d7bf
Create Date: 2025-06-21 19:33:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from reddit_watcher.models import JSONType

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "ca668e63d7bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema with idempotency and state management features."""

    # Add new columns to a2a_tasks table for idempotency
    op.add_column(
        "a2a_tasks",
        sa.Column(
            "parameters_hash", sa.String(length=64), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "a2a_tasks", sa.Column("idempotency_key", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "a2a_tasks", sa.Column("correlation_id", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "a2a_tasks", sa.Column("content_hash", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "a2a_tasks", sa.Column("lock_token", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "a2a_tasks",
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "a2a_tasks",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("a2a_tasks", sa.Column("result_data", JSONType(), nullable=True))
    op.add_column(
        "a2a_tasks", sa.Column("result_hash", sa.String(length=64), nullable=True)
    )

    # Add indexes and constraints for a2a_tasks
    op.create_unique_constraint(
        "uix_a2a_tasks_idempotency",
        "a2a_tasks",
        ["agent_type", "skill_name", "parameters_hash", "workflow_id"],
    )
    op.create_index(
        "ix_a2a_tasks_status_created", "a2a_tasks", ["status", "created_at"]
    )
    op.create_index(
        "ix_a2a_tasks_workflow_status", "a2a_tasks", ["workflow_id", "status"]
    )

    # Add unique constraint to alert_deliveries for idempotency
    op.create_unique_constraint(
        "uix_alert_deliveries_idempotency",
        "alert_deliveries",
        ["alert_batch_id", "channel", "recipient"],
    )
    op.create_index(
        "ix_alert_deliveries_status_created",
        "alert_deliveries",
        ["status", "created_at"],
    )

    # Create agent_states table
    op.create_table(
        "agent_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("agent_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="idle"
        ),
        sa.Column("state_data", JSONType(), nullable=False, server_default="{}"),
        sa.Column("capabilities", JSONType(), nullable=False, server_default="[]"),
        sa.Column("current_task_id", sa.String(length=36), nullable=True),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("tasks_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_execution_time_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add indexes for agent_states
    op.create_unique_constraint(
        "uix_agent_states_agent_id", "agent_states", ["agent_id"]
    )
    op.create_index(
        "ix_agent_states_status_updated", "agent_states", ["status", "last_updated"]
    )

    # Create task_recoveries table
    op.create_table(
        "task_recoveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), unique=True, nullable=False),
        sa.Column("original_task_id", sa.String(length=36), nullable=False),
        sa.Column(
            "recovery_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("recovery_strategy", sa.String(length=100), nullable=False),
        sa.Column("recovery_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "max_recovery_attempts", sa.Integer(), nullable=False, server_default="3"
        ),
        sa.Column("checkpoint_data", JSONType(), nullable=True),
        sa.Column("recovery_parameters", JSONType(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("recovery_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovery_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovery_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add indexes for task_recoveries
    op.create_unique_constraint(
        "uix_task_recoveries_task_id", "task_recoveries", ["task_id"]
    )
    op.create_index(
        "ix_task_recoveries_status_created",
        "task_recoveries",
        ["recovery_status", "created_at"],
    )

    # Create content_deduplication table
    op.create_table(
        "content_deduplication",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), unique=True, nullable=False),
        sa.Column(
            "content_type",
            sa.Enum("POST", "COMMENT", "SUBREDDIT", name="contenttype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=50),
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_agent", sa.String(length=100), nullable=True),
        sa.Column("workflow_id", sa.String(length=100), nullable=True),
        sa.Column("extra_data", JSONType(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add indexes and constraints for content_deduplication
    op.create_unique_constraint(
        "uix_content_deduplication_hash", "content_deduplication", ["content_hash"]
    )
    op.create_unique_constraint(
        "uix_content_deduplication_external",
        "content_deduplication",
        ["content_type", "external_id"],
    )
    op.create_index(
        "ix_content_deduplication_type_processed",
        "content_deduplication",
        ["content_type", "processed_at"],
    )


def downgrade() -> None:
    """Downgrade schema by removing idempotency and state management features."""

    # Drop tables
    op.drop_table("content_deduplication")
    op.drop_table("task_recoveries")
    op.drop_table("agent_states")

    # Drop indexes and constraints from alert_deliveries
    op.drop_index("ix_alert_deliveries_status_created", "alert_deliveries")
    op.drop_constraint(
        "uix_alert_deliveries_idempotency", "alert_deliveries", type_="unique"
    )

    # Drop indexes and constraints from a2a_tasks
    op.drop_index("ix_a2a_tasks_workflow_status", "a2a_tasks")
    op.drop_index("ix_a2a_tasks_status_created", "a2a_tasks")
    op.drop_constraint("uix_a2a_tasks_idempotency", "a2a_tasks", type_="unique")

    # Remove columns from a2a_tasks
    op.drop_column("a2a_tasks", "result_hash")
    op.drop_column("a2a_tasks", "result_data")
    op.drop_column("a2a_tasks", "next_retry_at")
    op.drop_column("a2a_tasks", "lock_expires_at")
    op.drop_column("a2a_tasks", "lock_token")
    op.drop_column("a2a_tasks", "content_hash")
    op.drop_column("a2a_tasks", "correlation_id")
    op.drop_column("a2a_tasks", "idempotency_key")
    op.drop_column("a2a_tasks", "parameters_hash")
