# ABOUTME: A2A HTTP server manager for Reddit monitoring agents
# ABOUTME: Handles FastAPI server setup, service discovery endpoints, and agent registration

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from reddit_watcher.a2a_protocol import EventQueue, RequestContext
from reddit_watcher.agents.base import BaseA2AAgent, BaseA2AAgentExecutor
from reddit_watcher.config import get_settings

logger = logging.getLogger(__name__)


# Custom A2A FastAPI application implementation
class A2AFastAPIApplication:
    """FastAPI application wrapper for A2A agents."""

    def __init__(self, executor):
        self.executor = executor
        self.app = FastAPI(
            title="A2A Agent Server", description="Agent-to-Agent protocol server"
        )
        self._setup_routes()

    def _setup_routes(self):
        """Set up A2A protocol routes."""

        @self.app.post("/message")
        async def handle_message(request: dict):
            """Handle A2A protocol messages."""
            context = RequestContext(
                message=request.get("message", ""), metadata=request.get("metadata", {})
            )
            event_queue = EventQueue()

            await self.executor.execute(context, event_queue)

            # Return events as response
            events = event_queue.get_events()
            return {"events": events, "status": "success"}

        @self.app.post("/stream")
        async def handle_stream(request: dict):
            """Handle streaming A2A protocol messages."""
            # Placeholder for streaming support
            return {"status": "streaming_not_implemented"}

        @self.app.get("/task/{task_id}")
        async def get_task_status(task_id: str):
            """Get task status."""
            # Placeholder for task status tracking
            return {"task_id": task_id, "status": "unknown"}


class A2AServiceDiscovery:
    """
    Redis-backed service discovery for A2A agents.

    Manages agent registration, health checks, and discovery
    within the Reddit Technical Watcher ecosystem.
    """

    def __init__(self):
        self.settings = get_settings()
        self.redis_client: redis.Redis | None = None
        self.logger = logging.getLogger(f"{__name__}.discovery")

    async def initialize(self) -> None:
        """Initialize Redis connection for service discovery."""
        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            await self.redis_client.ping()
            self.logger.info("Service discovery initialized with Redis")
        except Exception as e:
            self.logger.error(f"Failed to initialize service discovery: {e}")
            raise

    async def register_agent(self, agent: BaseA2AAgent) -> None:
        """
        Register an agent in the service discovery registry.

        Args:
            agent: The agent to register
        """
        if not self.redis_client:
            raise RuntimeError("Service discovery not initialized")

        try:
            agent_info = {
                "name": agent.name,
                "type": agent.agent_type,
                "description": agent.description,
                "version": agent.version,
                "service_url": f"http://localhost:{self.settings.a2a_port}",
                "health_endpoint": f"http://localhost:{self.settings.a2a_port}/health",
                "agent_card_endpoint": f"http://localhost:{self.settings.a2a_port}/.well-known/agent.json",
                "last_seen": str(asyncio.get_event_loop().time()),
            }

            # Store in Redis with TTL
            key = f"agent:{agent.agent_type}"
            await self.redis_client.hset(key, mapping=agent_info)
            await self.redis_client.expire(key, 300)  # 5 minutes TTL

            self.logger.info(
                f"Registered agent {agent.agent_type} in service discovery"
            )

        except Exception as e:
            self.logger.error(f"Failed to register agent {agent.agent_type}: {e}")
            raise

    async def deregister_agent(self, agent_type: str) -> None:
        """
        Deregister an agent from the service discovery registry.

        Args:
            agent_type: Type of agent to deregister
        """
        if not self.redis_client:
            return

        try:
            key = f"agent:{agent_type}"
            await self.redis_client.delete(key)
            self.logger.info(f"Deregistered agent {agent_type} from service discovery")
        except Exception as e:
            self.logger.error(f"Failed to deregister agent {agent_type}: {e}")

    async def discover_agents(self) -> dict[str, dict[str, Any]]:
        """
        Discover all registered agents.

        Returns:
            Dictionary mapping agent types to agent information
        """
        if not self.redis_client:
            return {}

        try:
            keys = await self.redis_client.keys("agent:*")
            agents = {}

            for key in keys:
                agent_info = await self.redis_client.hgetall(key)
                if agent_info:
                    agent_type = key.replace("agent:", "")
                    agents[agent_type] = agent_info

            return agents

        except Exception as e:
            self.logger.error(f"Failed to discover agents: {e}")
            return {}

    async def update_health(self, agent_type: str) -> None:
        """
        Update the health timestamp for an agent.

        Args:
            agent_type: Type of agent to update
        """
        if not self.redis_client:
            return

        try:
            key = f"agent:{agent_type}"
            if await self.redis_client.exists(key):
                await self.redis_client.hset(
                    key, "last_seen", str(asyncio.get_event_loop().time())
                )
                await self.redis_client.expire(key, 300)  # Reset TTL
        except Exception as e:
            self.logger.error(f"Failed to update health for agent {agent_type}: {e}")

    async def cleanup(self) -> None:
        """Clean up Redis connections."""
        if self.redis_client:
            await self.redis_client.aclose()


class A2AAgentServer:
    """
    A2A HTTP server for Reddit monitoring agents.

    Provides FastAPI-based HTTP server with A2A protocol support,
    service discovery endpoints, and health checks.
    """

    def __init__(self, agent: BaseA2AAgent):
        """
        Initialize the A2A agent server.

        Args:
            agent: The agent to serve
        """
        self.agent = agent
        self.settings = get_settings()
        self.discovery = A2AServiceDiscovery()
        self.a2a_app: FastAPI | None = None
        self.app: FastAPI | None = None
        self.logger = logging.getLogger(f"{__name__}.{agent.agent_type}")

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """FastAPI lifespan context manager."""
        try:
            # Startup
            await self.discovery.initialize()
            await self.discovery.register_agent(self.agent)

            # A2A executor will be created during app creation

            self.logger.info(f"A2A agent server started for {self.agent.agent_type}")
            yield

        finally:
            # Shutdown
            await self.discovery.deregister_agent(self.agent.agent_type)
            await self.discovery.cleanup()
            self.logger.info(f"A2A agent server stopped for {self.agent.agent_type}")

    def create_app(self) -> FastAPI:
        """
        Create and configure the FastAPI application.

        Returns:
            Configured FastAPI application
        """
        app = FastAPI(
            title=f"{self.agent.name} - A2A Agent",
            description=self.agent.description,
            version=self.agent.version,
            lifespan=self.lifespan,
        )

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Create A2A executor and app
        executor = BaseA2AAgentExecutor(self.agent)
        a2a_fastapi_app = A2AFastAPIApplication(executor)
        a2a_app = a2a_fastapi_app.app

        # Agent Card endpoint for service discovery
        @app.get("/.well-known/agent.json")
        async def get_agent_card():
            """Serve the Agent Card for A2A service discovery."""
            try:
                agent_card = self.agent.generate_agent_card()
                return JSONResponse(content=agent_card.model_dump())
            except Exception as e:
                self.logger.error(f"Error generating agent card: {e}")
                raise HTTPException(
                    status_code=500, detail="Failed to generate agent card"
                ) from e

        # Health check endpoint
        @app.get("/health")
        async def health_check():
            """Health check endpoint for service monitoring."""
            try:
                health_status = self.agent.get_health_status()
                await self.discovery.update_health(self.agent.agent_type)
                return JSONResponse(content=health_status)
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                return JSONResponse(
                    status_code=503, content={"status": "unhealthy", "error": str(e)}
                )

        # Service discovery endpoint
        @app.get("/discover")
        async def discover_agents():
            """Discover all registered A2A agents."""
            try:
                agents = await self.discovery.discover_agents()
                return JSONResponse(content={"agents": agents})
            except Exception as e:
                self.logger.error(f"Service discovery failed: {e}")
                raise HTTPException(
                    status_code=500, detail="Service discovery failed"
                ) from e

        # A2A protocol endpoints (mounted by A2A FastAPI app)
        app.mount("/a2a", a2a_app)

        self.app = app
        return app

    async def start_server(self) -> None:
        """Start the A2A agent server."""
        try:
            app = self.create_app()

            config = uvicorn.Config(
                app,
                host=self.settings.a2a_host,
                port=self.settings.a2a_port,
                log_level="info",
                access_log=True,
            )

            server = uvicorn.Server(config)

            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                self.logger.info(f"Received signal {signum}, shutting down...")
                server.should_exit = True

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            self.logger.info(
                f"Starting A2A server for {self.agent.name} on "
                f"http://{self.settings.a2a_host}:{self.settings.a2a_port}"
            )

            await server.serve()

        except Exception as e:
            self.logger.error(f"Failed to start A2A server: {e}")
            raise

    def run(self) -> None:
        """Run the A2A agent server (blocking)."""
        try:
            asyncio.run(self.start_server())
        except KeyboardInterrupt:
            self.logger.info("Server shutdown requested")
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise


def create_agent_server(agent: BaseA2AAgent) -> A2AAgentServer:
    """
    Factory function to create an A2A agent server.

    Args:
        agent: The agent to serve

    Returns:
        Configured A2AAgentServer instance
    """
    return A2AAgentServer(agent)


def run_agent_server(agent: BaseA2AAgent) -> None:
    """
    Run an A2A agent server (blocking).

    Args:
        agent: The agent to serve
    """
    server = create_agent_server(agent)
    server.run()
