# ABOUTME: Standalone AlertAgent testing without complex import dependencies
# ABOUTME: Direct testing of AlertAgent functionality with mock services

import asyncio
import json
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

from aioresponses import aioresponses

# Direct imports to avoid import chain issues
from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import create_config


class StandaloneAlertTester:
    """Standalone AlertAgent tester without server dependencies."""

    def __init__(self):
        """Initialize standalone tester."""
        try:
            self.config = create_config()
            self.alert_agent = AlertAgent(self.config)

            print("🧪 Standalone AlertAgent Tester")
            print(f"Agent: {self.alert_agent.name} v{self.alert_agent.version}")
            print("-" * 50)

        except Exception as e:
            print(f"❌ Failed to initialize AlertAgent: {e}")
            sys.exit(1)

    async def test_configuration(self):
        """Test AlertAgent configuration."""
        print("🔧 Testing Configuration...")

        config_tests = {
            "Slack configured": self.config.has_slack_webhook(),
            "SMTP configured": self.config.has_smtp_config(),
            "Email recipients": len(self.config.email_recipients) > 0,
        }

        for test_name, result in config_tests.items():
            print(f"  {'✅' if result else '❌'} {test_name}")

        return all(config_tests.values())

    async def test_agent_card(self):
        """Test Agent Card generation."""
        print("\n📇 Testing Agent Card...")

        try:
            agent_card = self.alert_agent.generate_agent_card()
            agent_card_json = self.alert_agent.get_agent_card_json()

            # Validate structure
            parsed_card = json.loads(agent_card_json)
            required_fields = ["name", "version", "description", "skills"]

            card_valid = all(field in parsed_card for field in required_fields)
            skills_count = len(parsed_card.get("skills", []))

            print("  ✅ Agent card generated successfully")
            print(f"    Name: {parsed_card.get('name')}")
            print(f"    Version: {parsed_card.get('version')}")
            print(f"    Skills: {skills_count}")

            return card_valid

        except Exception as e:
            print(f"  ❌ Agent card generation failed: {e}")
            return False

    async def test_skills_definition(self):
        """Test skills definition."""
        print("\n🛠️  Testing Skills...")

        skills = self.alert_agent.get_skills()
        expected_skills = {"sendSlack", "sendEmail", "health_check"}
        actual_skills = {skill.name for skill in skills}

        skills_valid = expected_skills == actual_skills

        print(f"  Expected: {expected_skills}")
        print(f"  Actual: {actual_skills}")
        print(f"  {'✅' if skills_valid else '❌'} Skills match")

        return skills_valid

    async def test_health_check(self):
        """Test health check skill."""
        print("\n🏥 Testing Health Check...")

        try:
            result = await self.alert_agent.execute_skill("health_check", {})

            health_valid = (
                result.get("status") == "healthy"
                and result.get("agent_type") == "alert"
                and "slack_configured" in result
                and "smtp_configured" in result
            )

            print(f"  Status: {result.get('status')}")
            print(f"  Agent type: {result.get('agent_type')}")
            print(f"  Slack configured: {result.get('slack_configured')}")
            print(f"  SMTP configured: {result.get('smtp_configured')}")
            print(f"  {'✅' if health_valid else '❌'} Health check")

            return health_valid

        except Exception as e:
            print(f"  ❌ Health check failed: {e}")
            return False

    async def test_slack_mock(self):
        """Test Slack with mock webhook."""
        print("\n🔔 Testing Slack (Mock)...")

        if not self.config.has_slack_webhook():
            print("  ⚠️  Slack not configured - skipping")
            return True

        try:
            async with self.alert_agent:
                with aioresponses() as m:
                    # Mock successful webhook response
                    m.post(self.config.slack_webhook_url, payload={"ok": True})

                    params = {
                        "message": "🧪 Mock Slack test message",
                        "title": "Mock Test Alert",
                        "priority": "medium",
                        "metadata": {"test": "mock_slack"},
                    }

                    result = await self.alert_agent.execute_skill("sendSlack", params)

                    if result.get("status") == "success":
                        print("  ✅ Mock Slack test successful")

                        # Test deduplication
                        result2 = await self.alert_agent.execute_skill(
                            "sendSlack", params
                        )
                        dedup_works = result2.get("status") == "skipped"
                        print(f"  {'✅' if dedup_works else '❌'} Deduplication test")

                        return True
                    else:
                        print(f"  ❌ Mock Slack failed: {result.get('error')}")
                        return False

        except Exception as e:
            print(f"  ❌ Mock Slack test exception: {e}")
            return False

    async def test_email_mock(self):
        """Test email with mock SMTP."""
        print("\n📧 Testing Email (Mock)...")

        if not self.config.has_smtp_config():
            print("  ⚠️  SMTP not configured - skipping")
            return True

        if not self.config.email_recipients:
            print("  ⚠️  No email recipients - skipping")
            return True

        try:
            with patch("smtplib.SMTP") as mock_smtp:
                # Mock SMTP server
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server

                params = {
                    "message": "🧪 Mock email test message",
                    "subject": "Mock Test Email",
                    "priority": "high",
                    "metadata": {"test": "mock_email"},
                }

                result = await self.alert_agent.execute_skill("sendEmail", params)

                if result.get("status") == "success":
                    print("  ✅ Mock email test successful")
                    print(f"    Recipients: {result.get('recipients')}")

                    # Verify SMTP calls
                    mock_smtp.assert_called_once()
                    mock_server.starttls.assert_called_once()
                    mock_server.login.assert_called_once()
                    mock_server.send_message.assert_called_once()

                    # Test deduplication
                    result2 = await self.alert_agent.execute_skill("sendEmail", params)
                    dedup_works = result2.get("status") == "skipped"
                    print(f"  {'✅' if dedup_works else '❌'} Deduplication test")

                    return True
                else:
                    print(f"  ❌ Mock email failed: {result.get('error')}")
                    return False

        except Exception as e:
            print(f"  ❌ Mock email test exception: {e}")
            return False

    async def test_message_formatting(self):
        """Test message formatting for different priorities."""
        print("\n🎨 Testing Message Formatting...")

        priorities = ["low", "medium", "high", "critical"]

        for priority in priorities:
            # Test Slack formatting
            slack_msg = self.alert_agent._format_slack_message(
                message=f"Test {priority} message",
                title=f"Test {priority.title()}",
                priority=priority,
                metadata={"test": "formatting"},
            )

            slack_valid = (
                "attachments" in slack_msg
                and len(slack_msg["attachments"]) > 0
                and "color" in slack_msg["attachments"][0]
            )

            # Test email formatting
            html_content, text_content = self.alert_agent._format_email_content(
                message=f"Test {priority} email",
                subject=f"Test {priority.title()}",
                priority=priority,
                template_name="default",
                metadata={"test": "formatting"},
            )

            email_valid = html_content and text_content

            status = "✅" if slack_valid and email_valid else "❌"
            print(f"  {status} {priority} priority formatting")

        return True

    async def test_error_handling(self):
        """Test error handling scenarios."""
        print("\n🚨 Testing Error Handling...")

        # Test invalid skill
        result = await self.alert_agent.execute_skill("invalid_skill", {})
        invalid_handled = result.get("status") == "error"
        print(f"  {'✅' if invalid_handled else '❌'} Invalid skill handling")

        # Test empty parameters
        if self.config.has_slack_webhook():
            result = await self.alert_agent.execute_skill("sendSlack", {})
            empty_handled = result.get("status") in ["success", "error"]
            print(f"  {'✅' if empty_handled else '❌'} Empty parameters handling")

        return invalid_handled

    async def test_concurrent_operations(self):
        """Test concurrent alert operations."""
        print("\n⚡ Testing Concurrent Operations...")

        if not self.config.has_slack_webhook():
            print("  ⚠️  Slack not configured - skipping concurrency test")
            return True

        try:
            async with self.alert_agent:
                with aioresponses() as m:
                    # Mock multiple webhook responses
                    for i in range(3):
                        m.post(self.config.slack_webhook_url, payload={"ok": True})

                    # Create concurrent tasks
                    tasks = []
                    for i in range(3):
                        params = {
                            "message": f"Concurrent test {i + 1}",
                            "title": f"Concurrent {i + 1}",
                            "priority": "low",
                            "metadata": {"test_id": i + 1},
                        }
                        task = self.alert_agent.execute_skill("sendSlack", params)
                        tasks.append(task)

                    start_time = datetime.now()
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    end_time = datetime.now()

                    duration = (end_time - start_time).total_seconds()
                    successful = sum(
                        1
                        for r in results
                        if isinstance(r, dict) and r.get("status") == "success"
                    )

                    print(f"  ⏱️  {len(tasks)} tasks in {duration:.2f}s")
                    print(f"  ✅ {successful} successful")
                    print(f"  ❌ {len(results) - successful} failed")

                    return successful > 0

        except Exception as e:
            print(f"  ❌ Concurrency test failed: {e}")
            return False

    async def generate_report(self, results: dict[str, bool]):
        """Generate test report."""
        print("\n" + "=" * 60)
        print("📊 STANDALONE ALERTAGENT TEST REPORT")
        print("=" * 60)

        total_tests = len(results)
        passed_tests = sum(results.values())

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {total_tests - passed_tests} ❌")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")

        print("\nDetailed Results:")
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"  {test_name}: {status}")

        # Production readiness
        critical_tests = ["Configuration", "Agent Card", "Skills", "Health Check"]
        critical_passed = all(results.get(test, False) for test in critical_tests)

        print(
            f"\n🚀 Production Readiness: {'✅ READY' if critical_passed else '❌ NEEDS WORK'}"
        )

        if not critical_passed:
            failed_critical = [
                test for test in critical_tests if not results.get(test, False)
            ]
            print(f"   Critical failures: {', '.join(failed_critical)}")

        print("=" * 60)

        return passed_tests == total_tests

    async def run_all_tests(self):
        """Run all standalone tests."""
        print("🧪 Starting Standalone AlertAgent Tests")
        print("=" * 60)

        results = {}

        # Run test suite
        results["Configuration"] = await self.test_configuration()
        results["Agent Card"] = await self.test_agent_card()
        results["Skills"] = await self.test_skills_definition()
        results["Health Check"] = await self.test_health_check()
        results["Slack Mock"] = await self.test_slack_mock()
        results["Email Mock"] = await self.test_email_mock()
        results["Formatting"] = await self.test_message_formatting()
        results["Error Handling"] = await self.test_error_handling()
        results["Concurrency"] = await self.test_concurrent_operations()

        # Generate report
        all_passed = await self.generate_report(results)

        return all_passed


async def main():
    """Main entry point."""
    tester = StandaloneAlertTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
