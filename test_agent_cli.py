#!/usr/bin/env python3
"""
Simple CLI for testing the A2A agent implementation.
"""

import asyncio
import json
import sys

from reddit_watcher.agents.test_agent import MockA2AAgent
from reddit_watcher.config import create_config


async def main():
    """Main CLI function."""
    config = create_config()
    agent = MockA2AAgent(config)

    print(f"=== {agent.name} ===")
    print(f"Type: {agent.agent_type}")
    print(f"Description: {agent.description}")
    print(f"Version: {agent.version}")
    print()

    # Test Agent Card generation
    print("=== Agent Card ===")
    try:
        card = agent.generate_agent_card()
        print("✓ Agent Card generated successfully")
        print(f"  Name: {card.name}")
        print(f"  URL: {card.url}")
        print(f"  Skills: {len(card.skills)}")
        print(f"  Provider: {card.provider.organization}")
    except Exception as e:
        print(f"✗ Agent Card generation failed: {e}")
        return 1

    print()

    # Test skill execution
    print("=== Skill Execution ===")

    # Test health check
    try:
        result = await agent.execute_skill("health_check", {})
        print(f"✓ Health check: {result.get('status')}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")

    # Test echo skill
    try:
        result = await agent.execute_skill("echo", {"message": "Hello A2A!"})
        print(f"✓ Echo skill: {result.get('status')}")
        print(f"  Original: {result.get('result', {}).get('original_message')}")
    except Exception as e:
        print(f"✗ Echo skill failed: {e}")

    # Test reddit topics
    try:
        result = await agent.execute_skill("reddit_topics", {})
        print(f"✓ Reddit topics: {result.get('status')}")
        topics = result.get("result", {}).get("topics", [])
        print(f"  Topics: {', '.join(topics[:3])}")
    except Exception as e:
        print(f"✗ Reddit topics failed: {e}")

    print()

    # Test Agent Card JSON
    print("=== Agent Card JSON ===")
    try:
        card_json = agent.get_agent_card_json()
        card_dict = json.loads(card_json)
        print("✓ Agent Card JSON generated successfully")
        print(f"  JSON keys: {len(card_dict.keys())}")
        print(f"  Skills in JSON: {len(card_dict.get('skills', []))}")
    except Exception as e:
        print(f"✗ Agent Card JSON failed: {e}")

    print()
    print("=== Test Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
