#!/usr/bin/env python3
# ABOUTME: Real integration test for the complete Reddit monitoring workflow
# ABOUTME: Tests actual agent coordination and A2A communication without mocks

import asyncio
import logging
import sys
from datetime import UTC, datetime

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent


def setup_logging():
    """Setup logging for the integration test."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def test_coordinator_health():
    """Test coordinator agent health check."""
    print("🏥 Testing CoordinatorAgent Health Check...")

    coordinator = CoordinatorAgent()

    try:
        result = await coordinator.execute_skill("health_check", {})

        print(f"✅ Health Check Status: {result['status']}")

        if result["status"] == "success":
            agent_status = result["result"]["coordinator_specific"]["agent_status"]

            print("\n📊 Agent Status Summary:")
            for agent_name, status in agent_status.items():
                status_emoji = "✅" if status["status"] == "healthy" else "❌"
                print(f"  {status_emoji} {agent_name}: {status['status']}")
                if status["status"] != "healthy":
                    print(f"    Error: {status.get('error', 'Unknown')}")

        return result

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return None

    finally:
        if hasattr(coordinator, "_cleanup_http_session"):
            await coordinator._cleanup_http_session()


async def test_workflow_status():
    """Test getting workflow status."""
    print("\n📈 Testing Workflow Status...")

    coordinator = CoordinatorAgent()

    try:
        result = await coordinator.execute_skill("get_workflow_status", {"limit": 5})

        print(f"✅ Workflow Status: {result['status']}")

        if result["status"] == "success":
            workflows = result["result"]["workflows"]
            print(f"📝 Found {len(workflows)} recent workflows")

            for workflow in workflows[:3]:  # Show first 3
                print(
                    f"  • ID: {workflow['id']} | Status: {workflow['status']} | Started: {workflow['started_at']}"
                )

        return result

    except Exception as e:
        print(f"❌ Workflow status check failed: {e}")
        return None

    finally:
        if hasattr(coordinator, "_cleanup_http_session"):
            await coordinator._cleanup_http_session()


async def test_agent_status_check():
    """Test checking all agent statuses."""
    print("\n🔍 Testing Agent Status Check...")

    coordinator = CoordinatorAgent()

    try:
        result = await coordinator.execute_skill("check_agent_status", {})

        print(f"✅ Agent Status Check: {result['status']}")

        if result["status"] == "success":
            total_agents = result["result"]["total_agents"]
            healthy_agents = result["result"]["healthy_agents"]
            health_percentage = result["result"]["health_percentage"]

            print(
                f"📊 Health Summary: {healthy_agents}/{total_agents} agents healthy ({health_percentage:.1f}%)"
            )

            # Show detailed status
            for agent_name, details in result["result"]["agent_details"].items():
                status_emoji = "✅" if details["status"] == "healthy" else "❌"
                print(f"  {status_emoji} {agent_name}: {details['status']}")

        return result

    except Exception as e:
        print(f"❌ Agent status check failed: {e}")
        return None

    finally:
        if hasattr(coordinator, "_cleanup_http_session"):
            await coordinator._cleanup_http_session()


async def test_monitoring_cycle_dry_run():
    """Test a monitoring cycle with minimal parameters (dry run)."""
    print("\n🚀 Testing Monitoring Cycle (Dry Run)...")
    print("⚠️  Note: This will try to communicate with other agents")
    print("   Make sure they're running or expect connection errors")

    coordinator = CoordinatorAgent()

    try:
        # Use a minimal test topic to avoid flooding Reddit API
        test_params = {
            "topics": ["test"],  # Simple test topic
            "subreddits": ["test"],  # Test subreddit
        }

        print(f"📋 Test Parameters: {test_params}")

        result = await coordinator.execute_skill("run_monitoring_cycle", test_params)

        print(f"✅ Monitoring Cycle: {result['status']}")

        if result["status"] == "success":
            workflow_result = result["result"]
            print(f"🎯 Workflow ID: {workflow_result['workflow_id']}")
            print(f"📊 Topics: {workflow_result['topics']}")
            print(f"🏠 Subreddits: {workflow_result['subreddits']}")

            # Show step results
            if "retrieval_result" in workflow_result:
                retrieval = workflow_result["retrieval_result"]
                print(f"📥 Retrieval: {retrieval.get('total_posts', 0)} posts")

            if "filter_result" in workflow_result:
                filtering = workflow_result["filter_result"]
                print(f"🔍 Filter: {filtering.get('relevant_posts', 0)} relevant posts")

            if "summarise_result" in workflow_result:
                summarise = workflow_result["summarise_result"]
                print(
                    f"📝 Summarise: {summarise.get('summaries_created', 0)} summaries"
                )

            if "alert_result" in workflow_result:
                alert = workflow_result["alert_result"]
                print(f"📢 Alert: {alert.get('alerts_sent', 0)} alerts sent")

        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            if "workflow_id" in result:
                print(f"🆔 Failed Workflow ID: {result['workflow_id']}")

        return result

    except Exception as e:
        print(f"❌ Monitoring cycle test failed: {e}")
        return None

    finally:
        if hasattr(coordinator, "_cleanup_http_session"):
            await coordinator._cleanup_http_session()


async def main():
    """Run the complete integration test suite."""
    print("🚀 Reddit Watcher - Real Integration Test")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now(UTC).isoformat()}")

    setup_logging()

    # Test 1: Health Check
    health_result = await test_coordinator_health()

    # Test 2: Workflow Status
    await test_workflow_status()

    # Test 3: Agent Status Check
    await test_agent_status_check()

    # Test 4: Monitoring Cycle (only if health check passed)
    if health_result and health_result.get("status") == "success":
        # Check if any agents are actually healthy before attempting workflow
        agent_status = health_result["result"]["coordinator_specific"]["agent_status"]
        healthy_count = sum(
            1 for status in agent_status.values() if status["status"] == "healthy"
        )

        if healthy_count > 0:
            print(
                f"\n✅ {healthy_count} agents healthy - proceeding with workflow test"
            )
            await test_monitoring_cycle_dry_run()
        else:
            print("\n⚠️  No healthy agents detected - skipping workflow test")
            print("   Start your agent servers to test the complete workflow")
    else:
        print("\n⚠️  Health check failed - skipping workflow test")

    print("\n" + "=" * 50)
    print("🏁 Integration test completed!")
    print("\n💡 To test with running agents:")
    print("   1. Start your agent servers on ports 8001-8004")
    print("   2. Configure your Reddit API credentials")
    print("   3. Run this test again")


if __name__ == "__main__":
    asyncio.run(main())
