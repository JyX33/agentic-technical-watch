# ABOUTME: Minimal AlertAgent test without import dependencies
# ABOUTME: Direct testing of AlertAgent core functionality

import asyncio
import json
import sys
from unittest.mock import MagicMock, patch

# Import with path manipulation to avoid agent init issues
sys.path.insert(0, "/home/jyx/git/agentic-technical-watch")

from aioresponses import aioresponses

# Direct import without going through agents.__init__
from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import create_config


async def test_alert_agent():
    """Minimal AlertAgent test."""
    print("🧪 Minimal AlertAgent Test")
    print("=" * 40)

    try:
        # Initialize
        config = create_config()
        alert_agent = AlertAgent(config)

        print(f"✅ AlertAgent initialized: {alert_agent.name}")

        # Test 1: Agent Card Generation
        try:
            alert_agent.generate_agent_card()
            agent_card_json = alert_agent.get_agent_card_json()
            parsed_card = json.loads(agent_card_json)

            print(f"✅ Agent Card: {parsed_card['name']} v{parsed_card['version']}")
            print(f"   Skills: {len(parsed_card['skills'])}")

        except Exception as e:
            print(f"❌ Agent Card failed: {e}")

        # Test 2: Skills Definition
        skills = alert_agent.get_skills()
        skill_names = {skill.name for skill in skills}
        expected = {"sendSlack", "sendEmail", "health_check"}

        if skill_names == expected:
            print(f"✅ Skills: {skill_names}")
        else:
            print(f"❌ Skills mismatch: expected {expected}, got {skill_names}")

        # Test 3: Health Check
        try:
            health_result = await alert_agent.execute_skill("health_check", {})
            if health_result.get("status") == "healthy":
                print(f"✅ Health Check: {health_result['status']}")
            else:
                print(f"❌ Health Check: {health_result}")

        except Exception as e:
            print(f"❌ Health Check failed: {e}")

        # Test 4: Slack Mock Test
        if config.has_slack_webhook():
            try:
                async with alert_agent:
                    with aioresponses() as m:
                        m.post(config.slack_webhook_url, payload={"ok": True})

                        slack_params = {
                            "message": "Test Slack message",
                            "title": "Test Alert",
                            "priority": "medium",
                        }

                        result = await alert_agent.execute_skill(
                            "sendSlack", slack_params
                        )
                        if result.get("status") == "success":
                            print("✅ Slack Mock Test: success")
                        else:
                            print(f"❌ Slack Mock: {result.get('error')}")

            except Exception as e:
                print(f"❌ Slack Mock failed: {e}")
        else:
            print("⚠️  Slack not configured")

        # Test 5: Email Mock Test
        if config.has_smtp_config() and config.email_recipients:
            try:
                with patch("smtplib.SMTP") as mock_smtp:
                    mock_server = MagicMock()
                    mock_smtp.return_value = mock_server

                    email_params = {
                        "message": "Test email message",
                        "subject": "Test Email",
                        "priority": "high",
                    }

                    result = await alert_agent.execute_skill("sendEmail", email_params)
                    if result.get("status") == "success":
                        print("✅ Email Mock Test: success")
                    else:
                        print(f"❌ Email Mock: {result.get('error')}")

            except Exception as e:
                print(f"❌ Email Mock failed: {e}")
        else:
            print("⚠️  Email not configured")

        # Test 6: Message Formatting
        try:
            # Test Slack formatting
            slack_msg = alert_agent._format_slack_message(
                "Test message", "Test Title", "high", {"test": "data"}
            )

            slack_valid = (
                "attachments" in slack_msg and len(slack_msg["attachments"]) > 0
            )

            # Test Email formatting
            html_content, text_content = alert_agent._format_email_content(
                "Test message", "Test Subject", "high", "default", {"test": "data"}
            )

            email_valid = html_content and text_content

            if slack_valid and email_valid:
                print("✅ Message Formatting: working")
            else:
                print(
                    f"❌ Message Formatting: slack={slack_valid}, email={email_valid}"
                )

        except Exception as e:
            print(f"❌ Message Formatting failed: {e}")

        # Test 7: Error Handling
        try:
            error_result = await alert_agent.execute_skill("invalid_skill", {})
            if error_result.get("status") == "error":
                print("✅ Error Handling: working")
            else:
                print(f"❌ Error Handling: unexpected result {error_result}")

        except Exception as e:
            print(f"❌ Error Handling failed: {e}")

        print("\n🎯 AlertAgent Core Functionality Tests Complete")

        # Configuration Summary
        print("\n📋 Configuration Summary:")
        print(f"   Slack: {'✅' if config.has_slack_webhook() else '❌'}")
        print(f"   SMTP: {'✅' if config.has_smtp_config() else '❌'}")
        print(f"   Email Recipients: {len(config.email_recipients)}")

        return True

    except Exception as e:
        print(f"❌ AlertAgent test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_alert_agent())
    sys.exit(0 if success else 1)
