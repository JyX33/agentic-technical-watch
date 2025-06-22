#!/usr/bin/env python3
# ABOUTME: Start the SummariseAgent server on port 8003
# ABOUTME: Individual script for running the summarise agent for testing

import os
import sys

# Set port before importing
os.environ["A2A_PORT"] = "8003"

from reddit_watcher.agents.server import run_agent_server
from reddit_watcher.agents.summarise_agent import SummariseAgent

if __name__ == "__main__":
    print("🚀 Starting SummariseAgent on port 8003")

    try:
        agent = SummariseAgent()
        print("✅ SummariseAgent created successfully")
        print("🌐 Server will be available at:")
        print("   Health: http://localhost:8003/health")
        print("   Agent Card: http://localhost:8003/.well-known/agent.json")
        print("   Discovery: http://localhost:8003/discover")
        print("\n⚠️  Press Ctrl+C to stop")

        run_agent_server(agent)

    except KeyboardInterrupt:
        print("\n🛑 SummariseAgent stopped by user")
    except Exception as e:
        print(f"❌ Failed to start SummariseAgent: {e}")
        sys.exit(1)
