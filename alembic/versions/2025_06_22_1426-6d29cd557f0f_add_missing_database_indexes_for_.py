"""Add missing database indexes for performance optimization

Revision ID: 6d29cd557f0f
Revises: d4e5f6a7b8c9
Create Date: 2025-06-22 14:26:13.148499

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d29cd557f0f"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add missing database indexes for performance optimization."""

    # Core Reddit Content Indexes

    # Subreddits - for active subreddit searches and last checked filtering
    op.create_index("ix_subreddits_is_active", "subreddits", ["is_active"])
    op.create_index("ix_subreddits_last_checked", "subreddits", ["last_checked"])
    op.create_index("ix_subreddits_discovered_at", "subreddits", ["discovered_at"])

    # Reddit Posts - critical for filtering and timeline queries
    op.create_index(
        "ix_reddit_posts_subreddit_created",
        "reddit_posts",
        ["subreddit", "created_utc"],
    )
    op.create_index("ix_reddit_posts_author", "reddit_posts", ["author"])
    op.create_index("ix_reddit_posts_score", "reddit_posts", ["score"])
    op.create_index("ix_reddit_posts_topic", "reddit_posts", ["topic"])
    op.create_index("ix_reddit_posts_created_utc", "reddit_posts", ["created_utc"])
    op.create_index(
        "ix_reddit_posts_subreddit_fk_id", "reddit_posts", ["subreddit_fk_id"]
    )
    # Composite index for common filtering patterns
    op.create_index(
        "ix_reddit_posts_topic_created", "reddit_posts", ["topic", "created_utc"]
    )
    op.create_index(
        "ix_reddit_posts_subreddit_score", "reddit_posts", ["subreddit", "score"]
    )

    # Reddit Comments - for post relationship and timeline queries
    op.create_index("ix_reddit_comments_post_id", "reddit_comments", ["post_id"])
    op.create_index("ix_reddit_comments_author", "reddit_comments", ["author"])
    op.create_index("ix_reddit_comments_score", "reddit_comments", ["score"])
    op.create_index(
        "ix_reddit_comments_created_utc", "reddit_comments", ["created_utc"]
    )
    op.create_index("ix_reddit_comments_parent_id", "reddit_comments", ["parent_id"])
    op.create_index("ix_reddit_comments_post_fk_id", "reddit_comments", ["post_fk_id"])
    op.create_index(
        "ix_reddit_comments_subreddit_fk_id", "reddit_comments", ["subreddit_fk_id"]
    )
    op.create_index(
        "ix_reddit_comments_parent_comment_fk_id",
        "reddit_comments",
        ["parent_comment_fk_id"],
    )
    # Composite indexes for filtering
    op.create_index(
        "ix_reddit_comments_post_created", "reddit_comments", ["post_id", "created_utc"]
    )

    # Content Processing Indexes

    # Content Filters - critical for filtering pipeline performance
    op.create_index("ix_content_filters_post_id", "content_filters", ["post_id"])
    op.create_index("ix_content_filters_comment_id", "content_filters", ["comment_id"])
    op.create_index(
        "ix_content_filters_is_relevant", "content_filters", ["is_relevant"]
    )
    op.create_index(
        "ix_content_filters_relevance_score", "content_filters", ["relevance_score"]
    )
    op.create_index(
        "ix_content_filters_processed_at", "content_filters", ["processed_at"]
    )
    # Composite index for relevant content queries
    op.create_index(
        "ix_content_filters_relevant_score",
        "content_filters",
        ["is_relevant", "relevance_score"],
    )

    # Content Summaries - for summary pipeline queries
    op.create_index(
        "ix_content_summaries_filter_id", "content_summaries", ["content_filter_id"]
    )
    op.create_index(
        "ix_content_summaries_sentiment", "content_summaries", ["sentiment"]
    )
    op.create_index(
        "ix_content_summaries_confidence_score",
        "content_summaries",
        ["confidence_score"],
    )
    op.create_index(
        "ix_content_summaries_model_used", "content_summaries", ["model_used"]
    )
    op.create_index(
        "ix_content_summaries_created_at", "content_summaries", ["created_at"]
    )

    # A2A Workflow Management Indexes (additional to existing ones)

    # A2A Tasks - enhanced indexing for workflow queries
    op.create_index("ix_a2a_tasks_agent_type", "a2a_tasks", ["agent_type"])
    op.create_index("ix_a2a_tasks_skill_name", "a2a_tasks", ["skill_name"])
    op.create_index("ix_a2a_tasks_priority", "a2a_tasks", ["priority"])
    op.create_index("ix_a2a_tasks_retry_count", "a2a_tasks", ["retry_count"])
    op.create_index("ix_a2a_tasks_next_retry_at", "a2a_tasks", ["next_retry_at"])
    op.create_index("ix_a2a_tasks_correlation_id", "a2a_tasks", ["correlation_id"])
    # Composite indexes for task management
    op.create_index(
        "ix_a2a_tasks_agent_status_priority",
        "a2a_tasks",
        ["agent_type", "status", "priority"],
    )
    op.create_index(
        "ix_a2a_tasks_workflow_agent_status",
        "a2a_tasks",
        ["workflow_id", "agent_type", "status"],
    )

    # A2A Workflows - for workflow management
    op.create_index(
        "ix_a2a_workflows_workflow_type", "a2a_workflows", ["workflow_type"]
    )
    op.create_index("ix_a2a_workflows_status", "a2a_workflows", ["status"])
    op.create_index("ix_a2a_workflows_next_run", "a2a_workflows", ["next_run"])
    op.create_index("ix_a2a_workflows_last_run", "a2a_workflows", ["last_run"])
    # Composite for scheduled workflow queries
    op.create_index(
        "ix_a2a_workflows_status_next_run", "a2a_workflows", ["status", "next_run"]
    )

    # Alert and Notification Indexes

    # Alert Batches - for alert delivery management
    op.create_index("ix_alert_batches_status", "alert_batches", ["status"])
    op.create_index("ix_alert_batches_priority", "alert_batches", ["priority"])
    op.create_index(
        "ix_alert_batches_schedule_type", "alert_batches", ["schedule_type"]
    )
    op.create_index("ix_alert_batches_created_at", "alert_batches", ["created_at"])
    # Composite for pending alert queries
    op.create_index(
        "ix_alert_batches_status_priority_created",
        "alert_batches",
        ["status", "priority", "created_at"],
    )

    # Alert Deliveries - enhanced indexing (note: some indexes already exist)
    op.create_index(
        "ix_alert_deliveries_alert_batch_id", "alert_deliveries", ["alert_batch_id"]
    )
    op.create_index("ix_alert_deliveries_channel", "alert_deliveries", ["channel"])
    op.create_index(
        "ix_alert_deliveries_retry_count", "alert_deliveries", ["retry_count"]
    )
    # Composite for delivery tracking
    op.create_index(
        "ix_alert_deliveries_channel_status", "alert_deliveries", ["channel", "status"]
    )

    # Agent Coordination Indexes (additional to existing ones)

    # Agent States - enhanced performance monitoring
    op.create_index("ix_agent_states_agent_type", "agent_states", ["agent_type"])
    op.create_index(
        "ix_agent_states_current_task_id", "agent_states", ["current_task_id"]
    )
    op.create_index("ix_agent_states_heartbeat_at", "agent_states", ["heartbeat_at"])
    # Composite for health monitoring
    op.create_index(
        "ix_agent_states_type_status_heartbeat",
        "agent_states",
        ["agent_type", "status", "heartbeat_at"],
    )

    # Legacy Coordinator Tables Indexes

    # Agent Tasks - for workflow coordination compatibility
    op.create_index("ix_agent_tasks_workflow_id", "agent_tasks", ["workflow_id"])
    op.create_index("ix_agent_tasks_agent_type", "agent_tasks", ["agent_type"])
    op.create_index("ix_agent_tasks_task_type", "agent_tasks", ["task_type"])
    op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])
    op.create_index("ix_agent_tasks_created_at", "agent_tasks", ["created_at"])
    # Composite for workflow task queries
    op.create_index(
        "ix_agent_tasks_workflow_status", "agent_tasks", ["workflow_id", "status"]
    )
    op.create_index(
        "ix_agent_tasks_workflow_agent_status",
        "agent_tasks",
        ["workflow_id", "agent_type", "status"],
    )

    # Workflow Executions - for execution tracking
    op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])
    op.create_index(
        "ix_workflow_executions_started_at", "workflow_executions", ["started_at"]
    )
    op.create_index(
        "ix_workflow_executions_completed_at", "workflow_executions", ["completed_at"]
    )
    # Composite for execution monitoring
    op.create_index(
        "ix_workflow_executions_status_started",
        "workflow_executions",
        ["status", "started_at"],
    )


def downgrade() -> None:
    """Remove database indexes added for performance optimization."""

    # Legacy Coordinator Tables Indexes
    op.drop_index("ix_workflow_executions_status_started")
    op.drop_index("ix_workflow_executions_completed_at")
    op.drop_index("ix_workflow_executions_started_at")
    op.drop_index("ix_workflow_executions_status")

    op.drop_index("ix_agent_tasks_workflow_agent_status")
    op.drop_index("ix_agent_tasks_workflow_status")
    op.drop_index("ix_agent_tasks_created_at")
    op.drop_index("ix_agent_tasks_status")
    op.drop_index("ix_agent_tasks_task_type")
    op.drop_index("ix_agent_tasks_agent_type")
    op.drop_index("ix_agent_tasks_workflow_id")

    # Agent Coordination Indexes
    op.drop_index("ix_agent_states_type_status_heartbeat")
    op.drop_index("ix_agent_states_heartbeat_at")
    op.drop_index("ix_agent_states_current_task_id")
    op.drop_index("ix_agent_states_agent_type")

    # Alert and Notification Indexes
    op.drop_index("ix_alert_deliveries_channel_status")
    op.drop_index("ix_alert_deliveries_retry_count")
    op.drop_index("ix_alert_deliveries_channel")
    op.drop_index("ix_alert_deliveries_alert_batch_id")

    op.drop_index("ix_alert_batches_status_priority_created")
    op.drop_index("ix_alert_batches_created_at")
    op.drop_index("ix_alert_batches_schedule_type")
    op.drop_index("ix_alert_batches_priority")
    op.drop_index("ix_alert_batches_status")

    # A2A Workflow Management Indexes
    op.drop_index("ix_a2a_workflows_status_next_run")
    op.drop_index("ix_a2a_workflows_last_run")
    op.drop_index("ix_a2a_workflows_next_run")
    op.drop_index("ix_a2a_workflows_status")
    op.drop_index("ix_a2a_workflows_workflow_type")

    op.drop_index("ix_a2a_tasks_workflow_agent_status")
    op.drop_index("ix_a2a_tasks_agent_status_priority")
    op.drop_index("ix_a2a_tasks_correlation_id")
    op.drop_index("ix_a2a_tasks_next_retry_at")
    op.drop_index("ix_a2a_tasks_retry_count")
    op.drop_index("ix_a2a_tasks_priority")
    op.drop_index("ix_a2a_tasks_skill_name")
    op.drop_index("ix_a2a_tasks_agent_type")

    # Content Processing Indexes
    op.drop_index("ix_content_summaries_created_at")
    op.drop_index("ix_content_summaries_model_used")
    op.drop_index("ix_content_summaries_confidence_score")
    op.drop_index("ix_content_summaries_sentiment")
    op.drop_index("ix_content_summaries_filter_id")

    op.drop_index("ix_content_filters_relevant_score")
    op.drop_index("ix_content_filters_processed_at")
    op.drop_index("ix_content_filters_relevance_score")
    op.drop_index("ix_content_filters_is_relevant")
    op.drop_index("ix_content_filters_comment_id")
    op.drop_index("ix_content_filters_post_id")

    # Reddit Comments Indexes
    op.drop_index("ix_reddit_comments_post_created")
    op.drop_index("ix_reddit_comments_parent_comment_fk_id")
    op.drop_index("ix_reddit_comments_subreddit_fk_id")
    op.drop_index("ix_reddit_comments_post_fk_id")
    op.drop_index("ix_reddit_comments_parent_id")
    op.drop_index("ix_reddit_comments_created_utc")
    op.drop_index("ix_reddit_comments_score")
    op.drop_index("ix_reddit_comments_author")
    op.drop_index("ix_reddit_comments_post_id")

    # Reddit Posts Indexes
    op.drop_index("ix_reddit_posts_subreddit_score")
    op.drop_index("ix_reddit_posts_topic_created")
    op.drop_index("ix_reddit_posts_subreddit_fk_id")
    op.drop_index("ix_reddit_posts_created_utc")
    op.drop_index("ix_reddit_posts_topic")
    op.drop_index("ix_reddit_posts_score")
    op.drop_index("ix_reddit_posts_author")
    op.drop_index("ix_reddit_posts_subreddit_created")

    # Subreddits Indexes
    op.drop_index("ix_subreddits_discovered_at")
    op.drop_index("ix_subreddits_last_checked")
    op.drop_index("ix_subreddits_is_active")
