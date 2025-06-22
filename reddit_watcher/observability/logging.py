# ABOUTME: Structured logging system with correlation IDs and request tracing
# ABOUTME: Provides consistent logging format, correlation tracking, and log aggregation for all components

import asyncio
import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

# Context variables for request tracking
request_id_context: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="")
agent_type_context: ContextVar[str] = ContextVar("agent_type", default="")
operation_context: ContextVar[str] = ContextVar("operation", default="")


@dataclass
class LogEntry:
    """Structured log entry with metadata."""

    timestamp: str
    level: str
    message: str
    agent_type: str = ""
    request_id: str = ""
    correlation_id: str = ""
    operation: str = ""
    duration_ms: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class StructuredFormatter(logging.Formatter):
    """
    Structured JSON formatter for consistent logging.

    Features:
    - JSON output format
    - Request/correlation ID inclusion
    - Metadata extraction from log records
    - Error information formatting
    - Performance metrics inclusion
    """

    def __init__(self, include_timestamp: bool = True, include_level: bool = True):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_level = include_level

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Get context information
        request_id = request_id_context.get("")
        correlation_id = correlation_id_context.get("")
        agent_type = agent_type_context.get("")
        operation = operation_context.get("")

        # Extract metadata from record
        metadata = {}
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "exc_info",
                "exc_text",
                "stack_info",
                "request_id",
                "correlation_id",
                "agent_type",
                "operation",
                "duration_ms",
                "error",
            ):
                metadata[key] = value

        # Handle exception information
        error_info = None
        if record.exc_info:
            error_info = self.formatException(record.exc_info)
        elif hasattr(record, "error"):
            error_info = str(record.error)

        # Create structured log entry
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created, UTC).isoformat(),
            level=record.levelname,
            message=record.getMessage(),
            agent_type=getattr(record, "agent_type", agent_type),
            request_id=getattr(record, "request_id", request_id),
            correlation_id=getattr(record, "correlation_id", correlation_id),
            operation=getattr(record, "operation", operation),
            duration_ms=getattr(record, "duration_ms", None),
            error=error_info,
            metadata=metadata if metadata else None,
        )

        return log_entry.to_json()


class CorrelationLogger:
    """
    Logger wrapper that automatically includes correlation information.

    Features:
    - Automatic request/correlation ID inclusion
    - Operation timing
    - Metadata attachment
    - Context preservation across async boundaries
    """

    def __init__(self, logger: logging.Logger, agent_type: str = ""):
        self.logger = logger
        self.default_agent_type = agent_type

    def _log(self, level: int, msg: str, **kwargs):
        """Internal logging method with context injection."""
        extra = {
            "agent_type": kwargs.pop(
                "agent_type", agent_type_context.get(self.default_agent_type)
            ),
            "request_id": kwargs.pop("request_id", request_id_context.get("")),
            "correlation_id": kwargs.pop(
                "correlation_id", correlation_id_context.get("")
            ),
            "operation": kwargs.pop("operation", operation_context.get("")),
        }

        # Add any additional metadata
        for key, value in kwargs.items():
            extra[key] = value

        self.logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs):
        """Log debug message with context."""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message with context."""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message with context."""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, error: Exception | None = None, **kwargs):
        """Log error message with context and exception info."""
        if error:
            kwargs["error"] = str(error)
            # Don't set exc_info as it's handled by logging framework
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, error: Exception | None = None, **kwargs):
        """Log critical message with context and exception info."""
        if error:
            kwargs["error"] = str(error)
            # Don't set exc_info as it's handled by logging framework
        self._log(logging.CRITICAL, msg, **kwargs)

    @contextmanager
    def operation(self, operation_name: str, **metadata):
        """Context manager for operation logging with timing."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]

        # Set operation context
        operation_token = operation_context.set(operation_name)

        try:
            self.info(
                f"Starting operation: {operation_name}",
                operation_id=operation_id,
                **metadata,
            )
            yield self
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error(
                f"Operation failed: {operation_name}",
                error=e,
                operation_id=operation_id,
                duration_ms=duration_ms,
                **metadata,
            )
            raise
        else:
            duration_ms = (time.time() - start_time) * 1000
            self.info(
                f"Operation completed: {operation_name}",
                operation_id=operation_id,
                duration_ms=duration_ms,
                **metadata,
            )
        finally:
            operation_context.reset(operation_token)


class LoggingManager:
    """
    Centralized logging management for Reddit Technical Watcher.

    Features:
    - Structured logging setup
    - Agent-specific loggers
    - Correlation ID management
    - Performance logging
    - Log level configuration
    """

    def __init__(self):
        self.loggers: dict[str, CorrelationLogger] = {}
        self.configured = False

    def configure_logging(
        self,
        level: str = "INFO",
        format_type: str = "structured",
        enable_file_logging: bool = True,
        log_file: str = "reddit_watcher.log",
    ):
        """Configure global logging settings."""
        if self.configured:
            return

        # Set root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Configure formatter
        if format_type == "structured":
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (if enabled)
        if enable_file_logging:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        self.configured = True

    def get_logger(self, name: str, agent_type: str = "") -> CorrelationLogger:
        """Get or create a correlation logger."""
        if name not in self.loggers:
            base_logger = logging.getLogger(name)
            self.loggers[name] = CorrelationLogger(base_logger, agent_type)
        return self.loggers[name]

    def set_request_context(
        self,
        request_id: str | None = None,
        correlation_id: str | None = None,
        agent_type: str | None = None,
    ):
        """Set request context for correlation."""
        if request_id:
            request_id_context.set(request_id)
        if correlation_id:
            correlation_id_context.set(correlation_id)
        if agent_type:
            agent_type_context.set(agent_type)

    @contextmanager
    def request_context(
        self,
        request_id: str | None = None,
        correlation_id: str | None = None,
        agent_type: str | None = None,
    ):
        """Context manager for request correlation."""
        # Generate IDs if not provided
        if not request_id:
            request_id = str(uuid.uuid4())
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Set context
        req_token = request_id_context.set(request_id)
        corr_token = correlation_id_context.set(correlation_id)
        agent_token = None
        if agent_type:
            agent_token = agent_type_context.set(agent_type)

        try:
            yield {
                "request_id": request_id,
                "correlation_id": correlation_id,
                "agent_type": agent_type,
            }
        finally:
            # Reset context
            request_id_context.reset(req_token)
            correlation_id_context.reset(corr_token)
            if agent_token:
                agent_type_context.reset(agent_token)


# Global logging manager
_logging_manager = LoggingManager()


def configure_logging(**kwargs):
    """Configure global logging settings."""
    _logging_manager.configure_logging(**kwargs)


def get_logger(name: str, agent_type: str = "") -> CorrelationLogger:
    """Get a correlation logger instance."""
    return _logging_manager.get_logger(name, agent_type)


def set_request_context(**kwargs):
    """Set request context for correlation."""
    _logging_manager.set_request_context(**kwargs)


@contextmanager
def request_context(**kwargs):
    """Context manager for request correlation."""
    with _logging_manager.request_context(**kwargs) as context:
        yield context


# Decorators for automatic operation logging
def log_operation(
    operation_name: str | None = None,
    agent_type: str | None = None,
    logger_name: str | None = None,
):
    """Decorator for automatic operation logging."""

    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = func.__name__

        logger_name_actual = logger_name or f"{func.__module__}.{func.__qualname__}"
        logger = get_logger(logger_name_actual, agent_type or "")

        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                with logger.operation(operation_name, function=func.__name__):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                with logger.operation(operation_name, function=func.__name__):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def log_performance(logger_name: str | None = None, agent_type: str | None = None):
    """Decorator for performance logging."""

    def decorator(func):
        logger_name_actual = logger_name or f"{func.__module__}.{func.__qualname__}"
        logger = get_logger(logger_name_actual, agent_type or "")

        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    logger.debug(
                        f"Function {func.__name__} completed",
                        duration_ms=duration_ms,
                        success=True,
                    )
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.error(
                        f"Function {func.__name__} failed",
                        error=e,
                        duration_ms=duration_ms,
                        success=False,
                    )
                    raise

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    logger.debug(
                        f"Function {func.__name__} completed",
                        duration_ms=duration_ms,
                        success=True,
                    )
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.error(
                        f"Function {func.__name__} failed",
                        error=e,
                        duration_ms=duration_ms,
                        success=False,
                    )
                    raise

            return sync_wrapper

    return decorator


# FastAPI middleware for request correlation
class LoggingMiddleware:
    """FastAPI middleware for request correlation and logging."""

    def __init__(self, app, agent_type: str = ""):
        self.app = app
        self.agent_type = agent_type
        self.logger = get_logger(f"{__name__}.middleware", agent_type)

    async def __call__(self, scope, receive, send):
        """Process request with correlation logging."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate correlation IDs
        request_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        # Set context
        with request_context(
            request_id=request_id,
            correlation_id=correlation_id,
            agent_type=self.agent_type,
        ):
            start_time = time.time()

            # Log request start
            self.logger.info(
                f"Request started: {scope['method']} {scope['path']}",
                request_id=request_id,
                correlation_id=correlation_id,
                method=scope["method"],
                path=scope["path"],
                client=scope.get("client", ["unknown", 0])[0],
            )

            try:
                await self.app(scope, receive, send)
                duration_ms = (time.time() - start_time) * 1000
                self.logger.info(
                    f"Request completed: {scope['method']} {scope['path']}",
                    request_id=request_id,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    success=True,
                )
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.logger.error(
                    f"Request failed: {scope['method']} {scope['path']}",
                    error=e,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    success=False,
                )
                raise


# Context manager for async task correlation
@contextmanager
def async_task_context(task_name: str, **metadata):
    """Context manager for async task correlation."""
    task_id = str(uuid.uuid4())[:8]
    correlation_id = correlation_id_context.get() or str(uuid.uuid4())

    logger = get_logger(f"async_task.{task_name}")

    with request_context(request_id=task_id, correlation_id=correlation_id):
        logger.info(f"Async task started: {task_name}", task_id=task_id, **metadata)
        start_time = time.time()

        try:
            yield
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Async task completed: {task_name}",
                task_id=task_id,
                duration_ms=duration_ms,
                **metadata,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Async task failed: {task_name}",
                error=e,
                task_id=task_id,
                duration_ms=duration_ms,
                **metadata,
            )
            raise
