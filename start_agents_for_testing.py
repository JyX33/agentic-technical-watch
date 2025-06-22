#!/usr/bin/env python3
# ABOUTME: Start all agent servers for complete workflow integration testing
# ABOUTME: Manages agent lifecycle with health monitoring and graceful shutdown

import asyncio
import logging
import signal
import sys
import time
from multiprocessing import Process

import aiohttp

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.agents.server import run_agent_server
from reddit_watcher.agents.summarise_agent import SummariseAgent
from reddit_watcher.config import get_settings


class AgentOrchestrator:
    """Orchestrates agent lifecycle for integration testing."""

    def __init__(self):
        self.config = get_settings()
        self.agents = []
        self.processes = []
        self.shutdown_event = asyncio.Event()
        self.logger = self._setup_logging()

        # Agent configuration
        self.agent_configs = [
            (RetrievalAgent, self.config.a2a_port + 1, "RetrievalAgent"),
            (FilterAgent, self.config.a2a_port + 2, "FilterAgent"),
            (SummariseAgent, self.config.a2a_port + 3, "SummariseAgent"),
            (AlertAgent, self.config.a2a_port + 4, "AlertAgent"),
        ]

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for agent orchestration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("agent_orchestrator.log"),
            ],
        )
        return logging.getLogger(__name__)

    def _run_agent_process(self, agent_class, port: int, agent_name: str):
        """Run a single agent server in a separate process."""
        try:
            # Set up logging for this process
            process_logger = logging.getLogger(f"{agent_name}-{port}")
            process_logger.info(f"Starting {agent_name} on port {port}")

            # Set environment variables for this process
            import os

            os.environ["A2A_PORT"] = str(port)
            os.environ["A2A_HOST"] = "0.0.0.0"

            # Create and configure agent
            agent = agent_class(self.config)

            print(f"🚀 {agent_name} server starting on http://localhost:{port}")
            print(f"   Health endpoint: http://localhost:{port}/health")
            print(f"   Agent card: http://localhost:{port}/.well-known/agent.json")

            # Run the agent server (blocking)
            run_agent_server(agent)

        except KeyboardInterrupt:
            print(f"🛑 {agent_name} received shutdown signal")
        except Exception as e:
            print(f"❌ {agent_name} failed: {e}")
            self.logger.error(f"{agent_name} process failed: {e}", exc_info=True)

    async def start_agents(self) -> bool:
        """Start all agent servers and wait for them to be healthy."""
        print("🌟 Starting Reddit Watcher Agent Ecosystem")
        print("=" * 60)

        try:
            # Start all agent processes
            for agent_class, port, agent_name in self.agent_configs:
                process = Process(
                    target=self._run_agent_process,
                    args=(agent_class, port, agent_name),
                    name=f"{agent_name}-Process",
                )
                process.start()
                self.processes.append((process, agent_name, port))

                # Small delay between starts
                await asyncio.sleep(1)

            print(f"\n✅ Started {len(self.processes)} agent processes")

            # Wait for agents to be healthy
            print("\n🏥 Waiting for agents to become healthy...")
            healthy_agents = await self._wait_for_agents_healthy()

            if healthy_agents:
                print(
                    f"✅ {healthy_agents} out of {len(self.agent_configs)} agents are healthy"
                )
                return True
            else:
                print("❌ No agents became healthy")
                return False

        except Exception as e:
            self.logger.error(f"Failed to start agents: {e}")
            await self.stop_agents()
            return False

    async def _wait_for_agents_healthy(self, max_wait: int = 60) -> int:
        """Wait for agents to become healthy with timeout."""
        start_time = time.time()
        healthy_count = 0

        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < max_wait:
                healthy_count = 0

                for _, agent_name, port in self.processes:
                    try:
                        async with session.get(
                            f"http://localhost:{port}/health",
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as response:
                            if response.status == 200:
                                healthy_count += 1
                                print(f"✅ {agent_name} (:{port}) is healthy")
                            else:
                                print(
                                    f"⚠️ {agent_name} (:{port}) returned status {response.status}"
                                )
                    except Exception as e:
                        print(f"⚠️ {agent_name} (:{port}) not ready: {e}")

                if healthy_count == len(self.processes):
                    print(f"\n🎉 All {healthy_count} agents are healthy!")
                    break

                print(
                    f"⏳ {healthy_count}/{len(self.processes)} agents healthy, waiting..."
                )
                await asyncio.sleep(5)

        return healthy_count

    async def monitor_agents(self):
        """Monitor agent health during testing."""
        print("\n📊 Starting agent health monitoring...")

        while not self.shutdown_event.is_set():
            try:
                alive_count = sum(
                    1 for process, _, _ in self.processes if process.is_alive()
                )

                if alive_count < len(self.processes):
                    dead_agents = [
                        (name, port)
                        for process, name, port in self.processes
                        if not process.is_alive()
                    ]
                    self.logger.warning(f"Dead agents detected: {dead_agents}")

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(10)

    async def stop_agents(self):
        """Stop all agent processes gracefully."""
        print("\n🛑 Stopping all agents...")

        for process, agent_name, port in self.processes:
            if process.is_alive():
                print(f"⏳ Stopping {agent_name} (:{port})...")
                process.terminate()

                # Wait for graceful shutdown
                process.join(timeout=10)

                if process.is_alive():
                    print(f"🔥 Force killing {agent_name} (:{port})")
                    process.kill()
                    process.join()

                print(f"✅ {agent_name} stopped")

        self.processes.clear()
        print("✅ All agents stopped")

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            print(f"\n🛑 Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def run_agent_ecosystem():
    """Run the complete agent ecosystem for integration testing."""
    orchestrator = AgentOrchestrator()
    orchestrator.setup_signal_handlers()

    try:
        # Start all agents
        if not await orchestrator.start_agents():
            print("❌ Failed to start agent ecosystem")
            return 1

        print("\n🎯 Agent ecosystem ready for integration testing!")
        print("=" * 60)
        print("Available endpoints:")

        for _, agent_name, port in orchestrator.agent_configs:
            print(f"  {agent_name}: http://localhost:{port}")

        print("\n💡 Usage:")
        print("  1. Run integration tests in another terminal:")
        print("     uv run python test_complete_workflow_integration.py")
        print("  2. Or test individual agents:")
        print("     curl http://localhost:8001/health")
        print("  3. Press Ctrl+C to stop all agents")

        # Monitor agents until shutdown
        monitor_task = asyncio.create_task(orchestrator.monitor_agents())

        # Wait for shutdown signal
        await orchestrator.shutdown_event.wait()

        # Cancel monitoring
        monitor_task.cancel()

        return 0

    except Exception as e:
        print(f"❌ Agent ecosystem failed: {e}")
        orchestrator.logger.error(f"Agent ecosystem error: {e}", exc_info=True)
        return 1

    finally:
        await orchestrator.stop_agents()


async def main():
    """Main entry point."""
    print("🚀 Reddit Watcher - Agent Ecosystem for Integration Testing")
    print("=" * 70)

    exit_code = await run_agent_ecosystem()

    print("\n" + "=" * 70)
    print("🏁 Agent ecosystem shutdown complete")

    return exit_code


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
