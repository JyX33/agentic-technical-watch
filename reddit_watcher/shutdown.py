# ABOUTME: Graceful shutdown utilities for Reddit monitoring agents
# ABOUTME: Handles proper cleanup of all resources during application shutdown

import asyncio
import logging
import signal
import sys
from collections.abc import Callable
from typing import Any

from reddit_watcher.database.utils import (
    async_close_database_connections,
    close_database_connections,
)

logger = logging.getLogger(__name__)


class GracefulShutdownManager:
    """
    Manages graceful shutdown of Reddit monitoring agents.

    Handles proper cleanup of database connections, HTTP sessions,
    Redis connections, and other resources during application shutdown.
    """

    def __init__(self):
        self.shutdown_handlers: list[Callable] = []
        self.async_shutdown_handlers: list[Callable] = []
        self.is_shutting_down = False

    def add_shutdown_handler(self, handler: Callable):
        """Add a synchronous shutdown handler."""
        self.shutdown_handlers.append(handler)

    def add_async_shutdown_handler(self, handler: Callable):
        """Add an asynchronous shutdown handler."""
        self.async_shutdown_handlers.append(handler)

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received shutdown signal {signum}")
            self.initiate_shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def initiate_shutdown(self):
        """Initiate graceful shutdown process."""
        if self.is_shutting_down:
            logger.warning("Shutdown already in progress")
            return

        self.is_shutting_down = True
        logger.info("Initiating graceful shutdown...")

        # Run sync handlers first
        for handler in self.shutdown_handlers:
            try:
                logger.debug(f"Running sync shutdown handler: {handler.__name__}")
                handler()
            except Exception as e:
                logger.error(f"Error in sync shutdown handler {handler.__name__}: {e}")

        # Run async handlers
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule async cleanup
                asyncio.create_task(self._async_shutdown())
            else:
                # Run async cleanup in new loop
                asyncio.run(self._async_shutdown())
        except Exception as e:
            logger.error(f"Error running async shutdown handlers: {e}")

        logger.info("Graceful shutdown completed")

    async def _async_shutdown(self):
        """Run async shutdown handlers."""
        for handler in self.async_shutdown_handlers:
            try:
                logger.debug(f"Running async shutdown handler: {handler.__name__}")
                await handler()
            except Exception as e:
                logger.error(f"Error in async shutdown handler {handler.__name__}: {e}")


# Global shutdown manager instance
_shutdown_manager = GracefulShutdownManager()


def get_shutdown_manager() -> GracefulShutdownManager:
    """Get the global shutdown manager instance."""
    return _shutdown_manager


def setup_graceful_shutdown():
    """Setup graceful shutdown for Reddit monitoring agents."""
    manager = get_shutdown_manager()

    # Add database cleanup handlers
    manager.add_shutdown_handler(close_database_connections)
    manager.add_async_shutdown_handler(async_close_database_connections)

    # Setup signal handlers
    manager.setup_signal_handlers()

    logger.info("Graceful shutdown configured")


def register_cleanup_handler(handler: Callable):
    """Register a synchronous cleanup handler."""
    get_shutdown_manager().add_shutdown_handler(handler)


def register_async_cleanup_handler(handler: Callable):
    """Register an asynchronous cleanup handler."""
    get_shutdown_manager().add_async_shutdown_handler(handler)


def shutdown_on_exception(func: Callable) -> Callable:
    """Decorator to trigger shutdown on unhandled exceptions."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unhandled exception in {func.__name__}: {e}", exc_info=True)
            get_shutdown_manager().initiate_shutdown()
            raise

    return wrapper


async def async_shutdown_on_exception(func: Callable) -> Callable:
    """Async decorator to trigger shutdown on unhandled exceptions."""

    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unhandled exception in {func.__name__}: {e}", exc_info=True)
            get_shutdown_manager().initiate_shutdown()
            raise

    return wrapper


def cleanup_and_exit(exit_code: int = 0):
    """Force cleanup and exit the application."""
    logger.info(f"Forcing application exit with code {exit_code}")
    get_shutdown_manager().initiate_shutdown()
    sys.exit(exit_code)


# Context manager for automatic resource cleanup
class ResourceManager:
    """Context manager for automatic resource cleanup."""

    def __init__(self):
        self.resources = []

    def add_resource(self, resource: Any, cleanup_method: str = "close"):
        """Add a resource with its cleanup method."""
        self.resources.append((resource, cleanup_method))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup all managed resources."""
        for resource, cleanup_method in reversed(self.resources):
            try:
                if hasattr(resource, cleanup_method):
                    cleanup_func = getattr(resource, cleanup_method)
                    if asyncio.iscoroutinefunction(cleanup_func):
                        await cleanup_func()
                    else:
                        cleanup_func()
                    logger.debug(f"Cleaned up resource {type(resource).__name__}")
            except Exception as e:
                logger.error(
                    f"Error cleaning up resource {type(resource).__name__}: {e}"
                )
