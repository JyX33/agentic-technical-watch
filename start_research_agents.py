#!/usr/bin/env python3
# ABOUTME: Start all agents for Reddit research workflow
# ABOUTME: Launches RetrievalAgent, FilterAgent, SummariseAgent, and AlertAgent

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class AgentManager:
    def __init__(self):
        self.processes = []
        self.agent_configs = [
            {
                "name": "RetrievalAgent",
                "port": 8001,
                "script": "run_retrieval_agent.py",
            },
            {"name": "FilterAgent", "port": 8002, "script": "run_filter_agent.py"},
            {
                "name": "SummariseAgent",
                "port": 8003,
                "script": "run_summarise_agent.py",
            },
            {"name": "AlertAgent", "port": 8004, "script": "run_alert_agent.py"},
        ]

    def start_agents(self):
        """Start all agent servers."""
        print("🚀 Starting Reddit Research Agents")
        print("=" * 50)

        for config in self.agent_configs:
            script_path = Path(config["script"])
            if not script_path.exists():
                print(f"⚠️  {config['script']} not found - skipping {config['name']}")
                continue

            print(f"📦 Starting {config['name']} on port {config['port']}...")

            try:
                # Start the agent process
                process = subprocess.Popen(
                    [sys.executable, config["script"]],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=os.environ.copy(),
                )

                self.processes.append(
                    {"name": config["name"], "port": config["port"], "process": process}
                )

                time.sleep(2)  # Give each agent time to start

                if process.poll() is None:
                    print(f"✅ {config['name']} started successfully")
                else:
                    print(f"❌ {config['name']} failed to start")

            except Exception as e:
                print(f"❌ Failed to start {config['name']}: {e}")

        if self.processes:
            print(f"\n🌐 Started {len(self.processes)} agents:")
            for proc_info in self.processes:
                print(f"   {proc_info['name']}: http://localhost:{proc_info['port']}")

            print("\n💡 Agents are ready for research!")
            print("   Test with: uv run python test_real_workflow.py")
            print("   Manual test: uv run python manual_reddit_research.py")
            print("\n⚠️  Press Ctrl+C to stop all agents")
        else:
            print("\n❌ No agents started successfully")
            return False

        return True

    def stop_agents(self):
        """Stop all agent processes."""
        print("\n🛑 Stopping all agents...")

        for proc_info in self.processes:
            try:
                process = proc_info["process"]
                if process.poll() is None:
                    print(f"   Stopping {proc_info['name']}...")
                    process.terminate()

                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"   Force killing {proc_info['name']}...")
                        process.kill()
                        process.wait()

            except Exception as e:
                print(f"   Error stopping {proc_info['name']}: {e}")

        print("✅ All agents stopped")

    def wait_for_agents(self):
        """Wait for agents and handle shutdown."""
        try:
            # Wait for any process to exit
            while True:
                time.sleep(1)
                for proc_info in self.processes:
                    if proc_info["process"].poll() is not None:
                        print(f"⚠️  {proc_info['name']} has stopped unexpectedly")
                        return

        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
            self.stop_agents()


def main():
    manager = AgentManager()

    # Set up signal handlers
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}")
        manager.stop_agents()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start agents
    if manager.start_agents():
        manager.wait_for_agents()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
