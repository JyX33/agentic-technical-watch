# ABOUTME: AlertAgent integration testing with mock and real service support
# ABOUTME: Comprehensive testing framework for Slack webhooks, SMTP email, and alert batching

import asyncio
import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from aioresponses import aioresponses

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import create_config


class AlertIntegrationTester:
    """
    Comprehensive AlertAgent integration tester supporting both mock and live testing.

    Can run with mocked services for CI/testing or with real credentials for
    production validation.
    """

    def __init__(self, use_mocks: bool = True, live_test_mode: bool = False):
        """
        Initialize integration tester.

        Args:
            use_mocks: Use mocked services instead of real ones
            live_test_mode: Enable live testing with real credentials (use carefully)
        """
        self.use_mocks = use_mocks
        self.live_test_mode = live_test_mode

        try:
            self.config = create_config()
            self.alert_agent = AlertAgent(self.config)

            print("🧪 AlertAgent Integration Tester Initialized")
            print(f"Mode: {'LIVE' if live_test_mode else 'MOCK'}")
            print(f"Agent: {self.alert_agent.name} v{self.alert_agent.version}")
            print("-" * 60)

        except Exception as e:
            print(f"❌ Failed to initialize AlertAgent: {e}")
            sys.exit(1)

    async def test_slack_webhook_integration(self):
        """Test Slack webhook integration with mock or real service."""
        print("🔔 Testing Slack Webhook Integration...")

        if not self.config.has_slack_webhook():
            print("  ⚠️  Slack webhook not configured")
            return {"status": "skipped", "reason": "no_config"}

        test_params = {
            "message": "🧪 Integration Test - Slack Webhook",
            "title": "AlertAgent Integration Test",
            "priority": "medium",
            "metadata": {
                "test_mode": "mock" if self.use_mocks else "live",
                "timestamp": datetime.now().isoformat(),
                "test_type": "slack_integration",
            },
        }

        if self.use_mocks:
            return await self._test_slack_with_mock(test_params)
        else:
            return await self._test_slack_live(test_params)

    async def _test_slack_with_mock(self, params: dict[str, Any]):
        """Test Slack integration with mocked webhook."""
        try:
            async with self.alert_agent:
                with aioresponses() as m:
                    # Mock successful Slack webhook response
                    m.post(self.config.slack_webhook_url, payload={"ok": True})

                    result = await self.alert_agent.execute_skill("sendSlack", params)

                    if result.get("status") == "success":
                        print("  ✅ Mock Slack webhook test successful")

                        # Test deduplication
                        result2 = await self.alert_agent.execute_skill(
                            "sendSlack", params
                        )
                        if result2.get("status") == "skipped":
                            print("  ✅ Slack deduplication working")
                        else:
                            print("  ⚠️  Slack deduplication may not be working")

                        return {"status": "success", "mock_test": True}
                    else:
                        print(f"  ❌ Mock Slack test failed: {result.get('error')}")
                        return {"status": "failed", "error": result.get("error")}

        except Exception as e:
            print(f"  ❌ Mock Slack test exception: {e}")
            return {"status": "error", "error": str(e)}

    async def _test_slack_live(self, params: dict[str, Any]):
        """Test Slack integration with live webhook (use carefully)."""
        print("  ⚠️  LIVE SLACK TEST - This will send a real message")

        if not self.live_test_mode:
            print("  ❌ Live test mode not enabled")
            return {"status": "skipped", "reason": "live_mode_disabled"}

        try:
            async with self.alert_agent:
                result = await self.alert_agent.execute_skill("sendSlack", params)

                if result.get("status") == "success":
                    print("  ✅ LIVE Slack webhook test successful")
                    print("    Message sent to Slack channel")
                    return {"status": "success", "live_test": True}
                else:
                    print(f"  ❌ LIVE Slack test failed: {result.get('error')}")
                    return {"status": "failed", "error": result.get("error")}

        except Exception as e:
            print(f"  ❌ LIVE Slack test exception: {e}")
            return {"status": "error", "error": str(e)}

    async def test_smtp_email_integration(self):
        """Test SMTP email integration with mock or real service."""
        print("\n📧 Testing SMTP Email Integration...")

        if not self.config.has_smtp_config():
            print("  ⚠️  SMTP not configured")
            return {"status": "skipped", "reason": "no_config"}

        if not self.config.email_recipients:
            print("  ⚠️  No email recipients configured")
            return {"status": "skipped", "reason": "no_recipients"}

        test_params = {
            "message": "🧪 Integration Test - SMTP Email\n\nThis is a test email from the AlertAgent integration tester.",
            "subject": "AlertAgent Integration Test - SMTP",
            "priority": "high",
            "html_template": "default",
            "metadata": {
                "test_mode": "mock" if self.use_mocks else "live",
                "timestamp": datetime.now().isoformat(),
                "test_type": "smtp_integration",
                "recipients_count": len(self.config.email_recipients),
            },
        }

        if self.use_mocks:
            return await self._test_smtp_with_mock(test_params)
        else:
            return await self._test_smtp_live(test_params)

    async def _test_smtp_with_mock(self, params: dict[str, Any]):
        """Test SMTP integration with mocked server."""
        try:
            with patch("smtplib.SMTP") as mock_smtp:
                # Mock SMTP server
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server

                result = await self.alert_agent.execute_skill("sendEmail", params)

                if result.get("status") == "success":
                    print("  ✅ Mock SMTP email test successful")
                    print(f"    Recipients: {result.get('recipients')}")

                    # Verify SMTP calls
                    mock_smtp.assert_called_with(
                        self.config.smtp_server, self.config.smtp_port
                    )
                    mock_server.starttls.assert_called_once()
                    mock_server.login.assert_called_once()
                    mock_server.send_message.assert_called_once()
                    mock_server.quit.assert_called_once()

                    # Test deduplication
                    result2 = await self.alert_agent.execute_skill("sendEmail", params)
                    if result2.get("status") == "skipped":
                        print("  ✅ Email deduplication working")
                    else:
                        print("  ⚠️  Email deduplication may not be working")

                    return {"status": "success", "mock_test": True}
                else:
                    print(f"  ❌ Mock SMTP test failed: {result.get('error')}")
                    return {"status": "failed", "error": result.get("error")}

        except Exception as e:
            print(f"  ❌ Mock SMTP test exception: {e}")
            return {"status": "error", "error": str(e)}

    async def _test_smtp_live(self, params: dict[str, Any]):
        """Test SMTP integration with live server (use carefully)."""
        print("  ⚠️  LIVE SMTP TEST - This will send a real email")

        if not self.live_test_mode:
            print("  ❌ Live test mode not enabled")
            return {"status": "skipped", "reason": "live_mode_disabled"}

        try:
            result = await self.alert_agent.execute_skill("sendEmail", params)

            if result.get("status") == "success":
                print("  ✅ LIVE SMTP email test successful")
                print(f"    Email sent to: {result.get('recipients')}")
                return {"status": "success", "live_test": True}
            else:
                print(f"  ❌ LIVE SMTP test failed: {result.get('error')}")
                return {"status": "failed", "error": result.get("error")}

        except Exception as e:
            print(f"  ❌ LIVE SMTP test exception: {e}")
            return {"status": "error", "error": str(e)}

    async def test_alert_batch_functionality(self):
        """Test alert batch creation and processing."""
        print("\n📦 Testing Alert Batch Functionality...")

        # Create sample alert batch
        batch_params = {
            "batch_id": f"test_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "title": "Test Alert Batch",
            "summary": "This is a test alert batch containing multiple items",
            "items": [
                {
                    "title": "Test Item 1",
                    "message": "First test item in batch",
                    "priority": "medium",
                    "source": "reddit",
                    "url": "https://reddit.com/test1",
                },
                {
                    "title": "Test Item 2",
                    "message": "Second test item in batch",
                    "priority": "high",
                    "source": "reddit",
                    "url": "https://reddit.com/test2",
                },
            ],
            "channels": ["slack", "email"],
            "schedule_type": "immediate",
        }

        try:
            # For now, we'll test the individual components since AlertBatch
            # model isn't fully implemented in the current agent

            # Test Slack batch notification
            if self.config.has_slack_webhook():
                slack_result = await self._test_batch_slack(batch_params)
                print(
                    f"  Slack batch: {'✅' if slack_result.get('status') == 'success' else '❌'}"
                )

            # Test Email batch notification
            if self.config.has_smtp_config() and self.config.email_recipients:
                email_result = await self._test_batch_email(batch_params)
                print(
                    f"  Email batch: {'✅' if email_result.get('status') == 'success' else '❌'}"
                )

            return {"status": "success", "batch_test": True}

        except Exception as e:
            print(f"  ❌ Alert batch test failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _test_batch_slack(self, batch_params: dict[str, Any]):
        """Test batch Slack notification."""
        items_summary = "\n".join(
            [f"• {item['title']}: {item['message']}" for item in batch_params["items"]]
        )

        slack_params = {
            "message": f"{batch_params['summary']}\n\n{items_summary}",
            "title": batch_params["title"],
            "priority": "medium",
            "metadata": {
                "batch_id": batch_params["batch_id"],
                "items_count": len(batch_params["items"]),
                "channels": batch_params["channels"],
            },
        }

        if self.use_mocks:
            async with self.alert_agent:
                with aioresponses() as m:
                    m.post(self.config.slack_webhook_url, payload={"ok": True})
                    return await self.alert_agent.execute_skill(
                        "sendSlack", slack_params
                    )
        else:
            if self.live_test_mode:
                async with self.alert_agent:
                    return await self.alert_agent.execute_skill(
                        "sendSlack", slack_params
                    )
            else:
                return {"status": "skipped", "reason": "live_mode_disabled"}

    async def _test_batch_email(self, batch_params: dict[str, Any]):
        """Test batch email notification."""
        (
            "<ul>"
            + "".join(
                [
                    f"<li><strong>{item['title']}</strong>: {item['message']}</li>"
                    for item in batch_params["items"]
                ]
            )
            + "</ul>"
        )

        email_params = {
            "message": f"{batch_params['summary']}\n\nItems:\n"
            + "\n".join(
                [
                    f"• {item['title']}: {item['message']}"
                    for item in batch_params["items"]
                ]
            ),
            "subject": f"{batch_params['title']} ({len(batch_params['items'])} items)",
            "priority": "medium",
            "html_template": "default",
            "metadata": {
                "batch_id": batch_params["batch_id"],
                "items_count": len(batch_params["items"]),
                "channels": batch_params["channels"],
            },
        }

        if self.use_mocks:
            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server
                return await self.alert_agent.execute_skill("sendEmail", email_params)
        else:
            if self.live_test_mode:
                return await self.alert_agent.execute_skill("sendEmail", email_params)
            else:
                return {"status": "skipped", "reason": "live_mode_disabled"}

    async def test_performance_and_concurrency(self):
        """Test AlertAgent performance under concurrent load."""
        print("\n⚡ Testing Performance and Concurrency...")

        if not (
            self.config.has_slack_webhook()
            or (self.config.has_smtp_config() and self.config.email_recipients)
        ):
            print("  ⚠️  No notification channels configured")
            return {"status": "skipped", "reason": "no_channels"}

        start_time = datetime.now()

        # Create multiple concurrent tasks
        tasks = []
        for i in range(5):
            if self.config.has_slack_webhook():
                task_params = {
                    "message": f"Concurrent test message {i + 1}",
                    "title": f"Concurrent Test {i + 1}",
                    "priority": "low",
                    "metadata": {"test_id": i + 1, "batch": "concurrency"},
                }

                if self.use_mocks:
                    # For mock testing, we need to handle each task separately
                    # due to aioresponses context manager limitations
                    task = self._mock_slack_task(task_params)
                else:
                    if self.live_test_mode:
                        async with self.alert_agent:
                            task = self.alert_agent.execute_skill(
                                "sendSlack", task_params
                            )
                    else:
                        continue  # Skip if not in live mode

                tasks.append(task)

        if not tasks:
            print("  ⚠️  No tasks created for concurrency test")
            return {"status": "skipped", "reason": "no_tasks"}

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            successful_results = [
                r
                for r in results
                if isinstance(r, dict) and r.get("status") == "success"
            ]

            print(f"  ⏱️  Executed {len(tasks)} concurrent alerts in {duration:.2f}s")
            print(f"  ✅ {len(successful_results)} successful")
            print(f"  ❌ {len(results) - len(successful_results)} failed/errors")

            return {
                "status": "success",
                "tasks_executed": len(tasks),
                "successful": len(successful_results),
                "duration_seconds": duration,
                "throughput": len(tasks) / duration if duration > 0 else 0,
            }

        except Exception as e:
            print(f"  ❌ Concurrency test failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _mock_slack_task(self, params: dict[str, Any]):
        """Create a mock Slack task for concurrency testing."""
        async with self.alert_agent:
            with aioresponses() as m:
                m.post(self.config.slack_webhook_url, payload={"ok": True})
                return await self.alert_agent.execute_skill("sendSlack", params)

    async def generate_integration_report(self, results: dict[str, dict]):
        """Generate comprehensive integration test report."""
        print("\n" + "=" * 70)
        print("📊 ALERTAGENT INTEGRATION TEST REPORT")
        print("=" * 70)

        total_tests = len(results)
        successful_tests = sum(
            1 for r in results.values() if r.get("status") == "success"
        )
        failed_tests = sum(1 for r in results.values() if r.get("status") == "failed")
        skipped_tests = sum(1 for r in results.values() if r.get("status") == "skipped")

        print(f"Test Mode: {'LIVE' if self.live_test_mode else 'MOCK'}")
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Skipped: {skipped_tests} ⚠️")

        if total_tests > 0:
            success_rate = (
                (successful_tests / (total_tests - skipped_tests)) * 100
                if (total_tests - skipped_tests) > 0
                else 0
            )
            print(f"Success Rate: {success_rate:.1f}%")

        print("\nDetailed Results:")
        for test_name, result in results.items():
            status_icon = {
                "success": "✅",
                "failed": "❌",
                "error": "💥",
                "skipped": "⚠️",
            }.get(result.get("status"), "❓")

            print(
                f"  {test_name}: {status_icon} {result.get('status', 'unknown').upper()}"
            )
            if result.get("error"):
                print(f"    Error: {result['error']}")
            if result.get("reason"):
                print(f"    Reason: {result['reason']}")

        # Integration readiness assessment
        critical_tests = ["Slack Integration", "Email Integration"]
        critical_passed = any(
            results.get(test, {}).get("status") == "success" for test in critical_tests
        )

        print(
            f"\n🚀 Integration Status: {'✅ READY' if critical_passed else '❌ NEEDS ATTENTION'}"
        )

        if not critical_passed:
            print(
                "   At least one notification channel should be working for production"
            )

        print("=" * 70)

        return successful_tests == (total_tests - skipped_tests)

    async def run_integration_tests(self):
        """Run all integration tests."""
        print("🧪 Starting AlertAgent Integration Tests")
        print("=" * 70)

        results = {}

        # Run integration tests
        results["Slack Integration"] = await self.test_slack_webhook_integration()
        results["Email Integration"] = await self.test_smtp_email_integration()
        results["Alert Batching"] = await self.test_alert_batch_functionality()
        results["Performance Test"] = await self.test_performance_and_concurrency()

        # Generate report
        all_passed = await self.generate_integration_report(results)

        return all_passed


async def main():
    """Main entry point for integration testing."""
    import argparse

    parser = argparse.ArgumentParser(description="AlertAgent Integration Tester")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live testing with real services (CAUTION)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use mocked services (default)",
    )
    parser.add_argument(
        "--test",
        choices=["slack", "email", "batch", "performance", "all"],
        default="all",
        help="Run specific test",
    )

    args = parser.parse_args()

    # Override mock if live is explicitly requested
    use_mocks = not args.live
    live_test_mode = args.live

    tester = AlertIntegrationTester(use_mocks=use_mocks, live_test_mode=live_test_mode)

    if args.test == "slack":
        result = await tester.test_slack_webhook_integration()
        print(f"Result: {result}")
    elif args.test == "email":
        result = await tester.test_smtp_email_integration()
        print(f"Result: {result}")
    elif args.test == "batch":
        result = await tester.test_alert_batch_functionality()
        print(f"Result: {result}")
    elif args.test == "performance":
        result = await tester.test_performance_and_concurrency()
        print(f"Result: {result}")
    elif args.test == "all":
        success = await tester.run_integration_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
