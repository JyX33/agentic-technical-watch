#!/usr/bin/env python3
# ABOUTME: Debug version of FilterAgent server with detailed error reporting
# ABOUTME: Enhanced error handling and step-by-step debugging for agent server startup

import asyncio
import logging
import os
import sys
import traceback

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Set port before importing
os.environ["A2A_PORT"] = "8002"

print("🔧 Debug FilterAgent Startup")
print("=" * 50)

try:
    print("📦 Step 1: Importing FilterAgent...")
    from reddit_watcher.agents.filter_agent import FilterAgent

    print("✅ FilterAgent imported successfully")

    print("📦 Step 2: Importing server components...")
    from reddit_watcher.agents.server import create_agent_server

    print("✅ Server components imported successfully")

    print("📦 Step 3: Creating FilterAgent instance...")
    agent = FilterAgent()
    print("✅ FilterAgent instance created successfully")

    print("📦 Step 4: Testing agent health check...")

    async def test_health():
        result = await agent.execute_skill("health_check", {})
        print(f"✅ Health check result: {result['status']}")
        return result

    health_result = asyncio.run(test_health())

    print("📦 Step 5: Creating server instance...")
    server = create_agent_server(agent)
    print("✅ Server instance created successfully")

    print("📦 Step 6: Starting server...")
    print("🌐 Server will be available at:")
    print("   Health: http://localhost:8002/health")
    print("   Agent Card: http://localhost:8002/.well-known/agent.json")
    print("   Discovery: http://localhost:8002/discover")
    print("\n⚠️  Press Ctrl+C to stop")

    # Run the server
    server.run()

except KeyboardInterrupt:
    print("\n🛑 FilterAgent stopped by user")
except Exception as e:
    print(f"\n❌ Error during startup: {e}")
    print(f"📍 Error type: {type(e).__name__}")
    print("📍 Traceback:")
    traceback.print_exc()
    sys.exit(1)
