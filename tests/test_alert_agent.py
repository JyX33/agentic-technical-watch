# ABOUTME: Tests for AlertAgent multi-channel notification functionality
# ABOUTME: Covers Slack webhook and SMTP email delivery with mocking and integration testing

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from aioresponses import aioresponses

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import reset_settings


class TestAlertAgent:
    """Test suite for AlertAgent functionality."""

    @pytest.fixture(autouse=True)
    def setup_test_settings(self, monkeypatch):
        """Set up test configuration for each test."""
        reset_settings()

        # Mock environment variables for testing
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test/webhook")
        monkeypatch.setenv("SMTP_SERVER", "smtp.test.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USERNAME", "test@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "testpass")
        monkeypatch.setenv("EMAIL_RECIPIENTS", '["user1@test.com", "user2@test.com"]')

        # Reset settings to pick up new environment
        reset_settings()

    @pytest.fixture
    def alert_agent(self):
        """Create AlertAgent instance for testing."""
        return AlertAgent()

    def test_agent_initialization(self, alert_agent):
        """Test AlertAgent initialization and basic properties."""
        assert alert_agent.agent_type == "alert"
        assert alert_agent.name == "Alert Notification Agent"
        assert alert_agent.version == "1.0.0"
        assert (
            "Delivers notifications via Slack webhooks and SMTP email"
            in alert_agent.description
        )

    def test_agent_skills(self, alert_agent):
        """Test that AlertAgent defines correct skills."""
        skills = alert_agent.get_skills()
        skill_names = [skill.name for skill in skills]

        assert "sendSlack" in skill_names
        assert "sendEmail" in skill_names
        assert "health_check" in skill_names
        assert len(skills) == 3

    def test_agent_card_generation(self, alert_agent):
        """Test Agent Card generation for A2A discovery."""
        agent_card = alert_agent.generate_agent_card()

        assert agent_card.name == "Alert Notification Agent"
        assert agent_card.version == "1.0.0"
        assert len(agent_card.skills) == 3

        # Check JSON serialization
        agent_card_json = alert_agent.get_agent_card_json()
        assert isinstance(agent_card_json, str)
        parsed_card = json.loads(agent_card_json)
        assert parsed_card["name"] == "Alert Notification Agent"

    def test_send_slack_alert_success(self, alert_agent):
        """Test successful Slack alert delivery."""
        # Mock database session
        with patch("reddit_watcher.agents.alert_agent.get_db_session"):
            with aioresponses() as m:
                # Mock Slack webhook response
                m.post("https://hooks.slack.com/test/webhook", payload={"ok": True})

                # Test parameters
                params = {
                    "message": "Test alert message",
                    "title": "Test Alert",
                    "priority": "high",
                    "metadata": {"source": "test", "topic": "Claude Code"},
                }

                # Execute skill
                result = asyncio.run(alert_agent.execute_skill("sendSlack", params))

                # Verify result
                assert result["status"] == "success"
                assert result["channel"] == "slack"
                assert "deduplication_hash" in result
                assert "timestamp" in result

    def test_send_slack_alert_deduplication(self, alert_agent):
        """Test Slack alert deduplication prevents duplicates."""
        with patch("reddit_watcher.agents.alert_agent.get_db_session"):
            with aioresponses() as m:
                # Mock Slack webhook response
                m.post("https://hooks.slack.com/test/webhook", payload={"ok": True})

                params = {
                    "message": "Duplicate test message",
                    "title": "Duplicate Alert",
                    "priority": "medium",
                }

                # Send first alert
                result1 = asyncio.run(alert_agent.execute_skill("sendSlack", params))
                assert result1["status"] == "success"

                # Send identical alert - should be deduplicated
                result2 = asyncio.run(alert_agent.execute_skill("sendSlack", params))
                assert result2["status"] == "skipped"
                assert result2["reason"] == "duplicate_alert"
                assert result2["deduplication_hash"] == result1["deduplication_hash"]

    def test_send_slack_alert_error_handling(self, alert_agent):
        """Test Slack alert error handling."""
        with patch("reddit_watcher.agents.alert_agent.get_db_session"):
            with aioresponses() as m:
                # Mock failing Slack webhook response
                m.post(
                    "https://hooks.slack.com/test/webhook",
                    status=400,
                    payload={"error": "invalid_payload"},
                )

                params = {"message": "Test error message", "title": "Test Error Alert"}

                result = asyncio.run(alert_agent.execute_skill("sendSlack", params))

                assert result["status"] == "error"
                assert "Slack API error 400" in result["error"]

    def test_send_email_alert_success(self, alert_agent):
        """Test successful email alert delivery."""
        with (
            patch("reddit_watcher.agents.alert_agent.get_db_session"),
            patch("smtplib.SMTP") as mock_smtp,
        ):
            # Mock SMTP server
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            params = {
                "message": "Test email alert message",
                "subject": "Test Email Alert",
                "priority": "critical",
                "metadata": {"urgency": "immediate", "source": "reddit"},
            }

            result = asyncio.run(alert_agent.execute_skill("sendEmail", params))

            # Verify result
            assert result["status"] == "success"
            assert result["channel"] == "email"
            assert result["recipients"] == ["user1@test.com", "user2@test.com"]

            # Verify SMTP calls
            mock_smtp.assert_called_once_with("smtp.test.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("test@example.com", "testpass")
            mock_server.send_message.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_alert_deduplication(self, alert_agent):
        """Test email alert deduplication."""
        with (
            patch("reddit_watcher.agents.alert_agent.get_db_session"),
            patch("smtplib.SMTP"),
        ):
            params = {
                "message": "Duplicate email message",
                "subject": "Duplicate Email Alert",
            }

            # Send first email
            result1 = asyncio.run(alert_agent.execute_skill("sendEmail", params))
            assert result1["status"] == "success"

            # Send identical email - should be deduplicated
            result2 = asyncio.run(alert_agent.execute_skill("sendEmail", params))
            assert result2["status"] == "skipped"
            assert result2["reason"] == "duplicate_alert"

    def test_send_email_smtp_error(self, alert_agent):
        """Test email alert SMTP error handling."""
        with (
            patch("reddit_watcher.agents.alert_agent.get_db_session"),
            patch("smtplib.SMTP") as mock_smtp,
        ):
            # Mock SMTP connection failure
            mock_smtp.side_effect = Exception("SMTP connection failed")

            params = {"message": "Test SMTP error", "subject": "SMTP Error Test"}

            result = asyncio.run(alert_agent.execute_skill("sendEmail", params))

            assert result["status"] == "error"
            assert "SMTP connection failed" in result["error"]

    def test_health_check_basic(self, alert_agent):
        """Test basic health check without connectivity test."""
        result = asyncio.run(alert_agent.execute_skill("health_check", {}))

        assert result["agent_type"] == "alert"
        assert result["name"] == "Alert Notification Agent"
        assert result["status"] == "healthy"
        assert result["slack_configured"] is True
        assert result["smtp_configured"] is True
        assert result["email_recipients"] == 2

    def test_health_check_with_connectivity(self, alert_agent):
        """Test health check with connectivity testing."""
        with aioresponses() as m:
            # Mock Slack webhook connectivity test
            m.post("https://hooks.slack.com/test/webhook", payload={"ok": True})

            with patch("smtplib.SMTP") as mock_smtp:
                # Mock SMTP connectivity test
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server

                result = asyncio.run(
                    alert_agent.execute_skill(
                        "health_check", {"check_connectivity": True}
                    )
                )

                assert result["connectivity"]["slack"] == "connected"
                assert result["connectivity"]["smtp"] == "connected"

    def test_slack_message_formatting(self, alert_agent):
        """Test Slack message formatting with different priorities."""
        # Test different priority levels
        priorities = {
            "low": {"color": "#36a64f", "emoji": "🟢"},
            "medium": {"color": "#ff9500", "emoji": "🟡"},
            "high": {"color": "#ff0000", "emoji": "🔴"},
            "critical": {"color": "#8b0000", "emoji": "🚨"},
        }

        for priority, expected in priorities.items():
            message = alert_agent._format_slack_message(
                message="Test message",
                title=f"Test {priority} Alert",
                priority=priority,
                metadata={"test": "data"},
            )

            assert message["username"] == "Reddit Watcher"
            assert message["icon_emoji"] == ":robot_face:"

            attachment = message["attachments"][0]
            assert attachment["color"] == expected["color"]
            assert expected["emoji"] in attachment["title"]
            assert len(attachment["fields"]) == 1  # metadata field

    def test_email_template_rendering(self, alert_agent):
        """Test email template rendering with HTML and text."""
        html_content, text_content = alert_agent._format_email_content(
            message="Test email content",
            subject="Test Subject",
            priority="high",
            template_name="default",
            metadata={"source": "reddit", "count": 5},
        )

        # Test HTML content
        assert "Test Subject" in html_content
        assert "Test email content" in html_content
        assert "🔴" in html_content  # High priority emoji
        assert "Source: reddit" in html_content
        assert "Count: 5" in html_content

        # Test text content
        assert "Test Subject" in text_content
        assert "Test email content" in text_content
        assert "🔴" in text_content
        assert "Source: reddit" in text_content

    def test_deduplication_hash_generation(self, alert_agent):
        """Test deduplication hash generation consistency."""
        # Same content should generate same hash
        hash1 = alert_agent._generate_dedup_hash(
            "slack", "message", "title", {"key": "value"}
        )
        hash2 = alert_agent._generate_dedup_hash(
            "slack", "message", "title", {"key": "value"}
        )
        assert hash1 == hash2

        # Different content should generate different hashes
        hash3 = alert_agent._generate_dedup_hash(
            "slack", "different", "title", {"key": "value"}
        )
        assert hash1 != hash3

        # Different channels should generate different hashes
        hash4 = alert_agent._generate_dedup_hash(
            "email", "message", "title", {"key": "value"}
        )
        assert hash1 != hash4

    def test_invalid_skill_execution(self, alert_agent):
        """Test execution of invalid skill returns error."""
        result = asyncio.run(alert_agent.execute_skill("invalid_skill", {}))

        assert result["status"] == "error"
        assert "Unknown skill: invalid_skill" in result["error"]

    def test_slack_alert_missing_webhook(self, monkeypatch, alert_agent):
        """Test Slack alert fails gracefully when webhook not configured."""
        # Remove Slack webhook configuration
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
        reset_settings()

        params = {"message": "Test message", "title": "Test"}
        result = asyncio.run(alert_agent.execute_skill("sendSlack", params))

        assert result["status"] == "error"
        assert "Slack webhook not configured" in result["error"]

    def test_email_alert_missing_smtp(self, monkeypatch, alert_agent):
        """Test email alert fails gracefully when SMTP not configured."""
        # Remove SMTP configuration
        monkeypatch.setenv("SMTP_SERVER", "")
        reset_settings()

        params = {"message": "Test message", "subject": "Test"}
        result = asyncio.run(alert_agent.execute_skill("sendEmail", params))

        assert result["status"] == "error"
        assert "SMTP configuration not available" in result["error"]

    def test_email_alert_no_recipients(self, monkeypatch, alert_agent):
        """Test email alert fails when no recipients configured."""
        # Remove email recipients
        monkeypatch.setenv("EMAIL_RECIPIENTS", "[]")
        reset_settings()

        params = {"message": "Test message", "subject": "Test"}
        result = asyncio.run(alert_agent.execute_skill("sendEmail", params))

        assert result["status"] == "error"
        assert "No email recipients configured" in result["error"]
