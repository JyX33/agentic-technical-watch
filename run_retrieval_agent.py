#!/usr/bin/env python3
# ABOUTME: Start the RetrievalAgent server on port 8001
# ABOUTME: Individual script for running the retrieval agent for testing

import os
import sys

# Set port before importing
os.environ["A2A_PORT"] = "8001"

from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.agents.server import run_agent_server

if __name__ == "__main__":
    print("🚀 Starting RetrievalAgent on port 8001")

    try:
        agent = RetrievalAgent()
        print("✅ RetrievalAgent created successfully")
        print("🌐 Server will be available at:")
        print("   Health: http://localhost:8001/health")
        print("   Agent Card: http://localhost:8001/.well-known/agent.json")
        print("   Discovery: http://localhost:8001/discover")
        print("\n⚠️  Press Ctrl+C to stop")

        run_agent_server(agent)

    except KeyboardInterrupt:
        print("\n🛑 RetrievalAgent stopped by user")
    except Exception as e:
        print(f"❌ Failed to start RetrievalAgent: {e}")
        sys.exit(1)
