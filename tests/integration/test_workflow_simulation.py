# ABOUTME: Complete workflow simulation and verification tests
# ABOUTME: Tests end-to-end A2A workflows including Reddit monitoring, filtering, summarization, and alerting

import asyncio
from typing import Any

import pytest

from tests.fixtures.assertions import A2AAssertions, RedditDataAssertions
from tests.integration.a2a_test_framework import A2ATestFramework, A2ATestResult


class TestWorkflowSimulation:
    """Test complete A2A workflow simulations"""

    @pytest.mark.asyncio
    async def test_complete_reddit_monitoring_workflow(self):
        """Test the complete Reddit monitoring workflow end-to-end"""
        async with A2ATestFramework() as framework:
            # Step 1: Ensure all agents are healthy
            await self._ensure_all_agents_healthy(framework)

            # Step 2: Retrieve posts
            retrieval_result = await framework.invoke_agent_skill(
                "retrieval",
                "fetch_posts",
                {"query": "Claude Code", "limit": 5, "sort": "relevance"},
            )

            A2AAssertions.assert_skill_execution_success(
                retrieval_result, "retrieval", "fetch_posts"
            )
            A2AAssertions.assert_posts_retrieved(
                retrieval_result, expected_min=1, expected_max=5
            )

            # Extract posts for next step
            posts = self._extract_posts_from_result(retrieval_result.data)
            original_post_count = len(posts)

            # Step 3: Filter posts for relevance
            filter_result = await framework.invoke_agent_skill(
                "filter",
                "keyword_filter",
                {
                    "content": posts,
                    "keywords": ["claude", "code", "ai", "agent"],
                    "threshold": 0.5,
                },
            )

            A2AAssertions.assert_skill_execution_success(
                filter_result, "filter", "keyword_filter"
            )
            A2AAssertions.assert_posts_filtered(filter_result, original_post_count)

            # Extract filtered posts for next step
            filtered_posts = self._extract_posts_from_result(filter_result.data)

            # Step 4: Generate summary
            summarise_result = await framework.invoke_agent_skill(
                "summarise",
                "summarize_content",
                {"content": filtered_posts, "max_length": 200},
            )

            A2AAssertions.assert_skill_execution_success(
                summarise_result, "summarise", "summarize_content"
            )
            A2AAssertions.assert_summary_generated(summarise_result, min_length=50)

            # Step 5: Send alert
            alert_result = await framework.invoke_agent_skill(
                "alert",
                "send_slack",
                {
                    "message": f"Reddit Monitoring Alert: {summarise_result.data.get('summary', 'Summary generated')}",
                    "channel": "#ai-alerts",
                    "urgency": "low",
                },
            )

            A2AAssertions.assert_skill_execution_success(
                alert_result, "alert", "send_slack"
            )
            A2AAssertions.assert_alert_sent(alert_result, expected_channel="#ai-alerts")

            # Verify complete workflow
            total_response_time = (
                retrieval_result.response_time_ms
                + filter_result.response_time_ms
                + summarise_result.response_time_ms
                + alert_result.response_time_ms
            )

            assert total_response_time < 30000, (
                f"Total workflow time too slow: {total_response_time}ms"
            )

    @pytest.mark.asyncio
    async def test_subreddit_discovery_workflow(self):
        """Test subreddit discovery and analysis workflow"""
        async with A2ATestFramework() as framework:
            # Step 1: Discover subreddits
            discovery_result = await framework.invoke_agent_skill(
                "retrieval",
                "discover_subreddits",
                {"query": "artificial intelligence", "limit": 10},
            )

            A2AAssertions.assert_skill_execution_success(
                discovery_result, "retrieval", "discover_subreddits"
            )

            # Validate subreddit data
            subreddits = self._extract_subreddits_from_result(discovery_result.data)
            assert len(subreddits) >= 1, "Should discover at least 1 subreddit"

            for subreddit in subreddits:
                RedditDataAssertions.assert_valid_subreddit(subreddit)

            # Step 2: Filter subreddits for relevance
            filter_result = await framework.invoke_agent_skill(
                "filter",
                "semantic_filter",
                {
                    "content": subreddits,
                    "target_topics": ["ai", "machine learning", "development"],
                    "similarity_threshold": 0.6,
                },
            )

            A2AAssertions.assert_skill_execution_success(
                filter_result, "filter", "semantic_filter"
            )

            filtered_subreddits = self._extract_subreddits_from_result(
                filter_result.data
            )
            assert len(filtered_subreddits) <= len(subreddits), (
                "Filtered count should not exceed original"
            )

    @pytest.mark.asyncio
    async def test_comment_analysis_workflow(self):
        """Test comment fetching and analysis workflow"""
        async with A2ATestFramework() as framework:
            # Step 1: Fetch comments for a specific post
            comments_result = await framework.invoke_agent_skill(
                "retrieval", "fetch_comments", {"post_id": "test_post_1", "limit": 50}
            )

            A2AAssertions.assert_skill_execution_success(
                comments_result, "retrieval", "fetch_comments"
            )

            # Validate comment data
            comments = self._extract_comments_from_result(comments_result.data)
            assert len(comments) >= 1, "Should retrieve at least 1 comment"

            for comment in comments:
                RedditDataAssertions.assert_valid_reddit_comment(comment)

            # Step 2: Filter comments for relevance
            filter_result = await framework.invoke_agent_skill(
                "filter",
                "keyword_filter",
                {
                    "content": comments,
                    "keywords": ["claude", "code", "ai", "protocol"],
                    "threshold": 0.3,
                },
            )

            A2AAssertions.assert_skill_execution_success(
                filter_result, "filter", "keyword_filter"
            )

            # Step 3: Summarize filtered comments
            filtered_comments = self._extract_comments_from_result(filter_result.data)
            if filtered_comments:
                summarise_result = await framework.invoke_agent_skill(
                    "summarise",
                    "summarize_content",
                    {"content": filtered_comments, "max_length": 150},
                )

                A2AAssertions.assert_skill_execution_success(
                    summarise_result, "summarise", "summarize_content"
                )
                A2AAssertions.assert_summary_generated(summarise_result, min_length=30)

    @pytest.mark.asyncio
    async def test_coordinator_orchestrated_workflow(self):
        """Test workflow orchestration through CoordinatorAgent"""
        async with A2ATestFramework() as framework:
            # Test coordinator orchestration
            workflow_result = await framework.test_workflow_orchestration(
                "reddit_monitoring",
                {
                    "query": "Claude Code",
                    "max_posts": 3,
                    "filter_threshold": 0.5,
                    "summary_length": 150,
                    "alert_channel": "#test-alerts",
                    "test_mode": True,
                },
            )

            A2AAssertions.assert_workflow_completed(workflow_result, expected_steps=4)

            # Verify workflow metadata
            workflow_data = workflow_result.data
            assert (
                "workflow_id" in workflow_data or "correlation_id" in workflow_data
            ), "Workflow should have tracking ID"
            assert "steps" in workflow_data or "results" in workflow_data, (
                "Workflow should include step results"
            )

    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(self):
        """Test error handling and recovery in workflows"""
        async with A2ATestFramework() as framework:
            # Simulate a workflow with an intentional error
            try:
                # Try to invoke non-existent skill
                error_result = await framework.invoke_agent_skill(
                    "retrieval", "nonexistent_skill", {"query": "test"}
                )

                A2AAssertions.assert_error_handled_gracefully(
                    error_result, "skill_not_found"
                )

            except Exception as e:
                pytest.fail(f"Workflow error handling failed with exception: {e}")

            # Verify that other agents are still functional after error
            health_check = await framework.invoke_agent_skill(
                "retrieval", "health_check"
            )
            A2AAssertions.assert_skill_execution_success(
                health_check, "retrieval", "health_check"
            )

    @pytest.mark.asyncio
    async def test_parallel_workflow_execution(self):
        """Test executing multiple workflows in parallel"""
        async with A2ATestFramework() as framework:
            # Create multiple workflow tasks
            workflow_tasks = [
                framework.invoke_agent_skill(
                    "retrieval", "fetch_posts", {"query": f"test_query_{i}", "limit": 2}
                )
                for i in range(3)
            ]

            # Execute workflows in parallel
            results = await asyncio.gather(*workflow_tasks, return_exceptions=True)

            # Validate parallel execution
            successful_workflows = [
                r for r in results if isinstance(r, A2ATestResult) and r.success
            ]
            assert len(successful_workflows) >= 2, (
                f"At least 2 parallel workflows should succeed, got {len(successful_workflows)}"
            )

            # Check response times for concurrent execution
            for _i, result in enumerate(successful_workflows):
                A2AAssertions.assert_response_time_acceptable(result, max_time_ms=8000)

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self):
        """Test that workflow state is properly maintained"""
        async with A2ATestFramework() as framework:
            # Execute first part of workflow
            retrieval_result = await framework.invoke_agent_skill(
                "retrieval",
                "fetch_posts",
                {
                    "query": "Claude Code",
                    "limit": 3,
                    "correlation_id": "test_workflow_123",
                },
            )

            A2AAssertions.assert_skill_execution_success(
                retrieval_result, "retrieval", "fetch_posts"
            )

            # Execute second part with same correlation ID
            posts = self._extract_posts_from_result(retrieval_result.data)
            filter_result = await framework.invoke_agent_skill(
                "filter",
                "keyword_filter",
                {
                    "content": posts,
                    "keywords": ["claude", "code"],
                    "correlation_id": "test_workflow_123",
                },
            )

            A2AAssertions.assert_skill_execution_success(
                filter_result, "filter", "keyword_filter"
            )

            # Verify correlation ID consistency (if implemented)
            if "correlation_id" in filter_result.data:
                assert filter_result.data["correlation_id"] == "test_workflow_123"

    @pytest.mark.asyncio
    async def test_workflow_performance_metrics(self):
        """Test workflow performance and resource usage"""
        async with A2ATestFramework() as framework:
            # Execute workflow multiple times to gather metrics
            execution_times = []

            for i in range(3):
                start_time = asyncio.get_event_loop().time()

                result = await framework.invoke_agent_skill(
                    "retrieval",
                    "fetch_posts",
                    {"query": f"performance_test_{i}", "limit": 2},
                )

                end_time = asyncio.get_event_loop().time()
                execution_time = (end_time - start_time) * 1000  # Convert to ms
                execution_times.append(execution_time)

                A2AAssertions.assert_skill_execution_success(
                    result, "retrieval", "fetch_posts"
                )

            # Analyze performance metrics
            avg_execution_time = sum(execution_times) / len(execution_times)
            max_execution_time = max(execution_times)

            assert avg_execution_time < 5000, (
                f"Average execution time too slow: {avg_execution_time}ms"
            )
            assert max_execution_time < 8000, (
                f"Max execution time too slow: {max_execution_time}ms"
            )

    # Helper methods

    async def _ensure_all_agents_healthy(self, framework: A2ATestFramework):
        """Ensure all agents are healthy before starting workflow"""
        agents = ["coordinator", "retrieval", "filter", "summarise", "alert"]

        for agent_name in agents:
            health_result = await framework.wait_for_agent_health(agent_name)
            A2AAssertions.assert_agent_healthy(health_result, agent_name)

    def _extract_posts_from_result(
        self, result_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract posts from various result data formats"""
        if "posts" in result_data:
            return result_data["posts"]
        elif "result" in result_data and isinstance(result_data["result"], list):
            return result_data["result"]
        elif isinstance(result_data, list):
            return result_data
        else:
            return []

    def _extract_comments_from_result(
        self, result_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract comments from various result data formats"""
        if "comments" in result_data:
            return result_data["comments"]
        elif "result" in result_data and isinstance(result_data["result"], list):
            return result_data["result"]
        elif isinstance(result_data, list):
            return result_data
        else:
            return []

    def _extract_subreddits_from_result(
        self, result_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract subreddits from various result data formats"""
        if "subreddits" in result_data:
            return result_data["subreddits"]
        elif "result" in result_data and isinstance(result_data["result"], list):
            return result_data["result"]
        elif isinstance(result_data, list):
            return result_data
        else:
            return []
