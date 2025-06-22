# ABOUTME: Prometheus metrics collection and middleware for A2A agents
# ABOUTME: Provides HTTP request metrics, agent performance tracking, and business logic monitoring

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )
    from prometheus_client.metrics import MetricWrapperBase

    PROMETHEUS_AVAILABLE = True
except ImportError:
    # Fallback implementations when prometheus_client is not available
    PROMETHEUS_AVAILABLE = False

    class MetricWrapperBase:
        def __init__(self, *args, **kwargs):
            pass

    class Counter(MetricWrapperBase):
        def __init__(self, *args, **kwargs):
            self._value = 0

        def inc(self, amount=1):
            self._value += amount

        def labels(self, **kwargs):
            return self

    class Histogram(MetricWrapperBase):
        def __init__(self, *args, **kwargs):
            self._count = 0
            self._sum = 0

        def observe(self, amount):
            self._count += 1
            self._sum += amount

        def labels(self, **kwargs):
            return self

        def time(self):
            return self._Timer(self)

        class _Timer:
            def __init__(self, histogram):
                self.histogram = histogram

            def __enter__(self):
                self.start = time.time()
                return self

            def __exit__(self, *args):
                self.histogram.observe(time.time() - self.start)

    class Gauge(MetricWrapperBase):
        def __init__(self, *args, **kwargs):
            self._value = 0

        def set(self, value):
            self._value = value

        def inc(self, amount=1):
            self._value += amount

        def dec(self, amount=1):
            self._value -= amount

        def labels(self, **kwargs):
            return self

    class Info(MetricWrapperBase):
        def __init__(self, *args, **kwargs):
            pass

        def info(self, values):
            pass

        def labels(self, **kwargs):
            return self

    class CollectorRegistry:
        def __init__(self):
            pass

    def generate_latest(*args, **kwargs):
        return b"# Prometheus client not available\n"


from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Container for agent-specific metrics."""

    # HTTP request metrics
    http_requests_total: Counter
    http_request_duration_seconds: Histogram
    http_requests_in_progress: Gauge

    # A2A protocol metrics
    a2a_messages_total: Counter
    a2a_message_duration_seconds: Histogram
    a2a_skill_executions_total: Counter
    a2a_skill_execution_duration_seconds: Histogram

    # Business logic metrics
    business_operations_total: Counter
    business_operation_duration_seconds: Histogram

    # Resource metrics
    agent_memory_usage_bytes: Gauge
    agent_cpu_usage_percent: Gauge
    agent_open_connections: Gauge


class PrometheusMetricsCollector:
    """
    Centralized Prometheus metrics collector for Reddit Technical Watcher.

    Features:
    - HTTP request/response metrics
    - A2A protocol communication metrics
    - Business logic operation metrics
    - Resource usage tracking
    - Custom metric registration
    """

    def __init__(
        self, agent_type: str = "unknown", registry: CollectorRegistry | None = None
    ):
        self.agent_type = agent_type
        self.registry = (
            registry or CollectorRegistry() if PROMETHEUS_AVAILABLE else None
        )

        # Initialize metrics
        self._init_system_metrics()
        self._init_agent_metrics()
        self._init_business_metrics()

        # Performance tracking
        self.active_requests = 0
        self.request_start_times: dict[str, float] = {}

        logger.info(f"Prometheus metrics collector initialized for {agent_type}")

    def _init_system_metrics(self):
        """Initialize system-level metrics."""
        # HTTP metrics
        self.http_requests_total = Counter(
            "reddit_watcher_http_requests_total",
            "Total HTTP requests",
            ["agent_type", "method", "endpoint", "status"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            "reddit_watcher_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["agent_type", "method", "endpoint"],
            registry=self.registry,
            buckets=[
                0.001,
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ],
        )

        self.http_requests_in_progress = Gauge(
            "reddit_watcher_http_requests_in_progress",
            "HTTP requests currently in progress",
            ["agent_type"],
            registry=self.registry,
        )

        # System resource metrics
        self.process_memory_bytes = Gauge(
            "reddit_watcher_process_memory_bytes",
            "Process memory usage in bytes",
            ["agent_type"],
            registry=self.registry,
        )

        self.process_cpu_percent = Gauge(
            "reddit_watcher_process_cpu_percent",
            "Process CPU usage percentage",
            ["agent_type"],
            registry=self.registry,
        )

        self.process_open_connections = Gauge(
            "reddit_watcher_process_open_connections",
            "Number of open network connections",
            ["agent_type"],
            registry=self.registry,
        )

    def _init_agent_metrics(self):
        """Initialize A2A agent-specific metrics."""
        # A2A protocol metrics
        self.a2a_messages_total = Counter(
            "reddit_watcher_a2a_messages_total",
            "Total A2A messages processed",
            ["agent_type", "skill", "status"],
            registry=self.registry,
        )

        self.a2a_message_duration_seconds = Histogram(
            "reddit_watcher_a2a_message_duration_seconds",
            "A2A message processing duration",
            ["agent_type", "skill"],
            registry=self.registry,
            buckets=[
                0.001,
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ],
        )

        self.a2a_skill_executions_total = Counter(
            "reddit_watcher_a2a_skill_executions_total",
            "Total A2A skill executions",
            ["agent_type", "skill", "success"],
            registry=self.registry,
        )

        self.a2a_skill_execution_duration_seconds = Histogram(
            "reddit_watcher_a2a_skill_execution_duration_seconds",
            "A2A skill execution duration",
            ["agent_type", "skill"],
            registry=self.registry,
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )

        # Service discovery metrics
        self.service_discovery_operations_total = Counter(
            "reddit_watcher_service_discovery_operations_total",
            "Total service discovery operations",
            ["agent_type", "operation", "status"],
            registry=self.registry,
        )

        # Circuit breaker metrics
        self.circuit_breaker_state_changes_total = Counter(
            "reddit_watcher_circuit_breaker_state_changes_total",
            "Total circuit breaker state changes",
            ["agent_type", "service", "state"],
            registry=self.registry,
        )

        self.circuit_breaker_state = Gauge(
            "reddit_watcher_circuit_breaker_state",
            "Current circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["agent_type", "service"],
            registry=self.registry,
        )

    def _init_business_metrics(self):
        """Initialize business logic metrics."""
        # Reddit data processing
        self.reddit_posts_processed_total = Counter(
            "reddit_watcher_reddit_posts_processed_total",
            "Total Reddit posts processed",
            ["agent_type", "subreddit"],
            registry=self.registry,
        )

        self.reddit_comments_processed_total = Counter(
            "reddit_watcher_reddit_comments_processed_total",
            "Total Reddit comments processed",
            ["agent_type", "subreddit"],
            registry=self.registry,
        )

        self.reddit_api_requests_total = Counter(
            "reddit_watcher_reddit_api_requests_total",
            "Total Reddit API requests",
            ["agent_type", "endpoint", "status"],
            registry=self.registry,
        )

        self.reddit_api_rate_limit_exceeded_total = Counter(
            "reddit_watcher_reddit_api_rate_limit_exceeded_total",
            "Total Reddit API rate limit exceeded events",
            ["agent_type"],
            registry=self.registry,
        )

        # Content filtering
        self.content_filter_operations_total = Counter(
            "reddit_watcher_content_filter_operations_total",
            "Total content filtering operations",
            ["agent_type", "result"],
            registry=self.registry,
        )

        self.content_relevance_score = Histogram(
            "reddit_watcher_content_relevance_score",
            "Content relevance scores",
            ["agent_type"],
            registry=self.registry,
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        # Summarization
        self.summarization_operations_total = Counter(
            "reddit_watcher_summarization_operations_total",
            "Total summarization operations",
            ["agent_type", "status"],
            registry=self.registry,
        )

        self.summarization_failures_total = Counter(
            "reddit_watcher_summarization_failures_total",
            "Total summarization failures",
            ["agent_type", "error_type"],
            registry=self.registry,
        )

        self.gemini_api_requests_total = Counter(
            "reddit_watcher_gemini_api_requests_total",
            "Total Gemini API requests",
            ["agent_type", "status"],
            registry=self.registry,
        )

        self.gemini_api_failures_total = Counter(
            "reddit_watcher_gemini_api_failures_total",
            "Total Gemini API failures",
            ["agent_type", "error_type"],
            registry=self.registry,
        )

        # Alert delivery
        self.alert_delivery_operations_total = Counter(
            "reddit_watcher_alert_delivery_operations_total",
            "Total alert delivery operations",
            ["agent_type", "channel", "status"],
            registry=self.registry,
        )

        self.alert_delivery_failures_total = Counter(
            "reddit_watcher_alert_delivery_failures_total",
            "Total alert delivery failures",
            ["agent_type", "channel", "error_type"],
            registry=self.registry,
        )

        self.slack_webhook_requests_total = Counter(
            "reddit_watcher_slack_webhook_requests_total",
            "Total Slack webhook requests",
            ["agent_type", "status"],
            registry=self.registry,
        )

        self.slack_webhook_failures_total = Counter(
            "reddit_watcher_slack_webhook_failures_total",
            "Total Slack webhook failures",
            ["agent_type", "error_type"],
            registry=self.registry,
        )

        # Workflow coordination
        self.workflow_executions_total = Counter(
            "reddit_watcher_workflow_executions_total",
            "Total workflow executions",
            ["agent_type", "status"],
            registry=self.registry,
        )

        self.workflow_duration_seconds = Histogram(
            "reddit_watcher_workflow_duration_seconds",
            "Workflow execution duration",
            ["agent_type"],
            registry=self.registry,
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0],
        )

        self.workflow_last_completion_timestamp = Gauge(
            "reddit_watcher_workflow_last_completion_timestamp",
            "Timestamp of last successful workflow completion",
            ["agent_type"],
            registry=self.registry,
        )

        # Business process metrics
        self.reddit_last_successful_fetch_timestamp = Gauge(
            "reddit_watcher_reddit_last_successful_fetch_timestamp",
            "Timestamp of last successful Reddit data fetch",
            ["agent_type"],
            registry=self.registry,
        )

        # Database metrics
        self.db_connections_active = Gauge(
            "reddit_watcher_db_connections_active",
            "Active database connections",
            ["agent_type"],
            registry=self.registry,
        )

        self.db_connections_max = Gauge(
            "reddit_watcher_db_connections_max",
            "Maximum database connections",
            ["agent_type"],
            registry=self.registry,
        )

        self.db_operations_total = Counter(
            "reddit_watcher_db_operations_total",
            "Total database operations",
            ["agent_type", "operation", "status"],
            registry=self.registry,
        )

        self.db_operation_duration_seconds = Histogram(
            "reddit_watcher_db_operation_duration_seconds",
            "Database operation duration",
            ["agent_type", "operation"],
            registry=self.registry,
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

    def record_http_request(
        self, method: str, endpoint: str, status_code: int, duration: float
    ):
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            agent_type=self.agent_type,
            method=method,
            endpoint=endpoint,
            status=str(status_code),
        ).inc()

        self.http_request_duration_seconds.labels(
            agent_type=self.agent_type, method=method, endpoint=endpoint
        ).observe(duration)

    def record_a2a_skill_execution(
        self, skill_name: str, duration: float, success: bool
    ):
        """Record A2A skill execution metrics."""
        self.a2a_skill_executions_total.labels(
            agent_type=self.agent_type, skill=skill_name, success=str(success).lower()
        ).inc()

        self.a2a_skill_execution_duration_seconds.labels(
            agent_type=self.agent_type, skill=skill_name
        ).observe(duration)

        if success:
            self.a2a_messages_total.labels(
                agent_type=self.agent_type, skill=skill_name, status="success"
            ).inc()
        else:
            self.a2a_messages_total.labels(
                agent_type=self.agent_type, skill=skill_name, status="error"
            ).inc()

    def record_business_operation(
        self, operation: str, duration: float, success: bool, **labels
    ):
        """Record business logic operation metrics."""
        # Update operation-specific metrics based on the operation type
        if operation == "reddit_fetch":
            if success:
                self.reddit_last_successful_fetch_timestamp.labels(
                    agent_type=self.agent_type
                ).set(time.time())
        elif operation == "workflow_execution":
            self.workflow_executions_total.labels(
                agent_type=self.agent_type, status="success" if success else "failure"
            ).inc()

            self.workflow_duration_seconds.labels(agent_type=self.agent_type).observe(
                duration
            )

            if success:
                self.workflow_last_completion_timestamp.labels(
                    agent_type=self.agent_type
                ).set(time.time())

    def update_resource_metrics(
        self, memory_bytes: float, cpu_percent: float, connections: int
    ):
        """Update resource usage metrics."""
        self.process_memory_bytes.labels(agent_type=self.agent_type).set(memory_bytes)
        self.process_cpu_percent.labels(agent_type=self.agent_type).set(cpu_percent)
        self.process_open_connections.labels(agent_type=self.agent_type).set(
            connections
        )

    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus client not available\n"

        return generate_latest(self.registry).decode("utf-8")

    @contextmanager
    def track_operation(self, operation_name: str, **labels):
        """Context manager for tracking operation duration."""
        start_time = time.time()
        success = True

        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            self.record_business_operation(operation_name, duration, success, **labels)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic Prometheus metrics collection.

    Automatically tracks HTTP request metrics including:
    - Request count by method, endpoint, and status
    - Request duration histograms
    - Requests in progress gauge
    """

    def __init__(self, app, metrics_collector: PrometheusMetricsCollector):
        super().__init__(app)
        self.metrics = metrics_collector

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.time()

        # Track request in progress
        self.metrics.http_requests_in_progress.labels(
            agent_type=self.metrics.agent_type
        ).inc()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"Request failed: {e}")
            status_code = 500
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            method = request.method
            endpoint = self._get_endpoint_name(request)

            self.metrics.record_http_request(method, endpoint, status_code, duration)

            # Decrease in-progress counter
            self.metrics.http_requests_in_progress.labels(
                agent_type=self.metrics.agent_type
            ).dec()

        return response

    def _get_endpoint_name(self, request: Request) -> str:
        """Extract endpoint name from request."""
        path = request.url.path

        # Normalize common paths
        if path.startswith("/api/"):
            return path
        elif path == "/":
            return "root"
        elif path == "/health":
            return "health"
        elif path == "/metrics":
            return "metrics"
        elif path == "/.well-known/agent.json":
            return "agent_card"
        else:
            return "other"


# Global metrics collectors for each agent type
_metrics_collectors: dict[str, PrometheusMetricsCollector] = {}


def get_metrics_collector(agent_type: str) -> PrometheusMetricsCollector:
    """Get or create a metrics collector for an agent type."""
    if agent_type not in _metrics_collectors:
        _metrics_collectors[agent_type] = PrometheusMetricsCollector(agent_type)
    return _metrics_collectors[agent_type]


def metrics_decorator(operation_name: str, agent_type: str = "unknown"):
    """Decorator for tracking function execution metrics."""

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                collector = get_metrics_collector(agent_type)
                with collector.track_operation(operation_name):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                collector = get_metrics_collector(agent_type)
                with collector.track_operation(operation_name):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


# Context manager for A2A skill execution tracking
@contextmanager
def track_a2a_skill(agent_type: str, skill_name: str):
    """Context manager for tracking A2A skill execution."""
    collector = get_metrics_collector(agent_type)
    start_time = time.time()
    success = True

    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration = time.time() - start_time
        collector.record_a2a_skill_execution(skill_name, duration, success)


# Convenience functions for common metrics
def record_reddit_fetch(
    agent_type: str, subreddit: str, posts_count: int, comments_count: int
):
    """Record Reddit data fetch metrics."""
    collector = get_metrics_collector(agent_type)
    collector.reddit_posts_processed_total.labels(
        agent_type=agent_type, subreddit=subreddit
    ).inc(posts_count)
    collector.reddit_comments_processed_total.labels(
        agent_type=agent_type, subreddit=subreddit
    ).inc(comments_count)


def record_content_filtering(agent_type: str, total_items: int, relevant_items: int):
    """Record content filtering metrics."""
    collector = get_metrics_collector(agent_type)
    collector.content_filter_operations_total.labels(
        agent_type=agent_type, result="relevant"
    ).inc(relevant_items)
    collector.content_filter_operations_total.labels(
        agent_type=agent_type, result="filtered"
    ).inc(total_items - relevant_items)


def record_summarization(agent_type: str, success: bool, error_type: str | None = None):
    """Record summarization operation metrics."""
    collector = get_metrics_collector(agent_type)
    collector.summarization_operations_total.labels(
        agent_type=agent_type, status="success" if success else "failure"
    ).inc()

    if not success and error_type:
        collector.summarization_failures_total.labels(
            agent_type=agent_type, error_type=error_type
        ).inc()


def record_alert_delivery(
    agent_type: str, channel: str, success: bool, error_type: str | None = None
):
    """Record alert delivery metrics."""
    collector = get_metrics_collector(agent_type)
    collector.alert_delivery_operations_total.labels(
        agent_type=agent_type,
        channel=channel,
        status="success" if success else "failure",
    ).inc()

    if not success and error_type:
        collector.alert_delivery_failures_total.labels(
            agent_type=agent_type, channel=channel, error_type=error_type
        ).inc()


def record_workflow_execution(agent_type: str, duration: float, success: bool):
    """Record workflow execution metrics."""
    collector = get_metrics_collector(agent_type)
    collector.record_business_operation("workflow_execution", duration, success)
