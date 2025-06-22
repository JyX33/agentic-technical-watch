# ABOUTME: Distributed tracing system for A2A agent communication flows
# ABOUTME: Provides end-to-end request tracing, span management, and performance correlation across agents

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.propagate import extract, inject
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

    # Fallback classes when OpenTelemetry is not available
    class trace:
        @staticmethod
        def get_tracer(*args, **kwargs):
            return None

        class Status:
            OK = "ok"
            ERROR = "error"


from reddit_watcher.observability.logging import get_logger

logger = logging.getLogger(__name__)

# Context variables for trace propagation
trace_id_context: ContextVar[str] = ContextVar("trace_id", default="")
span_id_context: ContextVar[str] = ContextVar("span_id", default="")
parent_span_id_context: ContextVar[str] = ContextVar("parent_span_id", default="")


class SpanKind(Enum):
    """Span kinds for different types of operations."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass
class SpanContext:
    """Span context information for manual tracing."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    baggage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "baggage": self.baggage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpanContext":
        """Create from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_span_id=data.get("parent_span_id"),
            baggage=data.get("baggage", {}),
        )


@dataclass
class Span:
    """Manual span implementation for when OpenTelemetry is not available."""

    name: str
    span_id: str
    trace_id: str
    parent_span_id: str | None
    kind: SpanKind
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"

    def set_attribute(self, key: str, value: Any):
        """Set span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None):
        """Add span event."""
        event = {
            "name": name,
            "timestamp": datetime.now(UTC).isoformat(),
            "attributes": attributes or {},
        }
        self.events.append(event)

    def set_status(self, status: str, description: str | None = None):
        """Set span status."""
        self.status = status
        if description:
            self.attributes["status_description"] = description

    def finish(self):
        """Finish the span."""
        self.end_time = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "name": self.name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": (
                (self.end_time - self.start_time).total_seconds() * 1000
                if self.end_time
                else None
            ),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
        }


class TracingProvider:
    """
    Centralized tracing provider for Reddit Technical Watcher.

    Features:
    - OpenTelemetry integration with fallback
    - A2A communication tracing
    - Cross-service correlation
    - Manual span management
    - Jaeger/OTLP export
    - Performance analysis
    """

    def __init__(
        self,
        service_name: str = "reddit-watcher",
        service_version: str = "1.0.0",
        jaeger_endpoint: str | None = None,
        otlp_endpoint: str | None = None,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.jaeger_endpoint = jaeger_endpoint
        self.otlp_endpoint = otlp_endpoint

        self.tracer = None
        self.manual_spans: dict[str, Span] = {}
        self.trace_exports: list[dict[str, Any]] = []

        # Initialize logger first
        self.logger = get_logger(__name__, service_name)

        # Initialize tracing
        self._init_tracing()

    def _init_tracing(self):
        """Initialize OpenTelemetry tracing."""
        if not OPENTELEMETRY_AVAILABLE:
            self.logger.warning("OpenTelemetry not available, using manual tracing")
            return

        try:
            # Create resource
            resource = Resource.create(
                {
                    SERVICE_NAME: self.service_name,
                    SERVICE_VERSION: self.service_version,
                }
            )

            # Set up tracer provider
            trace.set_tracer_provider(TracerProvider(resource=resource))
            tracer_provider = trace.get_tracer_provider()

            # Add exporters
            if self.jaeger_endpoint:
                jaeger_exporter = JaegerExporter(
                    agent_host_name="localhost",
                    agent_port=6831,
                )
                tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
                self.logger.info("Jaeger exporter configured")

            if self.otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
                tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                self.logger.info("OTLP exporter configured")

            # Get tracer
            self.tracer = trace.get_tracer(
                __name__,
                version=self.service_version,
            )

            # Instrument common libraries
            HTTPXClientInstrumentor().instrument()
            RedisInstrumentor().instrument()
            SQLAlchemyInstrumentor().instrument()

            self.logger.info("OpenTelemetry tracing initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize OpenTelemetry: {e}")
            self.tracer = None

    def create_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_context: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Create a new span."""
        # Generate IDs
        span_id = str(uuid.uuid4())[:16]

        if parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
        else:
            # Check if we have a current trace context
            current_trace_id = trace_id_context.get("")
            if current_trace_id:
                trace_id = current_trace_id
                parent_span_id = span_id_context.get("")
            else:
                trace_id = str(uuid.uuid4())[:32]
                parent_span_id = None

        # Create span
        span = Span(
            name=name,
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            start_time=datetime.now(UTC),
        )

        # Set initial attributes
        if attributes:
            span.attributes.update(attributes)

        # Store span
        self.manual_spans[span_id] = span

        return span

    def get_current_span_context(self) -> SpanContext | None:
        """Get the current span context."""
        trace_id = trace_id_context.get("")
        span_id = span_id_context.get("")
        parent_span_id = parent_span_id_context.get("")

        if trace_id and span_id:
            return SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id if parent_span_id else None,
            )

        return None

    def inject_trace_context(self, headers: dict[str, str]) -> dict[str, str]:
        """Inject trace context into HTTP headers for propagation."""
        context = self.get_current_span_context()
        if context:
            headers["x-trace-id"] = context.trace_id
            headers["x-span-id"] = context.span_id
            if context.parent_span_id:
                headers["x-parent-span-id"] = context.parent_span_id

        return headers

    def extract_trace_context(self, headers: dict[str, str]) -> SpanContext | None:
        """Extract trace context from HTTP headers."""
        trace_id = headers.get("x-trace-id")
        span_id = headers.get("x-span-id")
        parent_span_id = headers.get("x-parent-span-id")

        if trace_id and span_id:
            return SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
            )

        return None

    def finish_span(self, span: Span):
        """Finish a span and export it."""
        span.finish()

        # Export for analysis
        self.trace_exports.append(span.to_dict())

        # Remove from active spans
        if span.span_id in self.manual_spans:
            del self.manual_spans[span.span_id]

        self.logger.debug(
            f"Finished span: {span.name} (duration: {(span.end_time - span.start_time).total_seconds() * 1000:.2f}ms)"
        )

    @contextmanager
    def span_context(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ):
        """Context manager for span creation and management."""
        span = self.create_span(name, kind, attributes=attributes)

        # Set context variables
        trace_token = trace_id_context.set(span.trace_id)
        span_token = span_id_context.set(span.span_id)
        parent_token = None
        if span.parent_span_id:
            parent_token = parent_span_id_context.set(span.parent_span_id)

        try:
            yield span
        except Exception as e:
            span.set_status("error", str(e))
            span.add_event(
                "exception",
                {
                    "exception.type": type(e).__name__,
                    "exception.message": str(e),
                },
            )
            raise
        finally:
            self.finish_span(span)

            # Reset context
            trace_id_context.reset(trace_token)
            span_id_context.reset(span_token)
            if parent_token:
                parent_span_id_context.reset(parent_token)

    @asynccontextmanager
    async def async_span_context(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ):
        """Async context manager for span creation and management."""
        span = self.create_span(name, kind, attributes=attributes)

        # Set context variables
        trace_token = trace_id_context.set(span.trace_id)
        span_token = span_id_context.set(span.span_id)
        parent_token = None
        if span.parent_span_id:
            parent_token = parent_span_id_context.set(span.parent_span_id)

        try:
            yield span
        except Exception as e:
            span.set_status("error", str(e))
            span.add_event(
                "exception",
                {
                    "exception.type": type(e).__name__,
                    "exception.message": str(e),
                },
            )
            raise
        finally:
            self.finish_span(span)

            # Reset context
            trace_id_context.reset(trace_token)
            span_id_context.reset(span_token)
            if parent_token:
                parent_span_id_context.reset(parent_token)

    def get_trace_summary(self, limit: int = 100) -> dict[str, Any]:
        """Get trace summary statistics."""
        recent_traces = self.trace_exports[-limit:] if self.trace_exports else []

        if not recent_traces:
            return {
                "total_traces": 0,
                "average_duration_ms": 0,
                "error_rate": 0,
                "spans_by_service": {},
            }

        # Calculate statistics
        durations = [t["duration_ms"] for t in recent_traces if t["duration_ms"]]
        error_count = len([t for t in recent_traces if t["status"] == "error"])

        # Group by service/operation
        spans_by_service = {}
        for trace in recent_traces:
            service = trace["attributes"].get("service.name", "unknown")
            if service not in spans_by_service:
                spans_by_service[service] = 0
            spans_by_service[service] += 1

        return {
            "total_traces": len(recent_traces),
            "average_duration_ms": sum(durations) / len(durations) if durations else 0,
            "error_rate": (error_count / len(recent_traces)) * 100
            if recent_traces
            else 0,
            "spans_by_service": spans_by_service,
            "active_spans": len(self.manual_spans),
        }


# Global tracing provider
_tracing_provider: TracingProvider | None = None


def get_tracing_provider() -> TracingProvider:
    """Get the global tracing provider."""
    global _tracing_provider
    if _tracing_provider is None:
        _tracing_provider = TracingProvider()
    return _tracing_provider


def initialize_tracing(
    service_name: str = "reddit-watcher",
    service_version: str = "1.0.0",
    jaeger_endpoint: str | None = None,
    otlp_endpoint: str | None = None,
):
    """Initialize global tracing."""
    global _tracing_provider
    _tracing_provider = TracingProvider(
        service_name=service_name,
        service_version=service_version,
        jaeger_endpoint=jaeger_endpoint,
        otlp_endpoint=otlp_endpoint,
    )


# Convenience functions and decorators
def trace_operation(
    operation_name: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
):
    """Decorator for automatic operation tracing."""

    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                tracer = get_tracing_provider()
                async with tracer.async_span_context(
                    operation_name, kind, attributes
                ) as span:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                tracer = get_tracing_provider()
                with tracer.span_context(operation_name, kind, attributes) as span:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def trace_a2a_communication(
    agent_type: str,
    skill_name: str,
    target_agent: str | None = None,
):
    """Decorator for A2A communication tracing."""

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                tracer = get_tracing_provider()

                # Determine span kind
                kind = SpanKind.CLIENT if target_agent else SpanKind.SERVER
                span_name = f"a2a.{skill_name}"

                attributes = {
                    "a2a.agent_type": agent_type,
                    "a2a.skill_name": skill_name,
                    "a2a.protocol": "google_a2a",
                }

                if target_agent:
                    attributes["a2a.target_agent"] = target_agent

                async with tracer.async_span_context(
                    span_name, kind, attributes
                ) as span:
                    # Add parameters if available
                    if len(args) > 1 and isinstance(args[1], dict):
                        span.set_attribute("a2a.parameter_count", len(args[1]))

                    span.add_event("a2a.skill_execution_start")

                    try:
                        result = await func(*args, **kwargs)

                        # Add result metadata
                        if isinstance(result, dict):
                            span.set_attribute("a2a.result_keys", list(result.keys()))

                        span.add_event("a2a.skill_execution_success")
                        return result

                    except Exception as e:
                        span.add_event(
                            "a2a.skill_execution_error",
                            {
                                "error.type": type(e).__name__,
                                "error.message": str(e),
                            },
                        )
                        raise

            return async_wrapper
        else:
            return func  # Non-async A2A functions not supported

    return decorator


@contextmanager
def trace_context(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
):
    """Convenience context manager for tracing."""
    tracer = get_tracing_provider()
    with tracer.span_context(name, kind, attributes) as span:
        yield span


@asynccontextmanager
async def async_trace_context(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
):
    """Convenience async context manager for tracing."""
    tracer = get_tracing_provider()
    async with tracer.async_span_context(name, kind, attributes) as span:
        yield span


def get_current_trace_id() -> str | None:
    """Get the current trace ID."""
    return trace_id_context.get("") or None


def get_current_span_id() -> str | None:
    """Get the current span ID."""
    return span_id_context.get("") or None
