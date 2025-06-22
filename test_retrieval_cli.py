#!/usr/bin/env python3
# ABOUTME: CLI for testing RetrievalAgent Reddit data fetching functionality
# ABOUTME: Manual testing interface for PRAW integration and A2A skills validation

"""
CLI for testing RetrievalAgent functionality.

This script provides manual testing capabilities for the RetrievalAgent,
allowing developers to test Reddit API integration, rate limiting, and
data fetching capabilities without running the full A2A system.

Usage:
    python test_retrieval_cli.py

Environment variables needed:
    REDDIT_CLIENT_ID - Reddit OAuth2 client ID
    REDDIT_CLIENT_SECRET - Reddit OAuth2 client secret
    DATABASE_URL - PostgreSQL database connection URL
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_health_check(agent: RetrievalAgent):
    """Test the health check functionality."""
    print("\n=== Testing Health Check ===")
    result = await agent.execute_skill("health_check", {})
    print("Health Check Result:")
    print(json.dumps(result, indent=2, default=str))
    return result


async def test_fetch_posts_by_topic(agent: RetrievalAgent):
    """Test fetching posts by topic."""
    print("\n=== Testing Fetch Posts by Topic ===")

    # Test with default settings topics
    settings = get_settings()
    for topic in settings.reddit_topics[:2]:  # Test first 2 topics
        print(f"\nFetching posts for topic: {topic}")
        result = await agent.execute_skill(
            "fetch_posts_by_topic",
            {"topic": topic, "subreddit": "all", "limit": 5, "time_range": "day"},
        )
        print(f"Result: {result['status']}")
        if result["status"] == "success":
            posts_found = result["result"]["posts_found"]
            posts_stored = result["result"]["posts_stored"]
            print(f"Posts found: {posts_found}, stored: {posts_stored}")

            # Show first post if any
            if result["result"]["posts"]:
                first_post = result["result"]["posts"][0]
                print(f"First post: {first_post['title'][:60]}...")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

        # Small delay between requests
        await asyncio.sleep(1)

    return result


async def test_fetch_comments(agent: RetrievalAgent):
    """Test fetching comments from a post."""
    print("\n=== Testing Fetch Comments ===")

    # First, we need to find a post ID to test with
    print("First fetching a post to get a post ID...")
    settings = get_settings()
    post_result = await agent.execute_skill(
        "fetch_posts_by_topic",
        {
            "topic": settings.reddit_topics[0],
            "limit": 1,
        },
    )

    if post_result["status"] != "success" or not post_result["result"]["posts"]:
        print("No posts found to test comments with")
        return {"status": "skipped", "reason": "No posts available"}

    post_id = post_result["result"]["posts"][0]["post_id"]
    print(f"Testing comments for post ID: {post_id}")

    result = await agent.execute_skill(
        "fetch_comments_from_post",
        {
            "post_id": post_id,
            "limit": 10,
        },
    )

    print(f"Result: {result['status']}")
    if result["status"] == "success":
        comments_found = result["result"]["comments_found"]
        comments_stored = result["result"]["comments_stored"]
        print(f"Comments found: {comments_found}, stored: {comments_stored}")

        # Show first comment if any
        if result["result"]["comments"]:
            first_comment = result["result"]["comments"][0]
            print(f"First comment: {first_comment['body'][:60]}...")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    return result


async def test_discover_subreddits(agent: RetrievalAgent):
    """Test discovering subreddits."""
    print("\n=== Testing Discover Subreddits ===")

    settings = get_settings()
    topic = settings.reddit_topics[0]  # Use first topic
    print(f"Discovering subreddits for topic: {topic}")

    result = await agent.execute_skill(
        "discover_subreddits",
        {
            "topic": topic,
            "limit": 5,
        },
    )

    print(f"Result: {result['status']}")
    if result["status"] == "success":
        subreddits_found = result["result"]["subreddits_found"]
        subreddits_stored = result["result"]["subreddits_stored"]
        print(f"Subreddits found: {subreddits_found}, stored: {subreddits_stored}")

        # Show discovered subreddits
        for subreddit in result["result"]["subreddits"]:
            print(f"  - r/{subreddit['name']}: {subreddit['title'][:40]}...")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    return result


async def test_fetch_subreddit_info(agent: RetrievalAgent):
    """Test fetching subreddit information."""
    print("\n=== Testing Fetch Subreddit Info ===")

    # Test with a known subreddit
    subreddit_name = "test"
    print(f"Fetching info for subreddit: r/{subreddit_name}")

    result = await agent.execute_skill(
        "fetch_subreddit_info",
        {
            "subreddit_name": subreddit_name,
        },
    )

    print(f"Result: {result['status']}")
    if result["status"] == "success":
        info = result["result"]["info"]
        print(f"Subreddit: r/{info['name']}")
        print(f"Title: {info['title']}")
        print(f"Subscribers: {info['subscribers']:,}")
        print(f"Description: {info['description'][:100]}...")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    return result


async def run_interactive_tests():
    """Run interactive tests for RetrievalAgent."""
    print("=== RetrievalAgent Interactive Test CLI ===")
    print(f"Started at: {datetime.now()}")

    # Check configuration
    settings = get_settings()
    print("\nConfiguration:")
    print(f"Reddit credentials configured: {settings.has_reddit_credentials()}")
    print(f"Database URL: {settings.database_url}")
    print(f"Reddit topics: {settings.reddit_topics}")
    print(f"Rate limit: {settings.reddit_rate_limit} RPM")

    if not settings.has_reddit_credentials():
        print("\n❌ Warning: Reddit credentials not configured!")
        print("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables")
        print("Some tests may fail or be limited")

    # Initialize agent
    print("\n=== Initializing RetrievalAgent ===")
    agent = RetrievalAgent(settings)

    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Fetch Posts by Topic", test_fetch_posts_by_topic),
        ("Fetch Comments", test_fetch_comments),
        ("Discover Subreddits", test_discover_subreddits),
        ("Fetch Subreddit Info", test_fetch_subreddit_info),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            print(f"\n{'=' * 60}")
            print(f"Running: {test_name}")
            result = await test_func(agent)
            results[test_name] = result
            print(f"✅ {test_name} completed")
        except Exception as e:
            logger.error(f"❌ {test_name} failed: {e}")
            results[test_name] = {"status": "error", "error": str(e)}

        # Small delay between tests
        await asyncio.sleep(2)

    # Summary
    print(f"\n{'=' * 60}")
    print("=== Test Results Summary ===")
    for test_name, result in results.items():
        status = result.get("status", "unknown")
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⏭️"
        print(f"{emoji} {test_name}: {status}")

    print(f"\nTesting completed at: {datetime.now()}")


async def main():
    """Main entry point."""
    try:
        await run_interactive_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Testing failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
