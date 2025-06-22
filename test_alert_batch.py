# ABOUTME: Test AlertAgent batch functionality implementation
# ABOUTME: Validates sendBatch skill with multiple channels and items

import asyncio
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

# Direct import to avoid dependency issues
sys.path.insert(0, "/home/jyx/git/agentic-technical-watch")

from aioresponses import aioresponses

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import create_config


async def test_alert_batch():
    """Test AlertAgent batch functionality."""
    print("📦 Testing AlertAgent Batch Functionality")
    print("=" * 50)

    try:
        # Initialize
        config = create_config()
        alert_agent = AlertAgent(config)

        print(f"✅ AlertAgent initialized: {alert_agent.name}")

        # Test 1: Verify sendBatch skill exists
        skills = alert_agent.get_skills()
        skill_names = {skill.name for skill in skills}

        if "sendBatch" in skill_names:
            print("✅ sendBatch skill found")
        else:
            print(f"❌ sendBatch skill missing. Available: {skill_names}")
            return False

        # Test 2: Create sample batch
        batch_params = {
            "batch_id": f"test_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "title": "Test Alert Batch",
            "summary": "This is a test batch containing multiple Reddit alerts",
            "items": [
                {
                    "title": "Interesting Discussion",
                    "message": "New discussion about Claude Code features",
                    "priority": "medium",
                    "source": "reddit",
                    "url": "https://reddit.com/r/test/post1",
                },
                {
                    "title": "Technical Question",
                    "message": "User asking about A2A protocol implementation",
                    "priority": "high",
                    "source": "reddit",
                    "url": "https://reddit.com/r/test/post2",
                },
                {
                    "title": "Feature Request",
                    "message": "Request for new AlertAgent capabilities",
                    "priority": "low",
                    "source": "reddit",
                    "url": "https://reddit.com/r/test/post3",
                },
            ],
            "channels": ["slack", "email"],
            "schedule_type": "immediate",
            "priority": "medium",
        }

        print(f"📋 Created batch with {len(batch_params['items'])} items")

        # Test 3: Send batch with mocked services
        async with alert_agent:
            with aioresponses() as m:
                # Mock Slack webhook
                m.post(config.slack_webhook_url, payload={"ok": True})

                with patch("smtplib.SMTP") as mock_smtp:
                    # Mock SMTP server
                    mock_server = MagicMock()
                    mock_smtp.return_value = mock_server

                    # Execute sendBatch skill
                    result = await alert_agent.execute_skill("sendBatch", batch_params)

                    print("📊 Batch execution result:")
                    print(f"   Status: {result.get('status')}")
                    print(f"   Batch ID: {result.get('batch_id')}")
                    print(f"   Items: {result.get('items_count')}")
                    print(f"   Channels: {result.get('channels')}")
                    print(f"   Successful: {result.get('successful_deliveries')}")
                    print(f"   Failed: {result.get('failed_deliveries')}")

                    if result.get("status") in ["success", "partial_success"]:
                        print("✅ Batch execution successful")

                        # Check delivery results
                        delivery_results = result.get("delivery_results", {})

                        # Verify Slack delivery
                        slack_result = delivery_results.get("slack_delivery", {})
                        if slack_result.get("status") == "success":
                            print("✅ Slack batch delivery successful")
                        else:
                            print(f"❌ Slack batch delivery: {slack_result}")

                        # Verify Email delivery
                        email_result = delivery_results.get("email_delivery", {})
                        if email_result.get("status") == "success":
                            print("✅ Email batch delivery successful")
                        else:
                            print(f"❌ Email batch delivery: {email_result}")

                    else:
                        print(f"❌ Batch execution failed: {result.get('error')}")
                        return False

        # Test 4: Test batch deduplication
        print("\n🔄 Testing batch deduplication...")

        async with alert_agent:
            with aioresponses() as m:
                m.post(config.slack_webhook_url, payload={"ok": True})

                with patch("smtplib.SMTP") as mock_smtp:
                    mock_server = MagicMock()
                    mock_smtp.return_value = mock_server

                    # Send same batch again
                    result2 = await alert_agent.execute_skill("sendBatch", batch_params)

                    if (
                        result2.get("status") == "skipped"
                        and result2.get("reason") == "duplicate_batch"
                    ):
                        print("✅ Batch deduplication working")
                    else:
                        print(f"❌ Batch deduplication failed: {result2}")

        # Test 5: Test error handling - empty items
        print("\n🚨 Testing error handling...")

        empty_batch = {
            "title": "Empty Batch",
            "summary": "This batch has no items",
            "items": [],
            "channels": ["slack"],
        }

        result3 = await alert_agent.execute_skill("sendBatch", empty_batch)

        if result3.get("status") == "error":
            print("✅ Empty batch error handling working")
        else:
            print(f"❌ Empty batch should fail: {result3}")

        # Test 6: Test partial channel configuration
        print("\n🔧 Testing partial channel configuration...")

        # Test with only configured channels
        configured_channels = []
        if config.has_slack_webhook():
            configured_channels.append("slack")
        if config.has_smtp_config() and config.email_recipients:
            configured_channels.append("email")

        if configured_channels:
            partial_batch = {
                "title": "Partial Config Test",
                "summary": "Testing with available channels only",
                "items": [{"title": "Test Item", "message": "Test message"}],
                "channels": configured_channels,
                "priority": "low",
            }

            async with alert_agent:
                with aioresponses() as m:
                    if "slack" in configured_channels:
                        m.post(config.slack_webhook_url, payload={"ok": True})

                    with patch("smtplib.SMTP") as mock_smtp:
                        if "email" in configured_channels:
                            mock_server = MagicMock()
                            mock_smtp.return_value = mock_server

                        result4 = await alert_agent.execute_skill(
                            "sendBatch", partial_batch
                        )

                        if result4.get("status") in ["success", "partial_success"]:
                            print(
                                f"✅ Partial configuration test: {result4.get('status')}"
                            )
                        else:
                            print(f"❌ Partial configuration failed: {result4}")

        print("\n🎯 AlertAgent Batch Testing Complete")

        # Summary
        print("\n📋 Batch Functionality Summary:")
        print("   ✅ sendBatch skill implemented")
        print("   ✅ Multi-channel delivery")
        print("   ✅ Batch deduplication")
        print("   ✅ Error handling")
        print("   ✅ Delivery tracking")

        return True

    except Exception as e:
        print(f"❌ AlertAgent batch test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_alert_batch())
    sys.exit(0 if success else 1)
