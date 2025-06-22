# ABOUTME: Assertion helpers for A2A integration testing
# ABOUTME: Provides specialized assertions for validating A2A agent responses and workflows

from typing import Any

from ..integration.a2a_test_framework import A2ATestResult


class A2AAssertions:
    """Specialized assertions for A2A testing"""

    @staticmethod
    def assert_agent_healthy(result: A2ATestResult, agent_name: str):
        """Assert that an agent health check passed"""
        assert result.success, f"Agent '{agent_name}' is not healthy: {result.message}"
        assert result.data is not None, f"Agent '{agent_name}' returned no health data"
        assert result.response_time_ms is not None, (
            f"No response time recorded for '{agent_name}'"
        )
        assert result.response_time_ms < 10000, (
            f"Agent '{agent_name}' response too slow: {result.response_time_ms}ms"
        )

    @staticmethod
    def assert_agent_card_valid(
        result: A2ATestResult, agent_name: str, expected_skills: list[str]
    ):
        """Assert that an agent card is valid and contains expected skills"""
        assert result.success, (
            f"Agent '{agent_name}' card validation failed: {result.message}"
        )
        assert result.data is not None, f"Agent '{agent_name}' returned no card data"

        card_data = result.data
        required_fields = ["name", "description", "skills", "version"]

        for field in required_fields:
            assert field in card_data, (
                f"Agent '{agent_name}' card missing required field: {field}"
            )

        # Validate skills
        card_skills = [skill["name"] for skill in card_data.get("skills", [])]
        for expected_skill in expected_skills:
            assert expected_skill in card_skills, (
                f"Agent '{agent_name}' missing expected skill: {expected_skill}"
            )

    @staticmethod
    def assert_skill_execution_success(
        result: A2ATestResult, agent_name: str, skill_name: str
    ):
        """Assert that a skill execution was successful"""
        assert result.success, (
            f"Skill '{skill_name}' on agent '{agent_name}' failed: {result.message}"
        )
        assert result.data is not None, f"Skill '{skill_name}' returned no data"
        assert result.response_time_ms is not None, (
            f"No response time recorded for skill '{skill_name}'"
        )

    @staticmethod
    def assert_posts_retrieved(
        result: A2ATestResult, expected_min: int = 1, expected_max: int = 100
    ):
        """Assert that posts were retrieved successfully"""
        assert result.success, f"Post retrieval failed: {result.message}"
        assert result.data is not None, "No post data returned"

        # Extract posts from result data
        posts = []
        if "posts" in result.data:
            posts = result.data["posts"]
        elif "result" in result.data and isinstance(result.data["result"], list):
            posts = result.data["result"]
        elif isinstance(result.data, list):
            posts = result.data

        assert len(posts) >= expected_min, (
            f"Expected at least {expected_min} posts, got {len(posts)}"
        )
        assert len(posts) <= expected_max, (
            f"Expected at most {expected_max} posts, got {len(posts)}"
        )

        # Validate post structure
        for i, post in enumerate(posts):
            assert "id" in post, f"Post {i} missing 'id' field"
            assert "title" in post, f"Post {i} missing 'title' field"

    @staticmethod
    def assert_posts_filtered(result: A2ATestResult, original_count: int):
        """Assert that posts were filtered appropriately"""
        assert result.success, f"Post filtering failed: {result.message}"
        assert result.data is not None, "No filtered data returned"

        # Extract filtered posts
        filtered_posts = []
        if "filtered_posts" in result.data:
            filtered_posts = result.data["filtered_posts"]
        elif "result" in result.data and isinstance(result.data["result"], list):
            filtered_posts = result.data["result"]
        elif isinstance(result.data, list):
            filtered_posts = result.data

        # Filtered count should be <= original count
        assert len(filtered_posts) <= original_count, (
            f"Filtered count ({len(filtered_posts)}) should not exceed original count ({original_count})"
        )

        # Each filtered post should have relevance score
        for i, post in enumerate(filtered_posts):
            assert "relevance_score" in post or "score" in post, (
                f"Filtered post {i} missing relevance score"
            )

    @staticmethod
    def assert_summary_generated(result: A2ATestResult, min_length: int = 50):
        """Assert that a summary was generated successfully"""
        assert result.success, f"Summary generation failed: {result.message}"
        assert result.data is not None, "No summary data returned"

        # Extract summary text
        summary_text = ""
        if "summary" in result.data:
            summary_text = result.data["summary"]
        elif "result" in result.data and isinstance(result.data["result"], str):
            summary_text = result.data["result"]
        elif "text" in result.data:
            summary_text = result.data["text"]

        assert isinstance(summary_text, str), "Summary should be a string"
        assert len(summary_text) >= min_length, (
            f"Summary too short: {len(summary_text)} chars (min: {min_length})"
        )
        assert len(summary_text.strip()) > 0, "Summary is empty or whitespace only"

    @staticmethod
    def assert_alert_sent(result: A2ATestResult, expected_channel: str | None = None):
        """Assert that an alert was sent successfully"""
        assert result.success, f"Alert sending failed: {result.message}"
        assert result.data is not None, "No alert data returned"

        # Check for success indicators
        success_indicators = ["sent", "delivered", "ok", "success"]
        result_str = str(result.data).lower()

        has_success_indicator = any(
            indicator in result_str for indicator in success_indicators
        )
        assert has_success_indicator, (
            f"No success indicator found in alert result: {result.data}"
        )

        if expected_channel:
            assert expected_channel in result_str, (
                f"Expected channel '{expected_channel}' not found in result"
            )

    @staticmethod
    def assert_service_discovery_working(
        result: A2ATestResult, expected_agents: list[str]
    ):
        """Assert that service discovery is working and found expected agents"""
        assert result.success, f"Service discovery failed: {result.message}"
        assert result.data is not None, "No service discovery data returned"

        discovered_agents = result.data.get("agents", {})
        assert len(discovered_agents) > 0, "No agents discovered"

        for expected_agent in expected_agents:
            assert expected_agent in discovered_agents, (
                f"Expected agent '{expected_agent}' not discovered"
            )

    @staticmethod
    def assert_workflow_completed(result: A2ATestResult, expected_steps: int):
        """Assert that a workflow completed successfully"""
        assert result.success, f"Workflow execution failed: {result.message}"
        assert result.data is not None, "No workflow data returned"

        # Check for workflow completion indicators
        workflow_data = result.data

        if "steps_completed" in workflow_data:
            assert workflow_data["steps_completed"] >= expected_steps, (
                f"Expected {expected_steps} steps, completed {workflow_data['steps_completed']}"
            )

        if "status" in workflow_data:
            assert workflow_data["status"] in ["completed", "success"], (
                f"Workflow status: {workflow_data['status']}"
            )

    @staticmethod
    def assert_error_handled_gracefully(
        result: A2ATestResult, expected_error_type: str
    ):
        """Assert that an error was handled gracefully"""
        assert not result.success, "Expected operation to fail but it succeeded"
        assert result.error_details is not None, "No error details provided"

        error_details_lower = result.error_details.lower()
        expected_error_lower = expected_error_type.lower()

        assert expected_error_lower in error_details_lower, (
            f"Expected error type '{expected_error_type}' not found in error details: {result.error_details}"
        )

    @staticmethod
    def assert_response_time_acceptable(
        result: A2ATestResult, max_time_ms: float = 5000
    ):
        """Assert that response time is within acceptable limits"""
        assert result.response_time_ms is not None, "No response time recorded"
        assert result.response_time_ms <= max_time_ms, (
            f"Response time too slow: {result.response_time_ms}ms (max: {max_time_ms}ms)"
        )

    @staticmethod
    def assert_concurrent_requests_successful(
        results: list[A2ATestResult], min_success_rate: float = 0.8
    ):
        """Assert that concurrent requests mostly succeeded"""
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r.success)
        success_rate = successful_requests / total_requests if total_requests > 0 else 0

        assert success_rate >= min_success_rate, (
            f"Success rate too low: {success_rate:.2%} (min: {min_success_rate:.2%})"
        )

        # Check that all successful requests have reasonable response times
        for i, result in enumerate(results):
            if result.success:
                assert result.response_time_ms is not None, (
                    f"Request {i} missing response time"
                )
                assert result.response_time_ms < 10000, (
                    f"Request {i} response time too slow: {result.response_time_ms}ms"
                )


class RedditDataAssertions:
    """Specialized assertions for Reddit data validation"""

    @staticmethod
    def assert_valid_reddit_post(post: dict[str, Any]):
        """Assert that a Reddit post has the expected structure"""
        required_fields = ["id", "title", "author", "subreddit", "score", "created_utc"]

        for field in required_fields:
            assert field in post, f"Reddit post missing required field: {field}"

        # Validate field types
        assert isinstance(post["id"], str), "Post ID should be string"
        assert isinstance(post["title"], str), "Post title should be string"
        assert isinstance(post["score"], int), "Post score should be integer"
        assert isinstance(post["created_utc"], int | float), (
            "Post created_utc should be numeric"
        )

    @staticmethod
    def assert_valid_reddit_comment(comment: dict[str, Any]):
        """Assert that a Reddit comment has the expected structure"""
        required_fields = ["id", "body", "author", "score", "created_utc"]

        for field in required_fields:
            assert field in comment, f"Reddit comment missing required field: {field}"

        # Validate field types
        assert isinstance(comment["id"], str), "Comment ID should be string"
        assert isinstance(comment["body"], str), "Comment body should be string"
        assert isinstance(comment["score"], int), "Comment score should be integer"

    @staticmethod
    def assert_valid_subreddit(subreddit: dict[str, Any]):
        """Assert that a subreddit has the expected structure"""
        required_fields = ["display_name", "public_description", "subscribers"]

        for field in required_fields:
            assert field in subreddit, f"Subreddit missing required field: {field}"

        # Validate field types
        assert isinstance(subreddit["display_name"], str), (
            "Subreddit display_name should be string"
        )
        assert isinstance(subreddit["subscribers"], int), (
            "Subreddit subscribers should be integer"
        )


class MockAPIAssertions:
    """Specialized assertions for mock API validation"""

    @staticmethod
    def assert_mock_reddit_response(response_data: dict[str, Any]):
        """Assert that mock Reddit API response has correct structure"""
        assert "data" in response_data, "Mock Reddit response missing 'data' field"
        assert "children" in response_data["data"], (
            "Mock Reddit response missing 'children' field"
        )

        children = response_data["data"]["children"]
        assert isinstance(children, list), "Reddit children should be a list"

        for child in children:
            assert "data" in child, "Reddit child missing 'data' field"

    @staticmethod
    def assert_mock_gemini_response(response_data: dict[str, Any]):
        """Assert that mock Gemini API response has correct structure"""
        assert "candidates" in response_data, (
            "Mock Gemini response missing 'candidates' field"
        )
        assert "usageMetadata" in response_data, (
            "Mock Gemini response missing 'usageMetadata' field"
        )

        candidates = response_data["candidates"]
        assert isinstance(candidates, list), "Gemini candidates should be a list"
        assert len(candidates) > 0, "Gemini candidates should not be empty"

        for candidate in candidates:
            assert "content" in candidate, "Gemini candidate missing 'content' field"
            assert "parts" in candidate["content"], (
                "Gemini candidate content missing 'parts' field"
            )

    @staticmethod
    def assert_mock_slack_response(response_data: dict[str, Any]):
        """Assert that mock Slack webhook response has correct structure"""
        assert "ok" in response_data, "Mock Slack response missing 'ok' field"
        assert response_data["ok"] is True, "Mock Slack response indicates failure"
