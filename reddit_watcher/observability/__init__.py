# ABOUTME: Observability and monitoring infrastructure for Reddit Technical Watcher
# ABOUTME: Provides metrics collection, health monitoring, and structured logging across all components

from .alerting import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    EmailAlertChannel,
    SlackAlertChannel,
    create_health_alert_rule,
    create_metric_threshold_alert_rule,
    get_alert_manager,
)
from .health import (
    HealthMonitor,
    HealthStatus,
    create_health_monitor,
    get_health_registry,
)
from .integration import (
    ObservabilityIntegration,
    get_observability_integration,
    record_alert_sent,
    record_reddit_post_processed,
    record_workflow_completed,
    setup_observability_endpoints,
)
from .logging import (
    CorrelationLogger,
    LoggingManager,
    LoggingMiddleware,
    configure_logging,
    get_logger,
    log_operation,
    log_performance,
    request_context,
    set_request_context,
)
from .metrics import (
    PrometheusMetricsCollector,
    PrometheusMiddleware,
    get_metrics_collector,
    metrics_decorator,
    record_alert_delivery,
    record_content_filtering,
    record_reddit_fetch,
    record_summarization,
    record_workflow_execution,
    track_a2a_skill,
)
from .tracing import (
    SpanKind,
    TracingProvider,
    async_trace_context,
    get_current_span_id,
    get_current_trace_id,
    get_tracing_provider,
    initialize_tracing,
    trace_a2a_communication,
    trace_context,
    trace_operation,
)

__all__ = [
    # Alerting
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "EmailAlertChannel",
    "SlackAlertChannel",
    "create_health_alert_rule",
    "create_metric_threshold_alert_rule",
    "get_alert_manager",
    # Health monitoring
    "HealthMonitor",
    "HealthStatus",
    "create_health_monitor",
    "get_health_registry",
    # Integration
    "ObservabilityIntegration",
    "get_observability_integration",
    "record_alert_sent",
    "record_reddit_post_processed",
    "record_workflow_completed",
    "setup_observability_endpoints",
    # Logging
    "CorrelationLogger",
    "LoggingManager",
    "LoggingMiddleware",
    "configure_logging",
    "get_logger",
    "log_operation",
    "log_performance",
    "request_context",
    "set_request_context",
    # Metrics
    "PrometheusMetricsCollector",
    "PrometheusMiddleware",
    "get_metrics_collector",
    "metrics_decorator",
    "record_alert_delivery",
    "record_content_filtering",
    "record_reddit_fetch",
    "record_summarization",
    "record_workflow_execution",
    "track_a2a_skill",
    # Tracing
    "SpanKind",
    "TracingProvider",
    "async_trace_context",
    "get_current_span_id",
    "get_current_trace_id",
    "get_tracing_provider",
    "initialize_tracing",
    "trace_a2a_communication",
    "trace_context",
    "trace_operation",
]
