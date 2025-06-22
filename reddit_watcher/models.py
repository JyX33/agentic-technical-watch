# ABOUTME: SQLAlchemy models for Reddit watcher data storage and A2A state management
# ABOUTME: Defines entities for Reddit content, agent tasks, and workflow orchestration

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.sql import func
from sqlalchemy.types import JSON, TypeDecorator


# Custom JSON type that works with both PostgreSQL and SQLite
class JSONType(TypeDecorator):
    """JSON type that works with PostgreSQL (JSONB) and SQLite (JSON)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TaskStatus(enum.Enum):
    """Task execution status for A2A workflow management."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentType(enum.Enum):
    """Type of Reddit content."""

    POST = "post"
    COMMENT = "comment"
    SUBREDDIT = "subreddit"


class AlertStatus(enum.Enum):
    """Alert delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# Core Reddit Content Models


class Subreddit(Base):
    """Subreddit entity for tracking monitored communities."""

    __tablename__ = "subreddits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    subscribers: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    posts: Mapped[list["RedditPost"]] = relationship(
        "RedditPost", back_populates="subreddit_obj"
    )
    comments: Mapped[list["RedditComment"]] = relationship(
        "RedditComment", back_populates="subreddit_obj"
    )


class RedditPost(Base):
    """Reddit post content."""

    __tablename__ = "reddit_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # Reddit post ID
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2000))
    author: Mapped[str | None] = mapped_column(String(100))
    subreddit: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Subreddit name
    score: Mapped[int] = mapped_column(Integer, default=0)
    upvote_ratio: Mapped[float | None] = mapped_column(Float)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    is_video: Mapped[bool] = mapped_column(Boolean, default=False)
    over_18: Mapped[bool] = mapped_column(Boolean, default=False)
    permalink: Mapped[str | None] = mapped_column(String(500))
    topic: Mapped[str | None] = mapped_column(String(200))  # Monitoring topic
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(  # Alias for compatibility
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    subreddit_fk_id: Mapped[int | None] = mapped_column(
        ForeignKey("subreddits.id"), nullable=True
    )

    # Relationships
    subreddit_obj: Mapped[Subreddit | None] = relationship(
        "Subreddit", back_populates="posts"
    )
    comments: Mapped[list["RedditComment"]] = relationship(
        "RedditComment", back_populates="post", cascade="all, delete-orphan"
    )
    content_filters: Mapped[list["ContentFilter"]] = relationship(
        "ContentFilter", back_populates="post", cascade="all, delete-orphan"
    )


class RedditComment(Base):
    """Reddit comment content."""

    __tablename__ = "reddit_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # Reddit comment ID
    post_id: Mapped[str] = mapped_column(String(20), nullable=False)  # Parent post ID
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(100))
    score: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[str | None] = mapped_column(String(20))  # Parent comment ID
    permalink: Mapped[str | None] = mapped_column(String(500))
    is_submitter: Mapped[bool] = mapped_column(Boolean, default=False)
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    post_fk_id: Mapped[int | None] = mapped_column(ForeignKey("reddit_posts.id"))
    subreddit_fk_id: Mapped[int | None] = mapped_column(
        ForeignKey("subreddits.id"), nullable=True
    )
    parent_comment_fk_id: Mapped[int | None] = mapped_column(
        ForeignKey("reddit_comments.id")
    )

    # Relationships
    post: Mapped[RedditPost | None] = relationship(
        "RedditPost", back_populates="comments"
    )
    subreddit_obj: Mapped[Subreddit | None] = relationship(
        "Subreddit", back_populates="comments"
    )
    parent_comment: Mapped[Optional["RedditComment"]] = relationship(
        "RedditComment", remote_side=[id]
    )
    content_filters: Mapped[list["ContentFilter"]] = relationship(
        "ContentFilter", back_populates="comment", cascade="all, delete-orphan"
    )


# Content Processing Models


class ContentFilter(Base):
    """Content filtering results from FilterAgent."""

    __tablename__ = "content_filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    keywords_matched: Mapped[list] = mapped_column(JSONType)
    semantic_similarity: Mapped[float | None] = mapped_column(Float)
    filter_reason: Mapped[str | None] = mapped_column(String(500))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys (one-to-one with content)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("reddit_posts.id"))
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("reddit_comments.id"))

    # Relationships
    post: Mapped[RedditPost | None] = relationship(
        "RedditPost", back_populates="content_filters"
    )
    comment: Mapped[RedditComment | None] = relationship(
        "RedditComment", back_populates="content_filters"
    )
    summaries: Mapped[list["ContentSummary"]] = relationship(
        "ContentSummary", back_populates="content_filter"
    )


class ContentSummary(Base):
    """AI-generated content summaries from SummariseAgent."""

    __tablename__ = "content_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[list] = mapped_column(JSONType)
    sentiment: Mapped[str | None] = mapped_column(String(50))
    confidence_score: Mapped[float | None] = mapped_column(Float)
    model_used: Mapped[str] = mapped_column(String(100), default="gemini-2.5-flash")
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    content_filter_id: Mapped[int] = mapped_column(
        ForeignKey("content_filters.id"), nullable=False
    )

    # Relationships
    content_filter: Mapped[ContentFilter] = relationship(
        "ContentFilter", back_populates="summaries"
    )
    # For many-to-many with AlertBatch, we'd need an association table


# A2A Workflow Management Models


class A2ATask(Base):
    """A2A protocol task tracking for workflow orchestration with idempotency."""

    __tablename__ = "a2a_tasks"
    __table_args__ = (
        UniqueConstraint("task_id", name="uix_a2a_tasks_task_id"),
        UniqueConstraint(
            "agent_type",
            "skill_name",
            "parameters_hash",
            "workflow_id",
            name="uix_a2a_tasks_idempotency",
        ),
        Index("ix_a2a_tasks_status_created", "status", "created_at"),
        Index("ix_a2a_tasks_workflow_status", "workflow_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )  # UUID as string
    agent_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "retrieval", "filter"
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONType)
    parameters_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA256 hash of parameters for idempotency
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING
    )
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1=highest, 10=lowest

    # Idempotency and state management
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str | None] = mapped_column(
        String(64)
    )  # Hash of content being processed
    lock_token: Mapped[str | None] = mapped_column(
        String(100)
    )  # For distributed locking
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Execution tracking
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Workflow context
    workflow_id: Mapped[str | None] = mapped_column(String(100))
    parent_task_id: Mapped[str | None] = mapped_column(String(100))

    # Result tracking
    result_data: Mapped[dict | None] = mapped_column(JSONType)
    result_hash: Mapped[str | None] = mapped_column(
        String(64)
    )  # Hash of result for caching

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class A2AWorkflow(Base):
    """A2A workflow orchestration state."""

    __tablename__ = "a2a_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    workflow_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "reddit_scan", "alert_batch"
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING
    )

    # Workflow configuration
    schedule: Mapped[str | None] = mapped_column(String(100))  # cron-like schedule
    config: Mapped[dict] = mapped_column(JSONType)

    # Execution tracking
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Alert and Notification Models


class AlertBatch(Base):
    """Batch of alerts for delivery via AlertAgent."""

    __tablename__ = "alert_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5)

    # Alert configuration
    channels: Mapped[list] = mapped_column(JSONType)  # ["slack", "email"]
    schedule_type: Mapped[str] = mapped_column(
        String(50), default="immediate"
    )  # "immediate", "hourly", "daily"

    # Delivery tracking
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.PENDING
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships would need association table for many-to-many
    # summaries: Mapped[list[ContentSummary]] = relationship("ContentSummary", secondary="alert_summary_association")


class AlertDelivery(Base):
    """Individual alert delivery tracking per channel."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "alert_batch_id",
            "channel",
            "recipient",
            name="uix_alert_deliveries_idempotency",
        ),
        Index("ix_alert_deliveries_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_batch_id: Mapped[int] = mapped_column(
        ForeignKey("alert_batches.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # "slack", "email"
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.PENDING
    )

    # Channel-specific details
    recipient: Mapped[str | None] = mapped_column(String(200))
    webhook_url: Mapped[str | None] = mapped_column(String(500))
    message_id: Mapped[str | None] = mapped_column(String(200))

    # Delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_time_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentState(Base):
    """Agent state synchronization and coordination."""

    __tablename__ = "agent_states"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uix_agent_states_agent_id"),
        Index("ix_agent_states_status_updated", "status", "last_updated"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="idle"
    )  # idle, busy, error, offline

    # State data
    state_data: Mapped[dict] = mapped_column(JSONType, default=dict)
    capabilities: Mapped[list] = mapped_column(JSONType, default=list)
    current_task_id: Mapped[str | None] = mapped_column(String(36))

    # Health monitoring
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    # Performance metrics
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_failed: Mapped[int] = mapped_column(Integer, default=0)
    avg_execution_time_ms: Mapped[float | None] = mapped_column(Float)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskRecovery(Base):
    """Task recovery state for interrupted or failed operations."""

    __tablename__ = "task_recoveries"
    __table_args__ = (
        UniqueConstraint("task_id", name="uix_task_recoveries_task_id"),
        Index("ix_task_recoveries_status_created", "recovery_status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    original_task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    recovery_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, recovering, completed, failed

    # Recovery strategy
    recovery_strategy: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # retry, rollback, skip, manual
    recovery_attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_recovery_attempts: Mapped[int] = mapped_column(Integer, default=3)

    # Recovery data
    checkpoint_data: Mapped[dict | None] = mapped_column(
        JSONType
    )  # State at failure point
    recovery_parameters: Mapped[dict | None] = mapped_column(
        JSONType
    )  # Custom recovery params
    failure_reason: Mapped[str | None] = mapped_column(Text)

    # Recovery execution
    recovery_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    recovery_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    recovery_error: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ContentDeduplication(Base):
    """Content deduplication tracking to prevent reprocessing."""

    __tablename__ = "content_deduplication"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uix_content_deduplication_hash"),
        UniqueConstraint(
            "content_type", "external_id", name="uix_content_deduplication_external"
        ),
        Index(
            "ix_content_deduplication_type_processed", "content_type", "processed_at"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )  # SHA256 of content
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    external_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Reddit ID, etc.

    # Processing status
    processing_status: Mapped[str] = mapped_column(
        String(50), default="new"
    )  # new, processing, completed, failed
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Metadata
    source_agent: Mapped[str | None] = mapped_column(String(100))
    workflow_id: Mapped[str | None] = mapped_column(String(100))
    extra_data: Mapped[dict | None] = mapped_column(JSONType)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Additional models for CoordinatorAgent compatibility


class AgentTask(Base):
    """Agent task tracking for workflow coordination (alias for A2ATask)."""

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    task_data: Mapped[dict] = mapped_column(JSONType)
    result_data: Mapped[dict | None] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowExecution(Base):
    """Workflow execution tracking for coordinator agent."""

    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topics: Mapped[list] = mapped_column(JSONType)
    subreddits: Mapped[list] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(50), default="running")

    # Execution metrics
    posts_processed: Mapped[int | None] = mapped_column(Integer, default=0)
    comments_processed: Mapped[int | None] = mapped_column(Integer, default=0)
    relevant_items: Mapped[int | None] = mapped_column(Integer, default=0)
    summaries_created: Mapped[int | None] = mapped_column(Integer, default=0)
    alerts_sent: Mapped[int | None] = mapped_column(Integer, default=0)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Database utilities


def create_database_engine(
    database_url: str,
    pool_size: int = 20,
    max_overflow: int = 30,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    echo: bool = False,
):
    """Create SQLAlchemy engine with configurable connection pooling."""
    return create_engine(
        database_url,
        echo=echo,  # Set to True for SQL logging
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
    )


def create_session_maker(engine):
    """Create SQLAlchemy session maker."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_tables(engine):
    """Create all database tables."""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all database tables (use with caution!)."""
    Base.metadata.drop_all(engine)
