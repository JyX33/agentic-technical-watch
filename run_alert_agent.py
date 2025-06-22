#!/usr/bin/env python3
# ABOUTME: AlertAgent A2A server for multi-channel notifications on port 8004
# ABOUTME: Handles Slack webhook and SMTP email alerts with rich formatting and delivery tracking

import asyncio
import os
import sys

# Set port before importing
os.environ["A2A_PORT"] = "8004"

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.agents.server import A2AAgentServer


async def main():
    """Start the AlertAgent A2A server."""
    print("🚀 Starting AlertAgent on port 8004")

    # Create agent
    agent = AlertAgent()

    # Create server
    server = A2AAgentServer(agent=agent)

    try:
        await server.start_server()
    except KeyboardInterrupt:
        print("\n🛑 AlertAgent stopped by user")
    except Exception as e:
        print(f"❌ Failed to start AlertAgent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
