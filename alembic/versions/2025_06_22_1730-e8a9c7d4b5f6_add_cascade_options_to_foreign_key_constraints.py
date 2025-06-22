"""Add cascade options to foreign key constraints for data integrity

Revision ID: e8a9c7d4b5f6
Revises: 6d29cd557f0f
Create Date: 2025-06-22 17:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8a9c7d4b5f6"
down_revision: str | Sequence[str] | None = "6d29cd557f0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add cascade options to foreign key constraints for proper data integrity."""

    # RedditPost table - subreddit_fk_id should be SET NULL when subreddit is deleted
    op.drop_constraint(
        "reddit_posts_subreddit_fk_id_fkey", "reddit_posts", type_="foreignkey"
    )
    op.create_foreign_key(
        "reddit_posts_subreddit_fk_id_fkey",
        "reddit_posts",
        "subreddits",
        ["subreddit_fk_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # RedditComment table
    # post_fk_id should CASCADE when post is deleted
    op.drop_constraint(
        "reddit_comments_post_fk_id_fkey", "reddit_comments", type_="foreignkey"
    )
    op.create_foreign_key(
        "reddit_comments_post_fk_id_fkey",
        "reddit_comments",
        "reddit_posts",
        ["post_fk_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # subreddit_fk_id should be SET NULL when subreddit is deleted
    op.drop_constraint(
        "reddit_comments_subreddit_fk_id_fkey", "reddit_comments", type_="foreignkey"
    )
    op.create_foreign_key(
        "reddit_comments_subreddit_fk_id_fkey",
        "reddit_comments",
        "subreddits",
        ["subreddit_fk_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # parent_comment_fk_id should CASCADE when parent comment is deleted
    op.drop_constraint(
        "reddit_comments_parent_comment_fk_id_fkey",
        "reddit_comments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "reddit_comments_parent_comment_fk_id_fkey",
        "reddit_comments",
        "reddit_comments",
        ["parent_comment_fk_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ContentFilter table
    # post_id should CASCADE when post is deleted
    op.drop_constraint(
        "content_filters_post_id_fkey", "content_filters", type_="foreignkey"
    )
    op.create_foreign_key(
        "content_filters_post_id_fkey",
        "content_filters",
        "reddit_posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # comment_id should CASCADE when comment is deleted
    op.drop_constraint(
        "content_filters_comment_id_fkey", "content_filters", type_="foreignkey"
    )
    op.create_foreign_key(
        "content_filters_comment_id_fkey",
        "content_filters",
        "reddit_comments",
        ["comment_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ContentSummary table
    # content_filter_id should CASCADE when content filter is deleted
    op.drop_constraint(
        "content_summaries_content_filter_id_fkey",
        "content_summaries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "content_summaries_content_filter_id_fkey",
        "content_summaries",
        "content_filters",
        ["content_filter_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # AlertDelivery table
    # alert_batch_id should CASCADE when alert batch is deleted
    op.drop_constraint(
        "alert_deliveries_alert_batch_id_fkey", "alert_deliveries", type_="foreignkey"
    )
    op.create_foreign_key(
        "alert_deliveries_alert_batch_id_fkey",
        "alert_deliveries",
        "alert_batches",
        ["alert_batch_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove cascade options from foreign key constraints."""

    # Reverse all the changes by recreating foreign keys without ondelete options

    # AlertDelivery table
    op.drop_constraint(
        "alert_deliveries_alert_batch_id_fkey", "alert_deliveries", type_="foreignkey"
    )
    op.create_foreign_key(
        "alert_deliveries_alert_batch_id_fkey",
        "alert_deliveries",
        "alert_batches",
        ["alert_batch_id"],
        ["id"],
    )

    # ContentSummary table
    op.drop_constraint(
        "content_summaries_content_filter_id_fkey",
        "content_summaries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "content_summaries_content_filter_id_fkey",
        "content_summaries",
        "content_filters",
        ["content_filter_id"],
        ["id"],
    )

    # ContentFilter table
    op.drop_constraint(
        "content_filters_comment_id_fkey", "content_filters", type_="foreignkey"
    )
    op.create_foreign_key(
        "content_filters_comment_id_fkey",
        "content_filters",
        "reddit_comments",
        ["comment_id"],
        ["id"],
    )

    op.drop_constraint(
        "content_filters_post_id_fkey", "content_filters", type_="foreignkey"
    )
    op.create_foreign_key(
        "content_filters_post_id_fkey",
        "content_filters",
        "reddit_posts",
        ["post_id"],
        ["id"],
    )

    # RedditComment table
    op.drop_constraint(
        "reddit_comments_parent_comment_fk_id_fkey",
        "reddit_comments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "reddit_comments_parent_comment_fk_id_fkey",
        "reddit_comments",
        "reddit_comments",
        ["parent_comment_fk_id"],
        ["id"],
    )

    op.drop_constraint(
        "reddit_comments_subreddit_fk_id_fkey", "reddit_comments", type_="foreignkey"
    )
    op.create_foreign_key(
        "reddit_comments_subreddit_fk_id_fkey",
        "reddit_comments",
        "subreddits",
        ["subreddit_fk_id"],
        ["id"],
    )

    op.drop_constraint(
        "reddit_comments_post_fk_id_fkey", "reddit_comments", type_="foreignkey"
    )
    op.create_foreign_key(
        "reddit_comments_post_fk_id_fkey",
        "reddit_comments",
        "reddit_posts",
        ["post_fk_id"],
        ["id"],
    )

    # RedditPost table
    op.drop_constraint(
        "reddit_posts_subreddit_fk_id_fkey", "reddit_posts", type_="foreignkey"
    )
    op.create_foreign_key(
        "reddit_posts_subreddit_fk_id_fkey",
        "reddit_posts",
        "subreddits",
        ["subreddit_fk_id"],
        ["id"],
    )
