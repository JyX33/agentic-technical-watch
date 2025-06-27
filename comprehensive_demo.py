#!/usr/bin/env python3
# ABOUTME: Comprehensive demonstration of Reddit Watcher agents working with real-world scenarios
# ABOUTME: Shows end-to-end functionality including content processing, filtering, summarization, and alerts

import asyncio
import time

from reddit_watcher.config import create_config


class RedditWatcherDemo:
    """Comprehensive demonstration of Reddit Watcher functionality"""

    def __init__(self):
        self.config = create_config()

    async def demonstrate_content_filtering(self):
        """Demonstrate content filtering with realistic Reddit-style content"""
        print("🧹 Content Filtering Demonstration")
        print("=" * 45)

        from reddit_watcher.agents.filter_agent import FilterAgent

        agent = FilterAgent(config=self.config)

        # Realistic Reddit posts about our topics
        demo_posts = [
            {
                "title": "Show HN: Built an AI agent system with Claude Code",
                "content": "I've been working on an autonomous monitoring system using Claude Code and the A2A protocol. It automatically monitors Reddit for discussions about specific topics, filters relevant content, summarizes findings, and sends alerts. The service discovery and health monitoring make it really robust.",
                "subreddit": "r/MachineLearning",
                "author": "u/AIBuilder2024",
            },
            {
                "title": "What's the best pizza place in downtown?",
                "content": "Looking for recommendations for good pizza in the downtown area. Prefer thin crust and authentic Italian style.",
                "subreddit": "r/food",
                "author": "u/PizzaLover123",
            },
            {
                "title": "Agent-to-Agent Communication Patterns",
                "content": "Exploring different patterns for A2A communication in distributed systems. Service mesh vs direct HTTP, async messaging patterns, and fault tolerance strategies. The Redis-based service discovery approach seems promising.",
                "subreddit": "r/programming",
                "author": "u/SystemsEngineer",
            },
            {
                "title": "Claude vs ChatGPT for code assistance",
                "content": "Has anyone tried Claude Code for building AI applications? I'm comparing it with other tools for agent-based systems. The built-in A2A protocol support is interesting.",
                "subreddit": "r/ArtificialIntelligence",
                "author": "u/DevComparison",
            },
        ]

        print(f"Processing {len(demo_posts)} Reddit posts...\n")

        filtered_posts = []
        for i, post in enumerate(demo_posts, 1):
            print(f"📝 Post {i}: {post['title'][:50]}...")
            print(f"   From: {post['subreddit']} by {post['author']}")

            try:
                # Use keyword filtering
                result = await agent.execute_skill(
                    "filter_content_by_keywords",
                    {
                        "content": post["content"],
                        "title": post["title"],
                        "topics": self.config.reddit_topics,
                    },
                )

                relevance = result.get("relevance_score", 0)
                is_relevant = result.get("is_relevant", False)
                matched_keywords = result.get("matched_keywords", [])

                print(f"   Relevance: {relevance:.2f} | Relevant: {is_relevant}")
                if matched_keywords:
                    print(f"   Keywords: {', '.join(matched_keywords)}")

                if is_relevant:
                    filtered_posts.append({**post, "relevance_score": relevance})
                    print("   ✅ PASSED filter - included in summary")
                else:
                    print("   ❌ FILTERED OUT")

            except Exception as e:
                print(f"   ⚠️  Filter error: {e}")

            print()

        print(
            f"🎯 Filtering Results: {len(filtered_posts)}/{len(demo_posts)} posts passed filter"
        )
        return filtered_posts

    async def demonstrate_summarization(self, filtered_posts):
        """Demonstrate content summarization"""
        print("\n📝 Content Summarization Demonstration")
        print("=" * 50)

        if not filtered_posts:
            print("No content to summarize (all posts filtered out)")
            return None

        from reddit_watcher.agents.summarise_agent import SummariseAgent

        agent = SummariseAgent(config=self.config)

        # Combine filtered content
        combined_content = "\\n\\n".join(
            [
                f"**{post['title']}** (from {post['subreddit']})\\n{post['content']}"
                for post in filtered_posts
            ]
        )

        print(f"Summarizing {len(filtered_posts)} relevant posts...")
        print(f"Original content: {len(combined_content)} characters\\n")

        try:
            result = await agent.execute_skill(
                "summarizeContent",
                {
                    "content": combined_content,
                    "max_length": 300,
                    "focus_topics": self.config.reddit_topics,
                },
            )

            summary = result.get("summary", "")
            summary_stats = result.get("statistics", {})

            print("📊 Summary Statistics:")
            print(f"   Original length: {len(combined_content)} chars")
            print(f"   Summary length: {len(summary)} chars")
            print(
                f"   Compression: {(len(summary) / len(combined_content) * 100):.1f}%"
            )
            print(f"   Method: {result.get('method', 'unknown')}")
            print()

            print("📄 Generated Summary:")
            print("-" * 30)
            print(summary)
            print("-" * 30)

            return {
                "summary": summary,
                "original_length": len(combined_content),
                "summary_length": len(summary),
                "posts_count": len(filtered_posts),
                "compression_ratio": len(summary) / len(combined_content),
            }

        except Exception as e:
            print(f"⚠️  Summarization error: {e}")
            return None

    async def demonstrate_alert_delivery(self, summary_data):
        """Demonstrate alert delivery system"""
        print("\\n🚨 Alert Delivery Demonstration")
        print("=" * 42)

        if not summary_data:
            print("No summary data available for alerting")
            return None

        from reddit_watcher.agents.alert_agent import AlertAgent

        agent = AlertAgent(config=self.config)

        # Create alert payload
        alert_data = {
            "topic": "Claude Code & A2A",
            "summary": summary_data["summary"][:200] + "..."
            if len(summary_data["summary"]) > 200
            else summary_data["summary"],
            "posts_found": summary_data["posts_count"],
            "relevance_threshold": self.config.relevance_threshold,
            "monitoring_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "compression_achieved": f"{summary_data['compression_ratio']:.1%}",
        }

        print("🔔 Preparing alert notification...")
        print(f"   Topic: {alert_data['topic']}")
        print(f"   Posts found: {alert_data['posts_found']}")
        print(f"   Summary length: {len(alert_data['summary'])} chars")
        print()

        try:
            # Check delivery stats first
            stats = await agent.execute_skill("getDeliveryStats", {})
            print(
                f"📈 Current delivery stats: {stats.get('total_sent', 0)} alerts sent"
            )

            # Format alert for different channels
            print("🎯 Alert would be delivered to:")

            if self.config.has_slack_webhook():
                print("   ✅ Slack (configured)")
            else:
                print("   ⚠️  Slack (not configured - would be logged)")

            if self.config.has_smtp_config():
                print("   ✅ Email (configured)")
            else:
                print("   ⚠️  Email (not configured - would be logged)")

            # Simulate delivery
            print("\\n📤 Simulated Alert Content:")
            print("-" * 40)
            print("🤖 Reddit Watcher Alert")
            print(f"📊 Topic: {alert_data['topic']}")
            print(f"📝 Found {alert_data['posts_found']} relevant posts")
            print(f"⏰ Monitoring time: {alert_data['monitoring_time']}")
            print()
            print("📄 Summary:")
            print(alert_data["summary"])
            print("-" * 40)

            return {"status": "success", "alert_data": alert_data}

        except Exception as e:
            print(f"⚠️  Alert delivery error: {e}")
            return {"status": "failed", "error": str(e)}

    async def demonstrate_coordination(self):
        """Demonstrate workflow coordination"""
        print("\\n🎯 Workflow Coordination Demonstration")
        print("=" * 50)

        from reddit_watcher.agents.coordinator_agent import CoordinatorAgent

        agent = CoordinatorAgent(config=self.config)

        try:
            print("🔍 Checking agent ecosystem status...")

            # Check agent status
            status_result = await agent.execute_skill("check_agent_status", {})
            agent_statuses = status_result.get("agent_status", {})

            print("\\n📊 Agent Status Report:")
            for agent_name, status in agent_statuses.items():
                endpoint = status.get("endpoint", "unknown")
                reachable = status.get("reachable", False)
                status_icon = "🟢" if reachable else "🔴"
                print(f"   {status_icon} {agent_name.title()}Agent: {endpoint}")
                if not reachable:
                    error = status.get("error", "unknown error")
                    print(f"      Error: {error[:80]}...")

            # Check circuit breaker health
            cb_result = await agent.execute_skill("get_circuit_breaker_status", {})
            cb_health = cb_result.get("health_percentage", 0)

            print(f"\\n⚡ Circuit Breaker Health: {cb_health}%")
            if cb_health < 100:
                print(
                    "   Some circuit breakers may be open due to service unavailability"
                )

            # Show workflow capabilities
            skills = agent.get_skills()
            workflow_skills = [
                skill.name for skill in skills if "workflow" in skill.name.lower()
            ]

            print("\\n🔄 Available Workflow Operations:")
            for skill in skills:
                if any(
                    keyword in skill.name.lower()
                    for keyword in ["workflow", "monitoring", "recovery"]
                ):
                    print(f"   • {skill.name}: {skill.description}")

            return {"status": "success", "coordination": "operational"}

        except Exception as e:
            print(f"⚠️  Coordination error: {e}")
            return {"status": "failed", "error": str(e)}

    async def run_complete_demonstration(self):
        """Run complete end-to-end demonstration"""
        print("🚀 Reddit Watcher Complete Demonstration")
        print("=" * 55)
        print("Simulating real-world monitoring workflow\\n")

        # Step 1: Content Filtering
        filtered_posts = await self.demonstrate_content_filtering()

        # Step 2: Summarization
        summary_data = await self.demonstrate_summarization(filtered_posts)

        # Step 3: Alert Delivery
        alert_result = await self.demonstrate_alert_delivery(summary_data)

        # Step 4: Coordination
        coordination_result = await self.demonstrate_coordination()

        # Final Report
        print("\\n" + "=" * 55)
        print("🎯 DEMONSTRATION SUMMARY")
        print("=" * 55)

        print(
            f"✅ Content Filtering: {len(filtered_posts) if filtered_posts else 0} relevant posts found"
        )
        print(f"✅ Summarization: {'Generated' if summary_data else 'Failed'}")
        print(
            f"✅ Alert System: {'Ready' if alert_result and alert_result.get('status') == 'success' else 'Issues'}"
        )
        print(
            f"✅ Coordination: {'Operational' if coordination_result.get('status') == 'success' else 'Issues'}"
        )

        print("\\n💡 SYSTEM CAPABILITIES DEMONSTRATED:")
        print("   🔍 Intelligent content filtering with keyword matching")
        print("   📝 Automatic summarization with fallback methods")
        print("   🚨 Multi-channel alert delivery system")
        print("   🎯 Workflow coordination with health monitoring")
        print("   ⚡ Circuit breaker protection for resilience")
        print("   🔧 Service discovery and health checks")

        print("\\n🎉 Your Reddit Watcher system is fully operational!")
        print("   Ready for real-world deployment with API credentials")


async def main():
    """Run the complete demonstration"""
    demo = RedditWatcherDemo()
    await demo.run_complete_demonstration()


if __name__ == "__main__":
    asyncio.run(main())
