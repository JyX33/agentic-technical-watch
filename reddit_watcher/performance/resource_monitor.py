# ABOUTME: System resource monitoring and performance metrics collection
# ABOUTME: Provides CPU, memory, network, and database performance monitoring for production optimization

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available - resource monitoring will be limited")

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """System resource metrics at a point in time."""

    timestamp: float
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_usage_percent: float = 0.0
    disk_free_gb: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    open_files: int = 0
    active_connections: int = 0
    process_count: int = 0


@dataclass
class PerformanceMetrics:
    """Performance metrics for specific operations."""

    operation_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Metrics specific to A2A agent performance."""

    agent_type: str
    skill_name: str
    execution_time: float
    success: bool
    memory_usage_mb: float
    cpu_usage_percent: float
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ResourceMonitor:
    """
    System resource monitoring with performance metrics collection.

    Features:
    - Real-time system resource monitoring
    - Performance metrics collection
    - Agent-specific metrics tracking
    - Historical data retention
    - Alerting thresholds
    - Export capabilities
    """

    def __init__(
        self,
        history_size: int = 1000,
        collection_interval: float = 5.0,
        alert_thresholds: dict[str, float] | None = None,
    ):
        self.history_size = history_size
        self.collection_interval = collection_interval
        self.alert_thresholds = alert_thresholds or {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_usage_percent": 90.0,
        }

        # Historical data storage
        self.resource_history: deque = deque(maxlen=history_size)
        self.performance_history: deque = deque(maxlen=history_size)
        self.agent_metrics: deque = deque(maxlen=history_size)

        # Real-time metrics
        self.current_metrics: ResourceMetrics | None = None
        self.alert_callbacks: list[Callable] = []

        # Monitoring state
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        # Performance tracking
        self.operation_counters = defaultdict(int)
        self.error_counters = defaultdict(int)

        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available - resource monitoring will be limited")

    def add_alert_callback(self, callback: Callable[[str, float, float], None]):
        """Add a callback for resource alerts."""
        self.alert_callbacks.append(callback)

    def _collect_system_metrics(self) -> ResourceMetrics:
        """Collect current system resource metrics."""
        timestamp = time.time()

        if not PSUTIL_AVAILABLE:
            return ResourceMetrics(timestamp=timestamp)

        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)

            # Disk metrics
            disk = psutil.disk_usage("/")
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024 * 1024 * 1024)

            # Network metrics
            net_io = psutil.net_io_counters()
            network_bytes_sent = net_io.bytes_sent
            network_bytes_recv = net_io.bytes_recv

            # Process metrics
            process = psutil.Process(os.getpid())
            open_files = len(process.open_files())
            active_connections = len(process.connections())
            process_count = len(psutil.pids())

            return ResourceMetrics(
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                open_files=open_files,
                active_connections=active_connections,
                process_count=process_count,
            )

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return ResourceMetrics(timestamp=timestamp)

    def _check_alerts(self, metrics: ResourceMetrics):
        """Check if any metrics exceed alert thresholds."""
        alerts = []

        for metric_name, threshold in self.alert_thresholds.items():
            if hasattr(metrics, metric_name):
                value = getattr(metrics, metric_name)
                if value > threshold:
                    alerts.append((metric_name, value, threshold))

        for alert in alerts:
            metric_name, value, threshold = alert
            logger.warning(
                f"Resource alert: {metric_name} = {value:.1f} "
                f"(threshold: {threshold:.1f})"
            )

            for callback in self.alert_callbacks:
                try:
                    callback(metric_name, value, threshold)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

    async def _monitoring_loop(self):
        """Main monitoring loop that collects metrics periodically."""
        logger.info(
            f"Starting resource monitoring (interval: {self.collection_interval}s)"
        )

        while self._is_monitoring:
            try:
                # Collect current metrics
                metrics = self._collect_system_metrics()
                self.current_metrics = metrics
                self.resource_history.append(metrics)

                # Check for alerts
                self._check_alerts(metrics)

                # Log metrics periodically (every 10 collections)
                if len(self.resource_history) % 10 == 0:
                    logger.debug(
                        f"System metrics: CPU={metrics.cpu_percent:.1f}%, "
                        f"Memory={metrics.memory_percent:.1f}%, "
                        f"Disk={metrics.disk_usage_percent:.1f}%"
                    )

                await asyncio.sleep(self.collection_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.collection_interval)

    async def start_monitoring(self):
        """Start resource monitoring."""
        if self._is_monitoring:
            logger.warning("Resource monitoring already started")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Resource monitoring started")

    async def stop_monitoring(self):
        """Stop resource monitoring."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Resource monitoring stopped")

    def record_performance(
        self,
        operation_name: str,
        start_time: float,
        end_time: float,
        success: bool,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Record performance metrics for an operation."""
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
        )

        self.performance_history.append(metrics)
        self.operation_counters[operation_name] += 1

        if not success:
            self.error_counters[operation_name] += 1

        logger.debug(
            f"Performance recorded: {operation_name} "
            f"({metrics.duration:.3f}s, success={success})"
        )

    def record_agent_metrics(
        self,
        agent_type: str,
        skill_name: str,
        execution_time: float,
        success: bool,
        memory_usage_mb: float = 0.0,
        cpu_usage_percent: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ):
        """Record agent-specific performance metrics."""
        metrics = AgentMetrics(
            agent_type=agent_type,
            skill_name=skill_name,
            execution_time=execution_time,
            success=success,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self.agent_metrics.append(metrics)

        logger.debug(
            f"Agent metrics recorded: {agent_type}.{skill_name} "
            f"({execution_time:.3f}s, success={success})"
        )

    def get_current_metrics(self) -> ResourceMetrics | None:
        """Get the most recent resource metrics."""
        return self.current_metrics

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary statistics."""
        if not self.performance_history:
            return {}

        # Calculate averages and success rates
        operation_stats = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0.0,
                "success_count": 0,
                "avg_duration": 0.0,
                "success_rate": 0.0,
            }
        )

        for metrics in self.performance_history:
            stats = operation_stats[metrics.operation_name]
            stats["count"] += 1
            stats["total_duration"] += metrics.duration
            if metrics.success:
                stats["success_count"] += 1

        # Calculate derived metrics
        for stats in operation_stats.values():
            stats["avg_duration"] = stats["total_duration"] / stats["count"]
            stats["success_rate"] = stats["success_count"] / stats["count"]

        return dict(operation_stats)

    def get_agent_performance_summary(self) -> dict[str, Any]:
        """Get agent performance summary statistics."""
        if not self.agent_metrics:
            return {}

        # Group by agent type and skill
        agent_stats = defaultdict(
            lambda: defaultdict(
                lambda: {
                    "count": 0,
                    "total_execution_time": 0.0,
                    "success_count": 0,
                    "avg_execution_time": 0.0,
                    "success_rate": 0.0,
                    "avg_memory_mb": 0.0,
                    "avg_cpu_percent": 0.0,
                }
            )
        )

        for metrics in self.agent_metrics:
            stats = agent_stats[metrics.agent_type][metrics.skill_name]
            stats["count"] += 1
            stats["total_execution_time"] += metrics.execution_time
            stats["avg_memory_mb"] += metrics.memory_usage_mb
            stats["avg_cpu_percent"] += metrics.cpu_usage_percent
            if metrics.success:
                stats["success_count"] += 1

        # Calculate derived metrics
        for agent_type, skills in agent_stats.items():
            for skill_name, stats in skills.items():
                stats["avg_execution_time"] = (
                    stats["total_execution_time"] / stats["count"]
                )
                stats["success_rate"] = stats["success_count"] / stats["count"]
                stats["avg_memory_mb"] /= stats["count"]
                stats["avg_cpu_percent"] /= stats["count"]

        return dict(agent_stats)

    def get_resource_averages(self, last_n: int | None = None) -> dict[str, float]:
        """Get average resource usage over recent history."""
        if not self.resource_history:
            return {}

        history = list(self.resource_history)
        if last_n:
            history = history[-last_n:]

        if not history:
            return {}

        averages = {
            "cpu_percent": sum(m.cpu_percent for m in history) / len(history),
            "memory_percent": sum(m.memory_percent for m in history) / len(history),
            "memory_used_mb": sum(m.memory_used_mb for m in history) / len(history),
            "disk_usage_percent": sum(m.disk_usage_percent for m in history)
            / len(history),
            "open_files": sum(m.open_files for m in history) / len(history),
            "active_connections": sum(m.active_connections for m in history)
            / len(history),
        }

        return averages

    def export_metrics(self, filepath: str, format: str = "json"):
        """Export collected metrics to file."""
        data = {
            "resource_metrics": [
                {
                    "timestamp": m.timestamp,
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "memory_used_mb": m.memory_used_mb,
                    "memory_available_mb": m.memory_available_mb,
                    "disk_usage_percent": m.disk_usage_percent,
                    "disk_free_gb": m.disk_free_gb,
                    "network_bytes_sent": m.network_bytes_sent,
                    "network_bytes_recv": m.network_bytes_recv,
                    "open_files": m.open_files,
                    "active_connections": m.active_connections,
                    "process_count": m.process_count,
                }
                for m in self.resource_history
            ],
            "performance_metrics": [
                {
                    "operation_name": m.operation_name,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "duration": m.duration,
                    "success": m.success,
                    "error_message": m.error_message,
                    "metadata": m.metadata,
                }
                for m in self.performance_history
            ],
            "agent_metrics": [
                {
                    "agent_type": m.agent_type,
                    "skill_name": m.skill_name,
                    "execution_time": m.execution_time,
                    "success": m.success,
                    "memory_usage_mb": m.memory_usage_mb,
                    "cpu_usage_percent": m.cpu_usage_percent,
                    "timestamp": m.timestamp,
                    "metadata": m.metadata,
                }
                for m in self.agent_metrics
            ],
            "summary": {
                "performance": self.get_performance_summary(),
                "agent_performance": self.get_agent_performance_summary(),
                "resource_averages": self.get_resource_averages(),
            },
        }

        if format.lower() == "json":
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        logger.info(f"Metrics exported to {filepath}")


# Global instance
_resource_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


async def initialize_resource_monitoring():
    """Initialize and start resource monitoring."""
    monitor = get_resource_monitor()
    await monitor.start_monitoring()


async def cleanup_resource_monitoring():
    """Cleanup resource monitoring."""
    global _resource_monitor
    if _resource_monitor:
        await _resource_monitor.stop_monitoring()
        _resource_monitor = None


# Context manager for operation timing
class PerformanceTimer:
    """Context manager for timing operations and recording metrics."""

    def __init__(self, operation_name: str, metadata: dict[str, Any] | None = None):
        self.operation_name = operation_name
        self.metadata = metadata or {}
        self.start_time = 0.0
        self.monitor = get_resource_monitor()

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        success = exc_type is None
        error_message = str(exc_val) if exc_val else None

        self.monitor.record_performance(
            self.operation_name,
            self.start_time,
            end_time,
            success,
            error_message,
            self.metadata,
        )
