# ABOUTME: Integration layer for comprehensive observability across all Reddit Technical Watcher components
# ABOUTME: Provides unified monitoring, alerting, and dashboard integration for production operations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from reddit_watcher.observability.health import (
    create_health_monitor,
    get_health_registry,
)
from reddit_watcher.observability.logging import (
    LoggingMiddleware,
    get_logger,
    request_context,
)
from reddit_watcher.observability.metrics import (
    PrometheusMiddleware,
    get_metrics_collector,
)


@dataclass
class SystemMetrics:
    """System-wide metrics aggregation."""

    total_requests: int = 0
    total_errors: int = 0
    average_response_time: float = 0.0
    active_agents: int = 0
    reddit_posts_processed: int = 0
    alerts_sent: int = 0
    last_workflow_completion: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    system_uptime: float = 0.0


@dataclass
class AgentStatus:
    """Individual agent status information."""

    agent_type: str
    status: str
    uptime_seconds: float
    last_heartbeat: datetime
    request_count: int = 0
    error_count: int = 0
    average_response_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ObservabilityIntegration:
    """
    Centralized observability integration for Reddit Technical Watcher.

    Features:
    - Agent health monitoring and aggregation
    - System-wide metrics collection
    - Business metrics tracking
    - Dashboard data provision
    - Alerting integration
    - Performance monitoring
    """

    def __init__(self):
        self.logger = get_logger(__name__, "observability")
        self.start_time = time.time()
        self.agent_statuses: dict[str, AgentStatus] = {}
        self.system_metrics = SystemMetrics()

        # Initialize health monitoring
        self.health_registry = get_health_registry()
        self.health_monitor = create_health_monitor("observability_integration")

        # Metrics tracking
        self.metrics_collectors: dict[str, Any] = {}

    def register_agent(self, agent_type: str, agent_instance: Any = None):
        """Register an agent for monitoring."""
        self.agent_statuses[agent_type] = AgentStatus(
            agent_type=agent_type,
            status="unknown",
            uptime_seconds=0,
            last_heartbeat=datetime.now(UTC),
        )

        # Register metrics collector if available
        if agent_instance and hasattr(agent_instance, "metrics"):
            self.metrics_collectors[agent_type] = agent_instance.metrics

        self.logger.info(f"Registered agent for monitoring: {agent_type}")

    async def update_agent_status(self, agent_type: str, status_data: dict[str, Any]):
        """Update status information for an agent."""
        if agent_type not in self.agent_statuses:
            self.register_agent(agent_type)

        agent_status = self.agent_statuses[agent_type]
        agent_status.status = status_data.get("status", "unknown")
        agent_status.uptime_seconds = status_data.get("uptime_seconds", 0)
        agent_status.last_heartbeat = datetime.now(UTC)
        agent_status.metadata.update(status_data.get("metadata", {}))

        self.logger.debug(
            f"Updated status for agent {agent_type}: {agent_status.status}"
        )

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health status."""
        # Aggregate agent health
        healthy_agents = 0
        total_agents = len(self.agent_statuses)
        agent_health = {}

        for agent_type, status in self.agent_statuses.items():
            agent_health[agent_type] = {
                "status": status.status,
                "uptime_seconds": status.uptime_seconds,
                "last_heartbeat": status.last_heartbeat.isoformat(),
                "request_count": status.request_count,
                "error_count": status.error_count,
                "average_response_time": status.average_response_time,
                "metadata": status.metadata,
            }

            if status.status == "healthy":
                healthy_agents += 1

        # System-wide health determination
        overall_status = "healthy"
        if healthy_agents == 0:
            overall_status = "critical"
        elif healthy_agents < total_agents:
            overall_status = "degraded"

        return {
            "overall_status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "system_uptime": time.time() - self.start_time,
            "agents": {
                "total": total_agents,
                "healthy": healthy_agents,
                "degraded": total_agents - healthy_agents,
                "details": agent_health,
            },
            "metrics": {
                "total_requests": self.system_metrics.total_requests,
                "total_errors": self.system_metrics.total_errors,
                "error_rate": (
                    self.system_metrics.total_errors
                    / max(self.system_metrics.total_requests, 1)
                )
                * 100,
                "average_response_time": self.system_metrics.average_response_time,
                "reddit_posts_processed": self.system_metrics.reddit_posts_processed,
                "alerts_sent": self.system_metrics.alerts_sent,
                "last_workflow_completion": self.system_metrics.last_workflow_completion.isoformat(),
            },
        }

    def get_business_metrics(self) -> dict[str, Any]:
        """Get business-specific metrics for dashboards."""
        # Calculate processing rates
        uptime_hours = (time.time() - self.start_time) / 3600
        posts_per_hour = self.system_metrics.reddit_posts_processed / max(
            uptime_hours, 1
        )
        alerts_per_hour = self.system_metrics.alerts_sent / max(uptime_hours, 1)

        # Calculate availability
        total_possible_requests = len(self.agent_statuses) * max(
            uptime_hours * 60, 1
        )  # 1 per minute per agent
        availability = (
            (total_possible_requests - self.system_metrics.total_errors)
            / max(total_possible_requests, 1)
        ) * 100

        return {
            "processing_metrics": {
                "reddit_posts_processed_total": self.system_metrics.reddit_posts_processed,
                "reddit_posts_per_hour": posts_per_hour,
                "alerts_sent_total": self.system_metrics.alerts_sent,
                "alerts_per_hour": alerts_per_hour,
                "last_workflow_completion": self.system_metrics.last_workflow_completion.isoformat(),
            },
            "performance_metrics": {
                "system_availability_percent": availability,
                "total_requests": self.system_metrics.total_requests,
                "total_errors": self.system_metrics.total_errors,
                "error_rate_percent": (
                    self.system_metrics.total_errors
                    / max(self.system_metrics.total_requests, 1)
                )
                * 100,
                "average_response_time_ms": self.system_metrics.average_response_time,
            },
            "system_metrics": {
                "system_uptime_hours": uptime_hours,
                "active_agents": len(
                    [s for s in self.agent_statuses.values() if s.status == "healthy"]
                ),
                "total_agents": len(self.agent_statuses),
            },
        }

    async def collect_agent_metrics(self):
        """Collect and aggregate metrics from all registered agents."""
        total_requests = 0
        total_errors = 0
        response_times = []

        for _agent_type, collector in self.metrics_collectors.items():
            if hasattr(collector, "http_requests_total"):
                # Aggregate HTTP metrics
                # Note: This is a simplified aggregation - in production,
                # you'd want to use the actual Prometheus metrics
                pass

        # Update system metrics
        self.system_metrics.total_requests = total_requests
        self.system_metrics.total_errors = total_errors

        if response_times:
            self.system_metrics.average_response_time = sum(response_times) / len(
                response_times
            )

    def record_business_event(
        self, event_type: str, count: int = 1, metadata: dict[str, Any] = None
    ):
        """Record business logic events for tracking."""
        if event_type == "reddit_post_processed":
            self.system_metrics.reddit_posts_processed += count
        elif event_type == "alert_sent":
            self.system_metrics.alerts_sent += count
        elif event_type == "workflow_completed":
            self.system_metrics.last_workflow_completion = datetime.now(UTC)

        self.logger.debug(f"Recorded business event: {event_type} (count: {count})")

    async def start_monitoring(self):
        """Start background monitoring tasks."""
        await self.health_monitor.start_monitoring()
        self.logger.info("Observability integration monitoring started")

    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
        await self.health_monitor.stop_monitoring()
        self.logger.info("Observability integration monitoring stopped")


# Global observability integration instance
_observability_integration = ObservabilityIntegration()


def get_observability_integration() -> ObservabilityIntegration:
    """Get the global observability integration instance."""
    return _observability_integration


def setup_observability_endpoints(app: FastAPI, agent_type: str = "unknown"):
    """
    Set up observability endpoints on a FastAPI application.

    Args:
        app: FastAPI application instance
        agent_type: Type of agent for this service
    """
    integration = get_observability_integration()
    metrics_collector = get_metrics_collector(agent_type)
    logger = get_logger("observability.endpoints", agent_type)

    # Add middleware
    app.add_middleware(LoggingMiddleware, agent_type=agent_type)
    app.add_middleware(PrometheusMiddleware, metrics_collector)

    @app.get("/health", response_class=JSONResponse)
    async def health_check():
        """Comprehensive health check endpoint."""
        try:
            with request_context(agent_type=agent_type):
                health_data = integration.get_system_health()

                # Determine HTTP status based on health
                status_code = 200
                if health_data["overall_status"] == "degraded":
                    status_code = 200  # Still serving traffic
                elif health_data["overall_status"] == "critical":
                    status_code = 503  # Service unavailable

                return JSONResponse(
                    content=health_data,
                    status_code=status_code,
                    headers={"Cache-Control": "no-cache"},
                )
        except Exception as e:
            logger.error("Health check failed", error=e)
            return JSONResponse(
                content={"status": "error", "message": str(e)}, status_code=500
            )

    @app.get("/health/live", response_class=JSONResponse)
    async def liveness_check():
        """Simple liveness check for container orchestration."""
        return {"status": "alive", "timestamp": datetime.now(UTC).isoformat()}

    @app.get("/health/ready", response_class=JSONResponse)
    async def readiness_check():
        """Readiness check for container orchestration."""
        # Check critical dependencies
        health_data = integration.get_system_health()

        if health_data["overall_status"] in ["healthy", "degraded"]:
            return {"status": "ready", "timestamp": datetime.now(UTC).isoformat()}
        else:
            return JSONResponse(
                content={
                    "status": "not_ready",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status_code=503,
            )

    @app.get("/metrics", response_class=PlainTextResponse)
    async def prometheus_metrics():
        """Prometheus metrics endpoint."""
        try:
            metrics_text = metrics_collector.get_metrics_text()
            return PlainTextResponse(
                content=metrics_text,
                headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
            )
        except Exception as e:
            logger.error("Failed to generate metrics", error=e)
            return PlainTextResponse(
                content="# Error generating metrics\n", status_code=500
            )

    @app.get("/api/v1/system/health", response_class=JSONResponse)
    async def system_health_api():
        """API endpoint for system health (for external monitoring)."""
        return integration.get_system_health()

    @app.get("/api/v1/system/metrics", response_class=JSONResponse)
    async def system_metrics_api():
        """API endpoint for business metrics (for dashboards)."""
        return integration.get_business_metrics()

    @app.get("/api/v1/agents/status", response_class=JSONResponse)
    async def agents_status_api():
        """API endpoint for agent status information."""
        return {
            "agents": {
                agent_type: {
                    "status": status.status,
                    "uptime_seconds": status.uptime_seconds,
                    "last_heartbeat": status.last_heartbeat.isoformat(),
                    "request_count": status.request_count,
                    "error_count": status.error_count,
                    "average_response_time": status.average_response_time,
                }
                for agent_type, status in integration.agent_statuses.items()
            }
        }

    # Register this agent with the integration
    integration.register_agent(agent_type)
    logger.info(f"Observability endpoints configured for {agent_type} agent")


# Convenience functions for business metrics recording
def record_reddit_post_processed(count: int = 1):
    """Record Reddit post processing event."""
    get_observability_integration().record_business_event(
        "reddit_post_processed", count
    )


def record_alert_sent(count: int = 1):
    """Record alert delivery event."""
    get_observability_integration().record_business_event("alert_sent", count)


def record_workflow_completed():
    """Record workflow completion event."""
    get_observability_integration().record_business_event("workflow_completed")
