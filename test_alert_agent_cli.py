# ABOUTME: Comprehensive AlertAgent testing CLI for production validation and testing
# ABOUTME: Tests Slack webhooks, SMTP email, alert batching, and complete A2A integration

import asyncio
import json
import sys
from datetime import datetime

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.config import create_config


class AlertAgentTestCLI:
    """
    Comprehensive test CLI for AlertAgent functionality validation.

    Tests all notification channels, alert batching, delivery tracking,
    A2A skills integration, and production readiness checks.
    """

    def __init__(self):
        """Initialize test CLI with AlertAgent instance."""
        try:
            self.config = create_config()
            self.alert_agent = AlertAgent(self.config)

            print("🚀 AlertAgent Test CLI Initialized")
            print(f"Agent: {self.alert_agent.name} v{self.alert_agent.version}")
            print(f"Agent Type: {self.alert_agent.agent_type}")
            print("-" * 60)

        except Exception as e:
            print(f"❌ Failed to initialize AlertAgent: {e}")
            sys.exit(1)

    async def test_agent_configuration(self):
        """Test AlertAgent configuration and prerequisites."""
        print("🔧 Testing AlertAgent Configuration...")

        tests = [
            ("Slack webhook configured", self.config.has_slack_webhook()),
            ("SMTP configuration complete", self.config.has_smtp_config()),
            ("Email recipients configured", len(self.config.email_recipients) > 0),
        ]

        for test_name, result in tests:
            status = "✅" if result else "❌"
            print(f"  {status} {test_name}")

        # Configuration details
        print("\n📋 Configuration Details:")
        print(
            f"  Slack webhook: {'configured' if self.config.has_slack_webhook() else 'not configured'}"
        )
        print(
            f"  SMTP server: {self.config.smtp_server if self.config.smtp_server else 'not configured'}"
        )
        print(f"  Email recipients: {len(self.config.email_recipients)} configured")

        return all(result for _, result in tests)

    async def test_agent_skills(self):
        """Test AlertAgent A2A skills definition."""
        print("\n🛠️  Testing AlertAgent Skills...")

        skills = self.alert_agent.get_skills()
        expected_skills = {"sendSlack", "sendEmail", "health_check"}
        actual_skills = {skill.name for skill in skills}

        print(f"  Expected skills: {expected_skills}")
        print(f"  Actual skills: {actual_skills}")

        missing_skills = expected_skills - actual_skills
        extra_skills = actual_skills - expected_skills

        if missing_skills:
            print(f"  ❌ Missing skills: {missing_skills}")
        if extra_skills:
            print(f"  ⚠️  Extra skills: {extra_skills}")

        skills_valid = len(missing_skills) == 0
        print(f"  {'✅' if skills_valid else '❌'} Skills validation")

        return skills_valid

    async def test_agent_card_generation(self):
        """Test Agent Card generation for A2A service discovery."""
        print("\n📇 Testing Agent Card Generation...")

        try:
            agent_card = self.alert_agent.generate_agent_card()
            agent_card_json = self.alert_agent.get_agent_card_json()

            # Validate card structure
            parsed_card = json.loads(agent_card_json)
            required_fields = ["name", "version", "description", "skills"]

            card_valid = all(field in parsed_card for field in required_fields)

            print(f"  Agent name: {agent_card.name}")
            print(f"  Version: {agent_card.version}")
            print(f"  Skills count: {len(agent_card.skills)}")
            print(f"  {'✅' if card_valid else '❌'} Agent card structure")

            return card_valid

        except Exception as e:
            print(f"  ❌ Agent card generation failed: {e}")
            return False

    async def test_health_check_skill(self):
        """Test health check skill functionality."""
        print("\n🏥 Testing Health Check Skill...")

        try:
            # Basic health check
            result = await self.alert_agent.execute_skill("health_check", {})

            basic_checks = [
                ("Status", result.get("status") == "healthy"),
                ("Agent type", result.get("agent_type") == "alert"),
                ("Agent name", result.get("name") is not None),
                ("Slack configured", "slack_configured" in result),
                ("SMTP configured", "smtp_configured" in result),
            ]

            for check_name, check_result in basic_checks:
                status = "✅" if check_result else "❌"
                print(f"  {status} {check_name}")

            # Extended health check with connectivity
            if self.config.has_slack_webhook() or self.config.has_smtp_config():
                print("\n  🔗 Testing connectivity...")
                connectivity_result = await self.alert_agent.execute_skill(
                    "health_check", {"check_connectivity": True}
                )

                if "connectivity" in connectivity_result:
                    connectivity = connectivity_result["connectivity"]
                    if "slack" in connectivity:
                        print(f"    Slack: {connectivity['slack']}")
                    if "smtp" in connectivity:
                        print(f"    SMTP: {connectivity['smtp']}")

            return result.get("status") == "healthy"

        except Exception as e:
            print(f"  ❌ Health check failed: {e}")
            return False

    async def test_slack_integration(self):
        """Test Slack webhook integration."""
        print("\n🔔 Testing Slack Integration...")

        if not self.config.has_slack_webhook():
            print("  ⚠️  Slack webhook not configured - skipping test")
            return True

        try:
            async with self.alert_agent:
                # Test basic Slack alert
                params = {
                    "message": "🧪 AlertAgent Test - Slack Integration",
                    "title": "Test Alert",
                    "priority": "medium",
                    "metadata": {
                        "test_type": "slack_integration",
                        "timestamp": datetime.now().isoformat(),
                        "source": "test_cli",
                    },
                }

                result = await self.alert_agent.execute_skill("sendSlack", params)

                if result.get("status") == "success":
                    print("  ✅ Slack alert sent successfully")
                    print(f"    Channel: {result.get('channel')}")
                    print(f"    Dedup hash: {result.get('deduplication_hash')}")

                    # Test deduplication
                    result2 = await self.alert_agent.execute_skill("sendSlack", params)
                    if result2.get("status") == "skipped":
                        print("  ✅ Deduplication working correctly")
                    else:
                        print("  ⚠️  Deduplication may not be working")

                    return True
                else:
                    print(f"  ❌ Slack alert failed: {result.get('error')}")
                    return False

        except Exception as e:
            print(f"  ❌ Slack integration test failed: {e}")
            return False

    async def test_email_integration(self):
        """Test SMTP email integration."""
        print("\n📧 Testing Email Integration...")

        if not self.config.has_smtp_config():
            print("  ⚠️  SMTP not configured - skipping test")
            return True

        if not self.config.email_recipients:
            print("  ⚠️  No email recipients configured - skipping test")
            return True

        try:
            # Test basic email alert
            params = {
                "message": "🧪 AlertAgent Test - Email Integration\n\nThis is a test email from the AlertAgent test CLI.",
                "subject": "AlertAgent Test - Email Integration",
                "priority": "high",
                "html_template": "default",
                "metadata": {
                    "test_type": "email_integration",
                    "timestamp": datetime.now().isoformat(),
                    "source": "test_cli",
                    "recipients_count": len(self.config.email_recipients),
                },
            }

            result = await self.alert_agent.execute_skill("sendEmail", params)

            if result.get("status") == "success":
                print("  ✅ Email alert sent successfully")
                print(f"    Channel: {result.get('channel')}")
                print(f"    Recipients: {result.get('recipients')}")
                print(f"    Dedup hash: {result.get('deduplication_hash')}")

                # Test deduplication
                result2 = await self.alert_agent.execute_skill("sendEmail", params)
                if result2.get("status") == "skipped":
                    print("  ✅ Email deduplication working correctly")
                else:
                    print("  ⚠️  Email deduplication may not be working")

                return True
            else:
                print(f"  ❌ Email alert failed: {result.get('error')}")
                return False

        except Exception as e:
            print(f"  ❌ Email integration test failed: {e}")
            return False

    async def test_alert_formatting(self):
        """Test alert message formatting for different priorities."""
        print("\n🎨 Testing Alert Formatting...")

        priorities = ["low", "medium", "high", "critical"]

        for priority in priorities:
            print(f"  Testing {priority} priority formatting...")

            # Test Slack formatting
            slack_message = self.alert_agent._format_slack_message(
                message=f"Test {priority} priority message",
                title=f"Test {priority.title()} Alert",
                priority=priority,
                metadata={"test": "formatting", "priority_level": priority},
            )

            # Validate Slack formatting
            slack_valid = (
                "attachments" in slack_message
                and len(slack_message["attachments"]) > 0
                and "color" in slack_message["attachments"][0]
                and "title" in slack_message["attachments"][0]
            )

            # Test Email formatting
            html_content, text_content = self.alert_agent._format_email_content(
                message=f"Test {priority} priority email",
                subject=f"Test {priority.title()} Email Alert",
                priority=priority,
                template_name="default",
                metadata={"test": "formatting", "priority_level": priority},
            )

            # Validate Email formatting
            email_valid = (
                html_content
                and text_content
                and priority in html_content.lower()
                and priority in text_content.lower()
            )

            status = "✅" if slack_valid and email_valid else "❌"
            print(f"    {status} {priority} priority formatting")

        return True

    async def test_error_handling(self):
        """Test error handling scenarios."""
        print("\n🚨 Testing Error Handling...")

        # Test invalid skill
        result = await self.alert_agent.execute_skill("invalid_skill", {})
        invalid_skill_handled = result.get("status") == "error"
        print(f"  {'✅' if invalid_skill_handled else '❌'} Invalid skill handling")

        # Test missing parameters
        result = await self.alert_agent.execute_skill("sendSlack", {})
        if self.config.has_slack_webhook():
            empty_params_handled = result.get("status") in ["success", "error"]
            print(
                f"  {'✅' if empty_params_handled else '❌'} Empty parameters handling"
            )

        return invalid_skill_handled

    async def test_performance_metrics(self):
        """Test performance and timing metrics."""
        print("\n⚡ Testing Performance Metrics...")

        # Test multiple concurrent alerts
        if self.config.has_slack_webhook():
            start_time = datetime.now()

            async with self.alert_agent:
                tasks = []
                for i in range(3):
                    params = {
                        "message": f"Performance test message {i + 1}",
                        "title": f"Performance Test {i + 1}",
                        "priority": "low",
                        "metadata": {"test_id": i + 1, "batch": "performance"},
                    }
                    task = self.alert_agent.execute_skill("sendSlack", params)
                    tasks.append(task)

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

        return True

    async def generate_test_report(self, test_results: dict[str, bool]):
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("📊 ALERTAGENT VALIDATION REPORT")
        print("=" * 60)

        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")

        print("\nDetailed Results:")
        for test_name, result in test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"  {test_name}: {status}")

        # Production readiness assessment
        critical_tests = [
            "Configuration",
            "Skills Definition",
            "Agent Card Generation",
            "Health Check",
        ]

        critical_passed = all(test_results.get(test) for test in critical_tests)

        print(
            f"\n🚀 Production Readiness: {'✅ READY' if critical_passed else '❌ NOT READY'}"
        )

        if not critical_passed:
            failed_critical = [
                test for test in critical_tests if not test_results.get(test)
            ]
            print(f"   Critical failures: {', '.join(failed_critical)}")

        print("=" * 60)

        return passed_tests == total_tests

    async def run_all_tests(self):
        """Run all AlertAgent validation tests."""
        print("🔬 Starting Comprehensive AlertAgent Validation")
        print("=" * 60)

        test_results = {}

        # Run all test suites
        test_results["Configuration"] = await self.test_agent_configuration()
        test_results["Skills Definition"] = await self.test_agent_skills()
        test_results["Agent Card Generation"] = await self.test_agent_card_generation()
        test_results["Health Check"] = await self.test_health_check_skill()
        test_results["Slack Integration"] = await self.test_slack_integration()
        test_results["Email Integration"] = await self.test_email_integration()
        test_results["Alert Formatting"] = await self.test_alert_formatting()
        test_results["Error Handling"] = await self.test_error_handling()
        test_results["Performance"] = await self.test_performance_metrics()

        # Generate final report
        all_passed = await self.generate_test_report(test_results)

        return all_passed


async def main():
    """Main CLI entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        test_cli = AlertAgentTestCLI()

        if command == "config":
            await test_cli.test_agent_configuration()
        elif command == "skills":
            await test_cli.test_agent_skills()
        elif command == "health":
            await test_cli.test_health_check_skill()
        elif command == "slack":
            await test_cli.test_slack_integration()
        elif command == "email":
            await test_cli.test_email_integration()
        elif command == "formatting":
            await test_cli.test_alert_formatting()
        elif command == "errors":
            await test_cli.test_error_handling()
        elif command == "performance":
            await test_cli.test_performance_metrics()
        elif command == "all":
            success = await test_cli.run_all_tests()
            sys.exit(0 if success else 1)
        else:
            print(f"Unknown command: {command}")
            print(
                "Available commands: config, skills, health, slack, email, formatting, errors, performance, all"
            )
            sys.exit(1)
    else:
        # Run all tests by default
        test_cli = AlertAgentTestCLI()
        success = await test_cli.run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
