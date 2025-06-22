#!/usr/bin/env python3
# ABOUTME: Quick test to debug agent card generation issues
# ABOUTME: Tests agent card generation independently of server

import os

from dotenv import load_dotenv

# Load environment
load_dotenv()
os.environ["REDIS_URL"] = "redis://default:dev_redis_123@localhost:16379/0"

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.config import get_settings


def test_agent_card():
    """Test agent card generation."""
    try:
        print("🧪 Testing agent card generation...")

        # Create config and agent
        config = get_settings()
        agent = CoordinatorAgent(config)

        print(f"✅ Agent created: {agent.name}")

        # Generate agent card
        agent_card = agent.generate_agent_card()
        print(f"✅ Agent card generated: {type(agent_card)}")

        # Test model_dump
        card_dict = agent_card.model_dump()
        print(f"✅ Agent card converted to dict: {len(card_dict)} fields")

        # Print the card structure
        print("\n📋 Agent Card Structure:")
        for key, value in card_dict.items():
            if isinstance(value, list):
                print(f"  {key}: {len(value)} items")
            elif isinstance(value, dict):
                print(f"  {key}: {list(value.keys())}")
            else:
                print(f"  {key}: {value}")

        print("\n✅ Agent card generation successful!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_agent_card()
