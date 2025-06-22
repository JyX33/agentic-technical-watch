#!/usr/bin/env python3
# ABOUTME: Manual Reddit research script for step-by-step testing
# ABOUTME: Allows testing individual agents and research workflows

import asyncio
import sys
from datetime import datetime


async def test_retrieval_research(topics: list[str], subreddits: list[str]):
    """Test retrieval agent for Reddit research."""
    print("🔍 Testing Reddit Retrieval Research")
    print("=" * 50)

    try:
        from reddit_watcher.agents.retrieval_agent import RetrievalAgent

        agent = RetrievalAgent()

        # Test health
        health = await agent.execute_skill("health_check", {})
        print(f"✅ Retrieval Agent Health: {health['status']}")

        # Test subreddit discovery
        discovery_result = await agent.execute_skill(
            "discover_subreddits", {"topics": topics, "limit": 5}
        )
        print(f"🔍 Discovered Subreddits: {discovery_result['status']}")

        # Test post fetching
        fetch_result = await agent.execute_skill(
            "fetch_posts", {"subreddits": subreddits, "topics": topics, "limit": 10}
        )
        print(f"📄 Fetched Posts: {fetch_result['status']}")

        return True

    except Exception as e:
        print(f"❌ Retrieval test failed: {e}")
        return False


async def test_filter_research(sample_content: dict):
    """Test filter agent for content relevance."""
    print("\n🔧 Testing Content Filtering")
    print("=" * 50)

    try:
        from reddit_watcher.agents.filter_agent import FilterAgent

        agent = FilterAgent()

        # Test keyword filtering
        keyword_result = await agent.execute_skill(
            "filter_content_by_keywords",
            {"content": sample_content, "topics": ["Python", "AI", "FastAPI"]},
        )
        print(f"🔤 Keyword Filter: {keyword_result['status']}")

        # Test semantic filtering
        semantic_result = await agent.execute_skill(
            "filter_content_by_semantic_similarity",
            {
                "content": sample_content,
                "topics": ["artificial intelligence", "machine learning"],
            },
        )
        print(f"🧠 Semantic Filter: {semantic_result['status']}")

        return True

    except Exception as e:
        print(f"❌ Filter test failed: {e}")
        return False


async def main():
    """Run manual Reddit research tests."""
    print("🚀 Manual Reddit Research Testing")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now()}")

    # Research parameters
    research_topics = ["Python", "FastAPI", "AI", "machine learning"]
    target_subreddits = ["Python", "MachineLearning", "artificial", "programming"]

    print("\n📋 Research Configuration:")
    print(f"   Topics: {research_topics}")
    print(f"   Subreddits: {target_subreddits}")

    # Sample content for testing
    sample_content = {
        "title": "New Python FastAPI tutorial with AI integration",
        "body": "This tutorial covers building REST APIs with FastAPI and integrating machine learning models",
        "url": "https://example.com/fastapi-ai-tutorial",
    }

    # Test retrieval
    retrieval_success = await test_retrieval_research(
        research_topics, target_subreddits
    )

    # Test filtering
    filter_success = await test_filter_research(sample_content)

    # Summary
    print("\n📊 Test Results Summary:")
    print(f"   Retrieval: {'✅ PASS' if retrieval_success else '❌ FAIL'}")
    print(f"   Filtering: {'✅ PASS' if filter_success else '❌ FAIL'}")

    if retrieval_success and filter_success:
        print("\n🎉 Manual research tests passed!")
        print("   Ready for full workflow testing")
    else:
        print("\n⚠️  Some tests failed - check configuration")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Testing stopped by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
