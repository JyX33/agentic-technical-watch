# Database Performance Indexes

This document describes the comprehensive database indexes added for Reddit Technical Watcher performance optimization.

## Overview

Migration `6d29cd557f0f` adds 68 database indexes to optimize query performance across all major query patterns in the Reddit Technical Watcher system.

## Index Categories

### 1. Core Reddit Content Indexes (15 indexes)

**Subreddits Table:**
- `ix_subreddits_is_active` - Filter active subreddits
- `ix_subreddits_last_checked` - Find subreddits needing refresh
- `ix_subreddits_discovered_at` - Timeline queries

**Reddit Posts Table:**
- `ix_reddit_posts_subreddit_created` - Composite: subreddit + timeline queries
- `ix_reddit_posts_author` - Author-based queries
- `ix_reddit_posts_score` - Sort by popularity
- `ix_reddit_posts_topic` - Filter by monitoring topic
- `ix_reddit_posts_created_utc` - Timeline queries
- `ix_reddit_posts_subreddit_fk_id` - Foreign key lookups
- `ix_reddit_posts_topic_created` - Composite: topic + timeline
- `ix_reddit_posts_subreddit_score` - Composite: subreddit + popularity

**Reddit Comments Table:**
- `ix_reddit_comments_post_id` - Find comments for posts
- `ix_reddit_comments_author` - Author-based queries
- `ix_reddit_comments_score` - Sort by popularity
- `ix_reddit_comments_created_utc` - Timeline queries

### 2. Relationship Indexes (5 indexes)

Foreign key optimization for joins:
- `ix_reddit_comments_post_fk_id` - Post relationships
- `ix_reddit_comments_subreddit_fk_id` - Subreddit relationships
- `ix_reddit_comments_parent_comment_fk_id` - Comment threading
- `ix_reddit_comments_parent_id` - Parent comment lookups
- `ix_reddit_comments_post_created` - Composite: post + timeline

### 3. Content Processing Indexes (10 indexes)

**Content Filters Table:**
- `ix_content_filters_post_id` - Link to posts
- `ix_content_filters_comment_id` - Link to comments
- `ix_content_filters_is_relevant` - Filter relevant content
- `ix_content_filters_relevance_score` - Sort by relevance
- `ix_content_filters_processed_at` - Processing timeline
- `ix_content_filters_relevant_score` - Composite: relevance + score

**Content Summaries Table:**
- `ix_content_summaries_filter_id` - Link to filters
- `ix_content_summaries_sentiment` - Filter by sentiment
- `ix_content_summaries_confidence_score` - Sort by confidence
- `ix_content_summaries_model_used` - Filter by AI model
- `ix_content_summaries_created_at` - Timeline queries

### 4. A2A Workflow Management Indexes (18 indexes)

**A2A Tasks Table:**
- `ix_a2a_tasks_agent_type` - Filter by agent type
- `ix_a2a_tasks_skill_name` - Filter by skill
- `ix_a2a_tasks_priority` - Priority-based processing
- `ix_a2a_tasks_retry_count` - Retry logic
- `ix_a2a_tasks_next_retry_at` - Retry scheduling
- `ix_a2a_tasks_correlation_id` - Correlation tracking
- `ix_a2a_tasks_agent_status_priority` - Composite: agent + status + priority
- `ix_a2a_tasks_workflow_agent_status` - Composite: workflow + agent + status

**A2A Workflows Table:**
- `ix_a2a_workflows_workflow_type` - Filter by type
- `ix_a2a_workflows_status` - Filter by status
- `ix_a2a_workflows_next_run` - Scheduling queries
- `ix_a2a_workflows_last_run` - Last execution tracking
- `ix_a2a_workflows_status_next_run` - Composite: status + scheduling

### 5. Alert and Notification Indexes (10 indexes)

**Alert Batches Table:**
- `ix_alert_batches_status` - Filter by delivery status
- `ix_alert_batches_priority` - Priority-based delivery
- `ix_alert_batches_schedule_type` - Schedule type filtering
- `ix_alert_batches_created_at` - Timeline queries
- `ix_alert_batches_status_priority_created` - Composite: status + priority + timeline

**Alert Deliveries Table:**
- `ix_alert_deliveries_alert_batch_id` - Link to batches
- `ix_alert_deliveries_channel` - Filter by delivery channel
- `ix_alert_deliveries_retry_count` - Retry tracking
- `ix_alert_deliveries_channel_status` - Composite: channel + status

### 6. Agent Coordination Indexes (5 indexes)

**Agent States Table:**
- `ix_agent_states_agent_type` - Filter by agent type
- `ix_agent_states_current_task_id` - Current task tracking
- `ix_agent_states_heartbeat_at` - Health monitoring
- `ix_agent_states_type_status_heartbeat` - Composite: health monitoring

### 7. Legacy Coordinator Indexes (10 indexes)

**Agent Tasks Table:**
- `ix_agent_tasks_workflow_id` - Workflow linkage
- `ix_agent_tasks_agent_type` - Agent filtering
- `ix_agent_tasks_task_type` - Task type filtering
- `ix_agent_tasks_status` - Status filtering
- `ix_agent_tasks_created_at` - Timeline queries
- `ix_agent_tasks_workflow_status` - Composite: workflow + status
- `ix_agent_tasks_workflow_agent_status` - Composite: workflow + agent + status

**Workflow Executions Table:**
- `ix_workflow_executions_status` - Status filtering
- `ix_workflow_executions_started_at` - Start time queries
- `ix_workflow_executions_completed_at` - Completion tracking
- `ix_workflow_executions_status_started` - Composite: status + timeline

## Performance Impact

These indexes are designed to optimize the following query patterns:

### High-Frequency Queries
1. **Reddit Content Retrieval** - Finding new posts/comments by subreddit and time
2. **Content Filtering** - Relevance scoring and filtering operations
3. **Workflow Management** - Task queuing and status tracking
4. **Alert Processing** - Delivery status and retry management

### Complex Queries
1. **Multi-table Joins** - Foreign key relationships optimized
2. **Composite Filtering** - Multiple criteria queries (topic + time, status + priority)
3. **Aggregation Queries** - Counting and grouping operations
4. **Timeline Queries** - Date-range and ordering operations

## Migration Details

- **Migration File:** `2025_06_22_1426-6d29cd557f0f_add_missing_database_indexes_for_.py`
- **Indexes Added:** 68 total
- **Rollback Support:** Complete downgrade() implementation
- **Database Support:** PostgreSQL optimized

## Usage Guidelines

### Index Maintenance
- Indexes are automatically maintained by PostgreSQL
- Monitor index usage via `pg_stat_user_indexes`
- Consider REINDEX if performance degrades over time

### Query Optimization
- Use EXPLAIN ANALYZE to verify index usage
- These indexes should eliminate most table scans
- Monitor slow query logs for additional optimization opportunities

### Development
- New queries should leverage existing indexes where possible
- Consider index impact when adding new columns
- Test query performance with realistic data volumes

## Monitoring

Use these queries to monitor index effectiveness:

```sql
-- Index usage statistics
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Unused indexes (potential cleanup candidates)
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND schemaname = 'public';

-- Table scan vs index scan ratio
SELECT schemaname, tablename, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE schemaname = 'public';
```

## Future Considerations

1. **Partial Indexes** - Consider for frequently filtered boolean columns
2. **Expression Indexes** - For computed columns or complex WHERE clauses
3. **Covering Indexes** - Include additional columns to avoid table lookups
4. **Index Clustering** - Physically order table data to match frequent access patterns
