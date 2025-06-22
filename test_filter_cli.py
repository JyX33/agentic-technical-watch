#!/usr/bin/env python3
# ABOUTME: CLI for testing FilterAgent content relevance assessment functionality
# ABOUTME: Manual testing interface for keyword matching, semantic similarity, and batch filtering

"""
CLI for testing FilterAgent functionality.

This script provides manual testing capabilities for the FilterAgent,
allowing developers to test keyword matching, semantic similarity scoring,
and batch filtering capabilities without running the full A2A system.

Usage:
    python test_filter_cli.py

Environment variables needed:
    DATABASE_URL - PostgreSQL database connection URL (for batch testing)

The script will test:
- Agent health and semantic model status
- Keyword-based content filtering
- Semantic similarity scoring
- Individual and batch filtering operations
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.config import create_config, get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_health_check(agent: FilterAgent):
    """Test the health check functionality."""
    print("\n=== Testing Health Check ===")
    result = await agent.execute_skill("health_check", {})
    print("Health Check Result:")
    print(json.dumps(result, indent=2, default=str))

    # Check semantic model status
    if result["status"] == "success":
        filter_status = result["result"].get("filter_specific", {})
        model_status = filter_status.get("model_status", "unknown")
        print(f"\nSemantic Model Status: {model_status}")
        if model_status == "operational":
            print("✅ Semantic model is ready for similarity scoring")
            print(
                f"Embedding dimension: {filter_status.get('embedding_dimension', 'unknown')}"
            )
        elif model_status == "not_initialized":
            print("⚠️ Semantic model not initialized - only keyword filtering available")
        else:
            print(
                f"❌ Semantic model error: {filter_status.get('model_error', 'unknown')}"
            )

    return result


async def test_keyword_filtering(agent: FilterAgent):
    """Test keyword-based content filtering."""
    print("\n=== Testing Keyword Filtering ===")

    test_cases = [
        {
            "title": "Claude Code Tutorial for Beginners",
            "content": "Learn how to use Claude Code for AI development and automation",
            "description": "High relevance - matches multiple keywords",
        },
        {
            "title": "Agent-to-Agent Protocol Implementation",
            "content": "Building A2A systems for distributed agent communication",
            "description": "Medium relevance - matches A2A topic",
        },
        {
            "title": "Python Web Development",
            "content": "Building web applications with Flask and Django frameworks",
            "description": "Low relevance - no topic matches",
        },
        {
            "title": "AI Programming with Claude",
            "content": "Advanced techniques for artificial intelligence programming",
            "description": "Partial relevance - partial keyword matches",
        },
    ]

    settings = get_settings()
    print(f"Testing with topics: {settings.reddit_topics}")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        print(f"Title: {test_case['title']}")
        print(f"Content: {test_case['content'][:60]}...")

        result = await agent.execute_skill(
            "filter_content_by_keywords",
            {
                "title": test_case["title"],
                "content": test_case["content"],
            },
        )

        if result["status"] == "success":
            res = result["result"]
            print(f"Keywords matched: {res['keywords_matched']}")
            print(f"Match score: {res['match_score']:.3f}")
            print(f"Is relevant: {res['is_relevant']}")
            if res["keywords_matched"]:
                print(f"Match details: {json.dumps(res['match_details'], indent=2)}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

        await asyncio.sleep(0.5)

    return result


async def test_semantic_similarity(agent: FilterAgent):
    """Test semantic similarity filtering."""
    print("\n=== Testing Semantic Similarity ===")

    # Check if semantic model is available
    health = await agent.execute_skill("health_check", {})
    if (
        health["status"] == "success"
        and health["result"].get("filter_specific", {}).get("model_status")
        != "operational"
    ):
        print("⚠️ Semantic model not available - skipping semantic similarity tests")
        return {"status": "skipped", "reason": "Semantic model not available"}

    test_cases = [
        {
            "title": "Programming Assistant Tutorial",
            "content": "How to effectively use AI coding assistants for software development",
            "description": "Semantically similar to Claude Code",
        },
        {
            "title": "Multi-Agent System Design",
            "content": "Designing distributed systems with autonomous agents communicating via protocols",
            "description": "Semantically similar to A2A",
        },
        {
            "title": "Cooking Recipe Collection",
            "content": "Delicious recipes for homemade pasta and Italian cuisine",
            "description": "Semantically unrelated",
        },
        {
            "title": "AI Code Generation",
            "content": "Automated code generation using large language models and AI tools",
            "description": "High semantic similarity",
        },
    ]

    settings = get_settings()
    print(f"Testing semantic similarity with topics: {settings.reddit_topics}")
    print(f"Relevance threshold: {settings.relevance_threshold}")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        print(f"Title: {test_case['title']}")
        print(f"Content: {test_case['content'][:60]}...")

        result = await agent.execute_skill(
            "filter_content_by_semantic_similarity",
            {
                "title": test_case["title"],
                "content": test_case["content"],
            },
        )

        if result["status"] == "success":
            res = result["result"]
            print(f"Max similarity: {res['max_similarity']:.3f}")
            print(f"Best topic: {res['best_topic']}")
            print(f"Is relevant: {res['is_relevant']}")
            print("Topic similarities:")
            for topic, sim in res["topic_similarities"].items():
                print(f"  - {topic}: {sim:.3f}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

        await asyncio.sleep(0.5)

    return result


async def test_combined_filtering(agent: FilterAgent):
    """Test combined keyword + semantic filtering."""
    print("\n=== Testing Combined Filtering ===")

    # Check if semantic model is available
    health = await agent.execute_skill("health_check", {})
    semantic_available = (
        health["status"] == "success"
        and health["result"].get("filter_specific", {}).get("model_status")
        == "operational"
    )

    test_cases = [
        {
            "title": "Claude Code vs GitHub Copilot",
            "content": "Comparison of AI coding assistants for software development productivity",
            "expected": "High relevance - both keyword and semantic matches",
        },
        {
            "title": "Agent Communication Protocols",
            "content": "Implementing message passing between autonomous software agents",
            "expected": "Medium relevance - semantic similarity to A2A",
        },
        {
            "title": "Database Migration Scripts",
            "content": "SQL scripts for migrating data between database versions",
            "expected": "Low relevance - unrelated content",
        },
    ]

    settings = get_settings()

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Combined Test {i}: {test_case['expected']} ---")
        print(f"Title: {test_case['title']}")
        print(f"Content: {test_case['content'][:60]}...")

        # Test keyword filtering
        keyword_result = await agent.execute_skill(
            "filter_content_by_keywords",
            {
                "title": test_case["title"],
                "content": test_case["content"],
            },
        )

        # Test semantic filtering if available
        semantic_result = None
        if semantic_available:
            semantic_result = await agent.execute_skill(
                "filter_content_by_semantic_similarity",
                {
                    "title": test_case["title"],
                    "content": test_case["content"],
                },
            )

        # Display results
        if keyword_result["status"] == "success":
            kw_res = keyword_result["result"]
            print(
                f"Keyword score: {kw_res['match_score']:.3f} (matches: {kw_res['keywords_matched']})"
            )

        if semantic_result and semantic_result["status"] == "success":
            sem_res = semantic_result["result"]
            print(
                f"Semantic score: {sem_res['max_similarity']:.3f} (best: {sem_res['best_topic']})"
            )

            # Calculate combined score (70% keyword, 30% semantic)
            keyword_score = kw_res.get("match_score", 0.0)
            semantic_score = sem_res.get("max_similarity", 0.0)
            combined_score = (keyword_score * 0.7) + (semantic_score * 0.3)
            is_relevant = combined_score >= settings.relevance_threshold

            print(
                f"Combined score: {combined_score:.3f} (threshold: {settings.relevance_threshold})"
            )
            print(
                f"Final decision: {'✅ RELEVANT' if is_relevant else '❌ NOT RELEVANT'}"
            )
        else:
            print("Semantic filtering not available - using keyword-only result")

        await asyncio.sleep(0.5)

    return test_case


async def test_batch_operations(agent: FilterAgent):
    """Test batch filtering operations with sample data."""
    print("\n=== Testing Batch Operations ===")

    try:
        # Try to get some posts from database for testing
        from reddit_watcher.database.utils import get_db_session
        from reddit_watcher.models import RedditComment, RedditPost

        with get_db_session() as session:
            # Get a few recent posts
            posts = session.query(RedditPost).limit(3).all()
            comments = session.query(RedditComment).limit(3).all()

            if posts:
                print(f"\n--- Testing Batch Post Filtering ({len(posts)} posts) ---")
                post_ids = [post.post_id for post in posts]
                print(f"Post IDs: {post_ids}")

                result = await agent.execute_skill(
                    "batch_filter_posts",
                    {
                        "post_ids": post_ids,
                        "use_semantic": True,
                    },
                )

                if result["status"] == "success":
                    res = result["result"]
                    print(f"Total posts: {res['total_posts']}")
                    print(f"Processed: {res['processed']}")
                    print(f"Relevant: {res['relevant']}")
                    print(f"Stored: {res['stored']}")

                    if res["details"]:
                        print("Sample results:")
                        for detail in res["details"][:3]:
                            print(
                                f"  - {detail['post_id']}: {detail['title']} -> "
                                f"Score: {detail['relevance_score']:.3f}, "
                                f"Relevant: {detail['is_relevant']}"
                            )
                else:
                    print(
                        f"Batch post filtering failed: {result.get('error', 'Unknown error')}"
                    )
            else:
                print("No posts found in database for batch testing")

            if comments:
                print(
                    f"\n--- Testing Batch Comment Filtering ({len(comments)} comments) ---"
                )
                comment_ids = [comment.comment_id for comment in comments]
                print(f"Comment IDs: {comment_ids}")

                result = await agent.execute_skill(
                    "batch_filter_comments",
                    {
                        "comment_ids": comment_ids,
                        "use_semantic": True,
                    },
                )

                if result["status"] == "success":
                    res = result["result"]
                    print(f"Total comments: {res['total_comments']}")
                    print(f"Processed: {res['processed']}")
                    print(f"Relevant: {res['relevant']}")
                    print(f"Stored: {res['stored']}")

                    if res["details"]:
                        print("Sample results:")
                        for detail in res["details"][:3]:
                            print(
                                f"  - {detail['comment_id']}: {detail['body'][:40]}... -> "
                                f"Score: {detail['relevance_score']:.3f}, "
                                f"Relevant: {detail['is_relevant']}"
                            )
                else:
                    print(
                        f"Batch comment filtering failed: {result.get('error', 'Unknown error')}"
                    )
            else:
                print("No comments found in database for batch testing")

    except Exception as e:
        print(f"Database connection failed: {e}")
        print("Skipping batch operations test")
        return {"status": "skipped", "reason": "Database not available"}

    return result


async def run_interactive_tests():
    """Run interactive tests for FilterAgent."""
    print("=== FilterAgent Interactive Test CLI ===")
    print(f"Started at: {datetime.now()}")

    # Check configuration
    settings = get_settings()
    print("\nConfiguration:")
    print(f"Database URL: {settings.database_url}")
    print(f"Reddit topics: {settings.reddit_topics}")
    print(f"Relevance threshold: {settings.relevance_threshold}")

    # Initialize agent
    print("\n=== Initializing FilterAgent ===")
    print("⏳ Loading semantic similarity model (this may take a moment)...")
    config = create_config()
    agent = FilterAgent(config)

    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Keyword Filtering", test_keyword_filtering),
        ("Semantic Similarity", test_semantic_similarity),
        ("Combined Filtering", test_combined_filtering),
        ("Batch Operations", test_batch_operations),
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
        await asyncio.sleep(1)

    # Summary
    print(f"\n{'=' * 60}")
    print("=== Test Results Summary ===")
    for test_name, result in results.items():
        status = result.get("status", "unknown")
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⏭️"
        print(f"{emoji} {test_name}: {status}")
        if status == "skipped":
            print(f"    Reason: {result.get('reason', 'Unknown')}")

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
