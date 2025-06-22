# ABOUTME: A2A communication integration tests
# ABOUTME: Tests agent-to-agent communication, service discovery, and skill invocation

import asyncio

import pytest

from tests.integration.a2a_test_framework import A2ATestFramework


class TestA2ACommunication:
    """Test A2A agent communication functionality"""

    @pytest.mark.asyncio
    async def test_all_agents_health(self):
        """Test that all agents respond to health checks"""
        async with A2ATestFramework() as framework:
            results = await framework.validate_all_agents()

            # All agents should be healthy
            for agent_name, result in results.items():
                assert result.success, (
                    f"Agent '{agent_name}' failed validation: {result.message}"
                )
                assert result.data is not None, (
                    f"Agent '{agent_name}' returned no health data"
                )

    @pytest.mark.asyncio
    async def test_agent_cards_valid(self):
        """Test that all agents have valid Agent Cards"""
        async with A2ATestFramework() as framework:
            agent_names = ["coordinator", "retrieval", "filter", "summarise", "alert"]

            for agent_name in agent_names:
                result = await framework.get_agent_card(agent_name)

                assert result.success, (
                    f"Agent '{agent_name}' card validation failed: {result.message}"
                )
                assert result.data is not None, (
                    f"Agent '{agent_name}' returned no card data"
                )

                # Validate specific card structure
                card_data = result.data
                assert "name" in card_data, f"Agent '{agent_name}' card missing 'name'"
                assert "skills" in card_data, (
                    f"Agent '{agent_name}' card missing 'skills'"
                )
                assert "version" in card_data, (
                    f"Agent '{agent_name}' card missing 'version'"
                )
                assert len(card_data["skills"]) > 0, (
                    f"Agent '{agent_name}' has no skills"
                )

    @pytest.mark.asyncio
    async def test_redis_service_discovery(self):
        """Test agent discovery through Redis service registry"""
        async with A2ATestFramework() as framework:
            result = await framework.discover_agents_via_redis()

            assert result.success, f"Redis service discovery failed: {result.message}"
            assert result.data is not None, "No service discovery data returned"

            # Should discover at least some agents
            agents = result.data.get("agents", {})
            assert len(agents) > 0, "No agents discovered via Redis"

    @pytest.mark.asyncio
    async def test_retrieval_agent_skills(self):
        """Test RetrievalAgent skill invocation"""
        async with A2ATestFramework() as framework:
            # Test fetch_posts_by_topic skill
            result = await framework.invoke_agent_skill(
                "retrieval",
                "fetch_posts_by_topic",
                {"topic": "Claude Code", "limit": 5, "subreddit": "all"},
            )

            assert result.success, (
                f"RetrievalAgent fetch_posts_by_topic failed: {result.message}"
            )
            assert result.data is not None, "No data returned from fetch_posts"

            # Validate response structure
            response_data = result.data
            assert "posts" in response_data or "result" in response_data, (
                "Invalid response structure"
            )

    @pytest.mark.asyncio
    async def test_filter_agent_skills(self):
        """Test FilterAgent skill invocation"""
        async with A2ATestFramework() as framework:
            # Test filter_content_by_keywords skill
            result = await framework.invoke_agent_skill(
                "filter",
                "filter_content_by_keywords",
                {
                    "content": "Claude Code is amazing Great AI development tool",
                    "title": "Claude Code is amazing",
                    "topics": ["claude", "code", "ai"],
                },
            )

            assert result.success, (
                f"FilterAgent filter_content_by_keywords failed: {result.message}"
            )
            assert result.data is not None, (
                "No data returned from filter_content_by_keywords"
            )

    @pytest.mark.asyncio
    async def test_summarise_agent_skills(self):
        """Test SummariseAgent skill invocation"""
        async with A2ATestFramework() as framework:
            # Test summarizeContent skill
            result = await framework.invoke_agent_skill(
                "summarise",
                "summarizeContent",
                {
                    "content": [
                        {
                            "title": "Claude Code Discussion",
                            "text": "Claude Code is a powerful AI development tool. It supports A2A protocol for agent communication.",
                            "metadata": {"source": "reddit", "score": 42},
                        }
                    ],
                    "max_length": 100,
                },
            )

            assert result.success, (
                f"SummariseAgent summarizeContent failed: {result.message}"
            )
            assert result.data is not None, "No data returned from summarizeContent"

    @pytest.mark.asyncio
    async def test_alert_agent_skills(self):
        """Test AlertAgent skill invocation"""
        async with A2ATestFramework() as framework:
            # Test sendSlack skill
            result = await framework.invoke_agent_skill(
                "alert",
                "sendSlack",
                {
                    "message": "Test alert from integration test",
                    "channel": "#test-alerts",
                    "urgency": "low",
                },
            )

            assert result.success, f"AlertAgent sendSlack failed: {result.message}"
            assert result.data is not None, "No data returned from sendSlack"

    @pytest.mark.asyncio
    async def test_agent_to_agent_communication_chain(self):
        """Test a chain of agent-to-agent communications"""
        async with A2ATestFramework() as framework:
            # Step 1: Retrieval -> Filter
            retrieval_result = await framework.test_agent_to_agent_communication(
                "coordinator",
                "retrieval",
                "fetch_posts_by_topic",
                {"topic": "Claude Code", "limit": 3, "subreddit": "all"},
            )

            assert retrieval_result.success, (
                f"Retrieval step failed: {retrieval_result.message}"
            )

            # Step 2: Use retrieval results for filtering
            filter_result = await framework.test_agent_to_agent_communication(
                "retrieval",
                "filter",
                "filter_content_by_keywords",
                {
                    "content": "Claude Code discussion content",
                    "title": "Claude Code",
                    "topics": ["claude", "code"],
                },
            )

            assert filter_result.success, f"Filter step failed: {filter_result.message}"

    @pytest.mark.asyncio
    async def test_coordinator_workflow_orchestration(self):
        """Test workflow orchestration through CoordinatorAgent"""
        async with A2ATestFramework() as framework:
            result = await framework.test_workflow_orchestration(
                "reddit_monitoring",
                {"query": "Claude Code", "max_posts": 5, "test_mode": True},
            )

            assert result.success, f"Workflow orchestration failed: {result.message}"
            assert result.data is not None, "No workflow data returned"

    @pytest.mark.asyncio
    async def test_concurrent_agent_requests(self):
        """Test concurrent requests to multiple agents"""
        async with A2ATestFramework() as framework:
            # Create multiple concurrent requests
            tasks = [
                framework.invoke_agent_skill("retrieval", "health_check"),
                framework.invoke_agent_skill("filter", "health_check"),
                framework.invoke_agent_skill("summarise", "health_check"),
                framework.invoke_agent_skill("alert", "health_check"),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All requests should succeed
            for i, result in enumerate(results):
                assert not isinstance(result, Exception), (
                    f"Task {i} raised exception: {result}"
                )
                assert result.success, (
                    f"Concurrent request {i} failed: {result.message}"
                )

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling in A2A communication"""
        async with A2ATestFramework() as framework:
            # Test invalid skill invocation
            result = await framework.invoke_agent_skill(
                "retrieval", "nonexistent_skill", {}
            )

            # Should handle error gracefully
            assert not result.success, "Invalid skill invocation should fail"
            assert result.error_details is not None, "Error details should be provided"

    @pytest.mark.asyncio
    async def test_response_time_performance(self):
        """Test A2A communication response times"""
        async with A2ATestFramework() as framework:
            # Test health check response times
            agents = ["coordinator", "retrieval", "filter", "summarise", "alert"]

            for agent_name in agents:
                result = await framework.wait_for_agent_health(agent_name)

                assert result.success, f"Agent '{agent_name}' health check failed"
                assert result.response_time_ms is not None, (
                    f"No response time recorded for '{agent_name}'"
                )
                assert result.response_time_ms < 5000, (
                    f"Agent '{agent_name}' response time too slow: {result.response_time_ms}ms"
                )
