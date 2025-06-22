# ABOUTME: A2A HTTP server manager for Reddit monitoring agents
# ABOUTME: Handles FastAPI server setup, service discovery endpoints, and agent registration

import asyncio
import logging
import signal
import uuid
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from reddit_watcher.a2a_protocol import EventQueue, RequestContext
from reddit_watcher.agents.base import BaseA2AAgent, BaseA2AAgentExecutor
from reddit_watcher.auth_middleware import AuthMiddleware
from reddit_watcher.config import Settings
from reddit_watcher.shutdown import get_shutdown_manager, setup_graceful_shutdown

logger = logging.getLogger(__name__)


class A2AServiceDiscovery:
    """
    Redis-backed service discovery for A2A agents.

    Manages agent registration, health checks, and discovery
    within the Reddit Technical Watcher ecosystem.
    """

    def __init__(self, config: Settings):
        self.config = config
        self.redis_client: redis.Redis | None = None
        self.logger = logging.getLogger(f"{__name__}.discovery")

    async def initialize(self) -> None:
        """Initialize Redis connection for service discovery."""
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
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
                "service_url": f"http://localhost:{self.config.a2a_port}",
                "health_endpoint": f"http://localhost:{self.config.a2a_port}/health",
                "agent_card_endpoint": f"http://localhost:{self.config.a2a_port}/.well-known/agent.json",
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
        """Clean up Redis connections properly."""
        if self.redis_client:
            try:
                await self.redis_client.aclose()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.redis_client = None


class A2AAgentServer:
    """
    A2A HTTP server for Reddit monitoring agents.

    Provides FastAPI-based HTTP server with A2A protocol support,
    service discovery endpoints, and health checks.
    """

    def __init__(self, agent: BaseA2AAgent, config: Settings):
        """
        Initialize the A2A agent server.

        Args:
            agent: The agent to serve
            config: Configuration provider (injected dependency)
        """
        self.agent = agent
        self.config = config
        self.discovery = A2AServiceDiscovery(config)
        self.auth = AuthMiddleware(config)
        self.a2a_app: FastAPI | None = None
        self.app: FastAPI | None = None
        self.logger = logging.getLogger(f"{__name__}.{agent.agent_type}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.discovery.initialize()
        await self.discovery.register_agent(self.agent)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.discovery.deregister_agent(self.agent.agent_type)
        await self.discovery.cleanup()

    def __del__(self):
        """Cleanup on deletion."""
        try:
            import asyncio

            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self._async_cleanup())
        except RuntimeError:
            # Event loop is not running, can't clean up async resources
            self.logger.warning(
                "Could not cleanup server resources during deletion - event loop not running"
            )
            pass

    async def _async_cleanup(self):
        """Async cleanup method."""
        try:
            await self.discovery.deregister_agent(self.agent.agent_type)
            await self.discovery.cleanup()
        except Exception as e:
            self.logger.error(f"Error during async cleanup: {e}")

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

        # Security middleware stack (add in reverse order due to FastAPI middleware stacking)
        from reddit_watcher.security_middleware import (
            InputValidationMiddleware,
            RateLimitingMiddleware,
            SecurityAuditMiddleware,
            SecurityHeadersMiddleware,
        )

        if self.config.security_headers_enabled:
            app.add_middleware(SecurityHeadersMiddleware, config=self.config)
            app.add_middleware(RateLimitingMiddleware, config=self.config)
            app.add_middleware(InputValidationMiddleware, config=self.config)
            app.add_middleware(SecurityAuditMiddleware, config=self.config)

        # CORS middleware (more restrictive configuration)
        allowed_origins = getattr(
            self.config,
            "cors_allowed_origins",
            ["http://localhost:3000", "http://localhost:8080"],
        )
        if self.config.debug:
            allowed_origins = ["*"]  # Allow all origins in debug mode only

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-API-Key"],
        )

        # Initialize task storage for A2A protocol
        self._tasks = {}

        # Agent Card endpoint for service discovery
        @app.get("/.well-known/agent.json")
        async def get_agent_card():
            """Serve the Agent Card for A2A service discovery."""
            try:
                agent_card = self.agent.generate_agent_card()
                return JSONResponse(content=agent_card.model_dump())
            except Exception as e:
                self.logger.error(f"Error generating agent card: {e}", exc_info=True)
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

        # A2A protocol JSON-RPC endpoints (main endpoints for A2A communication)
        @app.post("/a2a")
        async def a2a_jsonrpc_endpoint(request: dict):
            """Main A2A JSON-RPC 2.0 endpoint for agent communication."""
            try:
                # Validate JSON-RPC request
                if not self._is_valid_jsonrpc_request(request):
                    return self._jsonrpc_error(
                        -32600, "Invalid Request", request.get("id")
                    )

                method = request.get("method")
                params = request.get("params", {})
                request_id = request.get("id")

                # Route to appropriate handler
                if method == "message/send":
                    return await self._handle_message_send(params, request_id)
                elif method == "message/stream":
                    return await self._handle_message_stream(params, request_id)
                elif method == "tasks/get":
                    return await self._handle_tasks_get(params, request_id)
                elif method == "tasks/cancel":
                    return await self._handle_tasks_cancel(params, request_id)
                elif method == "tasks/pushNotificationConfig/set":
                    return await self._handle_push_notification_set(params, request_id)
                elif method == "tasks/pushNotificationConfig/get":
                    return await self._handle_push_notification_get(params, request_id)
                elif method == "tasks/resubscribe":
                    return await self._handle_tasks_resubscribe(params, request_id)
                else:
                    return self._jsonrpc_error(-32601, "Method not found", request_id)

            except Exception as e:
                self.logger.error(f"A2A JSON-RPC error: {e}")
                return self._jsonrpc_error(
                    -32603, f"Internal error: {str(e)}", request.get("id")
                )

        # Direct skill invocation endpoints for testing
        @app.post("/skills/{skill_name}")
        async def invoke_skill(
            skill_name: str, request: dict, user: str = Depends(self.auth.verify_token)
        ):
            """Direct skill invocation endpoint for testing."""
            try:
                parameters = request.get("parameters", {})
                result = await self.agent.execute_skill(skill_name, parameters)
                return JSONResponse(content=result)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e
            except Exception as e:
                self.logger.error(f"Error executing skill {skill_name}: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Skill execution failed: {str(e)}"
                ) from e

        # List available skills endpoint
        @app.get("/skills")
        async def list_skills():
            """List all available skills for this agent."""
            try:
                skills = self.agent.get_skills()
                return JSONResponse(
                    content={"skills": [skill.model_dump() for skill in skills]}
                )
            except Exception as e:
                self.logger.error(f"Error listing skills: {e}")
                raise HTTPException(
                    status_code=500, detail="Failed to list skills"
                ) from e

        self.app = app
        return app

    def _is_valid_jsonrpc_request(self, request: dict) -> bool:
        """Validate JSON-RPC 2.0 request format."""
        return (
            isinstance(request, dict)
            and request.get("jsonrpc") == "2.0"
            and "method" in request
            and isinstance(request.get("method"), str)
        )

    def _jsonrpc_response(self, result: Any, request_id: Any) -> dict:
        """Create JSON-RPC 2.0 success response."""
        return {"jsonrpc": "2.0", "result": result, "id": request_id}

    def _jsonrpc_error(
        self, code: int, message: str, request_id: Any, data: Any = None
    ) -> dict:
        """Create JSON-RPC 2.0 error response."""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "error": error, "id": request_id}

    async def _handle_message_send(self, params: dict, request_id: Any) -> dict:
        """Handle message/send JSON-RPC method."""
        try:
            import uuid
            from datetime import datetime

            # Extract message from params
            message = params.get("message", {})
            metadata = params.get("metadata", {})

            # Create a task
            task_id = str(uuid.uuid4())
            context_id = str(uuid.uuid4())

            # Process the message with the executor
            executor = BaseA2AAgentExecutor(self.agent)
            context = RequestContext(
                message=message.get("parts", [{}])[0].get("text", ""), metadata=metadata
            )
            event_queue = EventQueue()

            await executor.execute(context, event_queue)
            events = event_queue.get_events()

            # Create task object according to A2A spec
            task = {
                "id": task_id,
                "contextId": context_id,
                "status": {
                    "state": "completed",
                    "message": {
                        "role": "agent",
                        "parts": [{"kind": "text", "text": str(events)}]
                        if events
                        else [{"kind": "text", "text": "Task completed"}],
                        "messageId": str(uuid.uuid4()),
                        "taskId": task_id,
                        "contextId": context_id,
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
                "artifacts": [],
                "history": [message] if message else [],
                "metadata": metadata,
                "kind": "task",
            }

            # Store task (in-memory for now)
            if not hasattr(self, "_tasks"):
                self._tasks = {}
            self._tasks[task_id] = task

            return self._jsonrpc_response(task, request_id)

        except Exception as e:
            self.logger.error(f"Error handling message/send: {e}")
            return self._jsonrpc_error(-32603, f"Internal error: {str(e)}", request_id)

    async def _handle_message_stream(self, params: dict, request_id: Any) -> dict:
        """Handle message/stream JSON-RPC method."""
        # For now, return not implemented
        return self._jsonrpc_error(-32004, "Streaming not implemented yet", request_id)

    async def _handle_tasks_get(self, params: dict, request_id: Any) -> dict:
        """Handle tasks/get JSON-RPC method."""
        try:
            task_id = params.get("id")
            if not task_id:
                return self._jsonrpc_error(
                    -32602, "Invalid params: task id required", request_id
                )

            if not hasattr(self, "_tasks"):
                self._tasks = {}

            task = self._tasks.get(task_id)
            if not task:
                return self._jsonrpc_error(-32001, "Task not found", request_id)

            return self._jsonrpc_response(task, request_id)

        except Exception as e:
            self.logger.error(f"Error handling tasks/get: {e}")
            return self._jsonrpc_error(-32603, f"Internal error: {str(e)}", request_id)

    async def _handle_tasks_cancel(self, params: dict, request_id: Any) -> dict:
        """Handle tasks/cancel JSON-RPC method."""
        try:
            task_id = params.get("id")
            if not task_id:
                return self._jsonrpc_error(
                    -32602, "Invalid params: task id required", request_id
                )

            if not hasattr(self, "_tasks"):
                self._tasks = {}

            task = self._tasks.get(task_id)
            if not task:
                return self._jsonrpc_error(-32001, "Task not found", request_id)

            # Update task status to cancelled
            task["status"]["state"] = "canceled"
            task["status"]["message"] = {
                "role": "agent",
                "parts": [{"kind": "text", "text": "Task was cancelled"}],
                "messageId": str(uuid.uuid4()),
                "taskId": task_id,
                "contextId": task["contextId"],
            }

            return self._jsonrpc_response(task, request_id)

        except Exception as e:
            self.logger.error(f"Error handling tasks/cancel: {e}")
            return self._jsonrpc_error(-32603, f"Internal error: {str(e)}", request_id)

    async def _handle_push_notification_set(
        self, params: dict, request_id: Any
    ) -> dict:
        """Handle tasks/pushNotificationConfig/set JSON-RPC method."""
        return self._jsonrpc_error(
            -32003, "Push Notification is not supported", request_id
        )

    async def _handle_push_notification_get(
        self, params: dict, request_id: Any
    ) -> dict:
        """Handle tasks/pushNotificationConfig/get JSON-RPC method."""
        return self._jsonrpc_error(
            -32003, "Push Notification is not supported", request_id
        )

    async def _handle_tasks_resubscribe(self, params: dict, request_id: Any) -> dict:
        """Handle tasks/resubscribe JSON-RPC method."""
        return self._jsonrpc_error(
            -32004, "Streaming resubscription not supported", request_id
        )

    async def start_server(self) -> None:
        """Start the A2A agent server with graceful shutdown."""
        try:
            # Setup graceful shutdown
            setup_graceful_shutdown()
            shutdown_manager = get_shutdown_manager()

            # Register server cleanup handlers
            shutdown_manager.add_async_shutdown_handler(self._async_cleanup)

            app = self.create_app()

            config = uvicorn.Config(
                app,
                host=self.config.a2a_host,
                port=self.config.a2a_port,
                log_level="info",
                access_log=True,
            )

            server = uvicorn.Server(config)

            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                self.logger.info(f"Received signal {signum}, shutting down...")
                server.should_exit = True
                shutdown_manager.initiate_shutdown()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            self.logger.info(
                f"Starting A2A server for {self.agent.name} on "
                f"http://{self.config.a2a_host}:{self.config.a2a_port}"
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


def create_agent_server(agent: BaseA2AAgent, config: Settings) -> A2AAgentServer:
    """
    Factory function to create an A2A agent server.

    Args:
        agent: The agent to serve
        config: Configuration provider (injected dependency)

    Returns:
        Configured A2AAgentServer instance
    """
    return A2AAgentServer(agent, config)


def run_agent_server(agent: BaseA2AAgent, config: Settings) -> None:
    """
    Run an A2A agent server (blocking).

    Args:
        agent: The agent to serve
        config: Configuration provider (injected dependency)
    """
    server = create_agent_server(agent, config)
    server.run()
