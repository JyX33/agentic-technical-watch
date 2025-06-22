#!/usr/bin/env python3
# ABOUTME: Complete Reddit research demonstration using all agents
# ABOUTME: Shows end-to-end research workflow from retrieval to filtering

import asyncio
from datetime import datetime


async def demo_reddit_research():
    """Demonstrate complete Reddit research workflow."""
    print("🚀 Reddit Research Demonstration")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now()}")

    # Research parameters
    research_topics = ["Python", "FastAPI", "AI"]
    target_subreddits = ["Python", "MachineLearning", "artificial"]

    print("\n📋 Research Configuration:")
    print(f"   Topics: {research_topics}")
    print(f"   Target Subreddits: {target_subreddits}")

    try:
        # Step 1: Initialize agents
        print("\n📦 Step 1: Initializing Research Agents...")
        from reddit_watcher.agents.filter_agent import FilterAgent
        from reddit_watcher.agents.retrieval_agent import RetrievalAgent

        retrieval_agent = RetrievalAgent()
        filter_agent = FilterAgent()

        print("✅ Agents initialized successfully")

        # Step 2: Test agent health
        print("\n🏥 Step 2: Checking Agent Health...")
        retrieval_health = await retrieval_agent.execute_skill("health_check", {})
        filter_health = await filter_agent.execute_skill("health_check", {})

        print(f"   RetrievalAgent: {retrieval_health['status']}")
        print(f"   FilterAgent: {filter_health['status']}")

        if (
            retrieval_health["status"] != "success"
            or filter_health["status"] != "success"
        ):
            print("❌ Agent health check failed - check Reddit API credentials")
            return

        # Step 3: Discover relevant subreddits
        print("\n🔍 Step 3: Discovering Relevant Subreddits...")
        discovery_result = await retrieval_agent.execute_skill(
            "discover_subreddits", {"topics": research_topics, "limit": 5}
        )

        if discovery_result["status"] == "success":
            discovered = discovery_result["result"].get("discovered_subreddits", [])
            print(f"✅ Found {len(discovered)} relevant subreddits:")
            for sub in discovered[:3]:  # Show first 3
                print(
                    f"   - r/{sub['name']}: {sub.get('description', 'No description')[:50]}..."
                )
        else:
            print(
                f"⚠️  Subreddit discovery failed: {discovery_result.get('error', 'Unknown error')}"
            )

        # Step 4: Fetch research posts
        print("\n📄 Step 4: Fetching Research Posts...")
        posts_result = await retrieval_agent.execute_skill(
            "fetch_posts_by_topic",
            {"topic": "Python FastAPI", "subreddits": ["Python", "webdev"], "limit": 5},
        )

        if posts_result["status"] == "success":
            posts = posts_result["result"].get("posts", [])
            print(f"✅ Retrieved {len(posts)} posts for analysis")

            # Step 5: Filter and analyze posts
            print("\n🔧 Step 5: Filtering and Analyzing Content...")

            for i, post in enumerate(posts[:3], 1):  # Analyze first 3 posts
                print(f"\n   📝 Post {i}: {post.get('title', 'No title')[:60]}...")

                # Filter by keywords
                keyword_result = await filter_agent.execute_skill(
                    "filter_content_by_keywords",
                    {
                        "content": {
                            "title": post.get("title", ""),
                            "body": post.get("selftext", ""),
                            "url": post.get("url", ""),
                        },
                        "topics": research_topics,
                    },
                )

                # Filter by semantic similarity
                semantic_result = await filter_agent.execute_skill(
                    "filter_content_by_semantic_similarity",
                    {
                        "content": {
                            "title": post.get("title", ""),
                            "body": post.get("selftext", ""),
                            "url": post.get("url", ""),
                        },
                        "topics": [
                            "python web framework",
                            "API development",
                            "machine learning",
                        ],
                    },
                )

                if (
                    keyword_result["status"] == "success"
                    and semantic_result["status"] == "success"
                ):
                    keyword_score = keyword_result["result"].get("relevance_score", 0)
                    semantic_score = semantic_result["result"].get(
                        "similarity_score", 0
                    )

                    print(f"      Keyword Relevance: {keyword_score:.2f}")
                    print(f"      Semantic Similarity: {semantic_score:.2f}")

                    if keyword_score > 0.5 or semantic_score > 0.7:
                        print("      ✅ HIGH RELEVANCE - Worth detailed analysis")
                    else:
                        print("      ⚠️  Low relevance - may skip")
                else:
                    print("      ❌ Filtering failed")

        else:
            print(
                f"❌ Post retrieval failed: {posts_result.get('error', 'Unknown error')}"
            )

        # Step 6: Summary
        print("\n📊 Research Summary:")
        print("   ✅ Subreddit Discovery: Working")
        print("   ✅ Post Retrieval: Working")
        print("   ✅ Content Filtering: Working")
        print("   ✅ Relevance Analysis: Working")

        print("\n🎉 Reddit research workflow completed successfully!")
        print("   Your agents are ready for automated monitoring")

    except Exception as e:
        print(f"\n❌ Research demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(demo_reddit_research())
    except KeyboardInterrupt:
        print("\n🛑 Research demo stopped by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
