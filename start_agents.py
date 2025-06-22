#!/usr/bin/env python3
# ABOUTME: Script to start all agent servers for real testing
# ABOUTME: Launches each agent on its designated port for A2A communication

import logging
from multiprocessing import Process

from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.agents.server import run_agent_server
from reddit_watcher.agents.summarise_agent import SummariseAgent
from reddit_watcher.config import get_settings


def setup_logging():
    """Setup logging for agent servers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def run_agent_process(agent_class, port, agent_name):
    """Run a single agent server in a separate process."""
    try:
        print(f"🚀 Starting {agent_name} on port {port}")

        # Set the port in settings for this process
        import os

        os.environ["A2A_PORT"] = str(port)

        # Create agent instance
        agent = agent_class()

        print(f"✅ {agent_name} server starting on http://localhost:{port}")
        print(f"   Health: http://localhost:{port}/health")
        print(f"   Agent Card: http://localhost:{port}/.well-known/agent.json")

        # Run the agent server (blocking)
        run_agent_server(agent)

    except Exception as e:
        print(f"❌ Failed to start {agent_name}: {e}")
        raise


def start_all_agents():
    """Start all agent servers in separate processes."""
    setup_logging()

    settings = get_settings()
    base_port = settings.a2a_port

    # Define agents and their ports
    agents = [
        (RetrievalAgent, base_port + 1, "RetrievalAgent"),
        (FilterAgent, base_port + 2, "FilterAgent"),
        (SummariseAgent, base_port + 3, "SummariseAgent"),
        # TODO: Add AlertAgent when implemented
        # (AlertAgent, base_port + 4, "AlertAgent"),
    ]

    processes = []

    try:
        print("🌟 Starting Reddit Watcher Agent Servers")
        print("=" * 50)

        for agent_class, port, agent_name in agents:
            process = Process(
                target=run_agent_process,
                args=(agent_class, port, agent_name),
                name=f"{agent_name}-{port}",
            )
            process.start()
            processes.append(process)

        print(f"\n✅ Started {len(processes)} agent servers")
        print("\n🔗 Agent Endpoints:")
        for _, port, agent_name in agents:
            print(f"   {agent_name}: http://localhost:{port}")

        print("\n⚠️  Press Ctrl+C to stop all agents")

        # Wait for all processes
        for process in processes:
            process.join()

    except KeyboardInterrupt:
        print("\n🛑 Stopping all agents...")

        # Terminate all processes
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()

        print("✅ All agents stopped")

    except Exception as e:
        print(f"❌ Error managing agents: {e}")

        # Cleanup
        for process in processes:
            if process.is_alive():
                process.terminate()


if __name__ == "__main__":
    start_all_agents()
