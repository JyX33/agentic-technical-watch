#!/usr/bin/env python3
# ABOUTME: Start the FilterAgent server on port 8002
# ABOUTME: Individual script for running the filter agent for testing

import os
import sys

# Set port before importing
os.environ["A2A_PORT"] = "8002"

from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.agents.server import run_agent_server

if __name__ == "__main__":
    print("🚀 Starting FilterAgent on port 8002")

    try:
        agent = FilterAgent()
        print("✅ FilterAgent created successfully")
        print("🌐 Server will be available at:")
        print("   Health: http://localhost:8002/health")
        print("   Agent Card: http://localhost:8002/.well-known/agent.json")
        print("   Discovery: http://localhost:8002/discover")
        print("\n⚠️  Press Ctrl+C to stop")

        run_agent_server(agent)

    except KeyboardInterrupt:
        print("\n🛑 FilterAgent stopped by user")
    except Exception as e:
        print(f"❌ Failed to start FilterAgent: {e}")
        sys.exit(1)
