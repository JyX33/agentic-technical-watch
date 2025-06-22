# ABOUTME: Comprehensive health monitoring system for all Reddit Technical Watcher components
# ABOUTME: Provides detailed health checks, service status tracking, and dependency monitoring

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import sqlalchemy
    from sqlalchemy import text

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""

    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceHealth:
    """Complete health status for a service."""

    service_name: str
    overall_status: HealthStatus
    checks: list[HealthCheck] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    uptime_seconds: float = 0.0
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_name": self.service_name,
            "overall_status": self.overall_status.value,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "message": check.message,
                    "duration_ms": check.duration_ms,
                    "last_checked": check.last_checked.isoformat(),
                    "metadata": check.metadata,
                }
                for check in self.checks
            ],
            "last_updated": self.last_updated.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
            "metadata": self.metadata,
        }


class HealthMonitor:
    """
    Comprehensive health monitoring system for Reddit Technical Watcher.

    Features:
    - Individual health checks for dependencies
    - Service health aggregation
    - Periodic health monitoring
    - Health status caching and persistence
    - Dependency health tracking
    - Custom health check registration
    """

    def __init__(self, service_name: str, version: str = "1.0.0"):
        self.service_name = service_name
        self.version = version
        self.start_time = time.time()

        # Health checks registry
        self.health_checks: dict[str, Callable] = {}
        self.health_results: dict[str, HealthCheck] = {}

        # Monitoring configuration
        self.check_interval = 30.0  # seconds
        self.timeout = 10.0  # seconds per check

        # Monitoring task
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        # Dependencies
        self.redis_client: redis.Redis | None = None
        self.database_engine: Any | None = None

        # Register default health checks
        self._register_default_checks()

        logger.info(f"Health monitor initialized for {service_name}")

    def _register_default_checks(self):
        """Register default health checks."""
        self.register_health_check("service_status", self._check_service_status)
        self.register_health_check("memory_usage", self._check_memory_usage)
        self.register_health_check("disk_space", self._check_disk_space)

    def register_health_check(self, name: str, check_func: Callable):
        """Register a custom health check function."""
        self.health_checks[name] = check_func
        logger.debug(f"Registered health check: {name}")

    def register_redis_client(self, redis_client: redis.Redis):
        """Register Redis client for health monitoring."""
        if REDIS_AVAILABLE:
            self.redis_client = redis_client
            self.register_health_check(
                "redis_connectivity", self._check_redis_connectivity
            )
            logger.debug("Redis health check registered")

    def register_database_engine(self, engine: Any):
        """Register database engine for health monitoring."""
        if SQLALCHEMY_AVAILABLE:
            self.database_engine = engine
            self.register_health_check(
                "database_connectivity", self._check_database_connectivity
            )
            logger.debug("Database health check registered")

    async def _check_service_status(self) -> HealthCheck:
        """Check basic service status."""
        start_time = time.time()

        try:
            uptime = time.time() - self.start_time
            status = HealthStatus.HEALTHY
            message = f"Service running for {uptime:.1f} seconds"

            return HealthCheck(
                name="service_status",
                status=status,
                message=message,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"uptime_seconds": uptime},
            )
        except Exception as e:
            return HealthCheck(
                name="service_status",
                status=HealthStatus.UNHEALTHY,
                message=f"Service status check failed: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _check_memory_usage(self) -> HealthCheck:
        """Check memory usage."""
        start_time = time.time()

        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Determine status based on memory usage
            if memory_percent < 80:
                status = HealthStatus.HEALTHY
                message = f"Memory usage: {memory_percent:.1f}%"
            elif memory_percent < 95:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {memory_percent:.1f}%"

            return HealthCheck(
                name="memory_usage",
                status=status,
                message=message,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={
                    "memory_percent": memory_percent,
                    "memory_rss_mb": memory_info.rss / (1024 * 1024),
                    "memory_vms_mb": memory_info.vms / (1024 * 1024),
                },
            )
        except ImportError:
            return HealthCheck(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                message="psutil not available for memory monitoring",
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheck(
                name="memory_usage",
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _check_disk_space(self) -> HealthCheck:
        """Check disk space usage."""
        start_time = time.time()

        try:
            import psutil

            disk_usage = psutil.disk_usage("/")
            usage_percent = (disk_usage.used / disk_usage.total) * 100

            # Determine status based on disk usage
            if usage_percent < 80:
                status = HealthStatus.HEALTHY
                message = f"Disk usage: {usage_percent:.1f}%"
            elif usage_percent < 95:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {usage_percent:.1f}%"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {usage_percent:.1f}%"

            return HealthCheck(
                name="disk_space",
                status=status,
                message=message,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={
                    "disk_usage_percent": usage_percent,
                    "disk_total_gb": disk_usage.total / (1024**3),
                    "disk_used_gb": disk_usage.used / (1024**3),
                    "disk_free_gb": disk_usage.free / (1024**3),
                },
            )
        except ImportError:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message="psutil not available for disk monitoring",
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=f"Disk check failed: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _check_redis_connectivity(self) -> HealthCheck:
        """Check Redis connectivity."""
        start_time = time.time()

        if not self.redis_client:
            return HealthCheck(
                name="redis_connectivity",
                status=HealthStatus.UNKNOWN,
                message="Redis client not configured",
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Test Redis connection with ping
            result = await asyncio.wait_for(
                self.redis_client.ping(), timeout=self.timeout
            )

            if result:
                # Get Redis info for additional metadata
                info = await self.redis_client.info()

                return HealthCheck(
                    name="redis_connectivity",
                    status=HealthStatus.HEALTHY,
                    message="Redis connection healthy",
                    duration_ms=(time.time() - start_time) * 1000,
                    metadata={
                        "redis_version": info.get("redis_version", "unknown"),
                        "connected_clients": info.get("connected_clients", 0),
                        "used_memory_human": info.get("used_memory_human", "unknown"),
                    },
                )
            else:
                return HealthCheck(
                    name="redis_connectivity",
                    status=HealthStatus.UNHEALTHY,
                    message="Redis ping failed",
                    duration_ms=(time.time() - start_time) * 1000,
                )
        except TimeoutError:
            return HealthCheck(
                name="redis_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection timeout ({self.timeout}s)",
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheck(
                name="redis_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _check_database_connectivity(self) -> HealthCheck:
        """Check database connectivity."""
        start_time = time.time()

        if not self.database_engine:
            return HealthCheck(
                name="database_connectivity",
                status=HealthStatus.UNKNOWN,
                message="Database engine not configured",
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Test database connection with a simple query
            async with self.database_engine.begin() as conn:
                result = await asyncio.wait_for(
                    conn.execute(text("SELECT 1")), timeout=self.timeout
                )

                # Get connection pool info if available
                pool_info = {}
                if hasattr(self.database_engine.pool, "size"):
                    pool_info = {
                        "pool_size": self.database_engine.pool.size(),
                        "checked_in": self.database_engine.pool.checkedin(),
                        "checked_out": self.database_engine.pool.checkedout(),
                        "overflow": self.database_engine.pool.overflow(),
                        "total_connections": self.database_engine.pool.size()
                        + self.database_engine.pool.overflow(),
                    }

                return HealthCheck(
                    name="database_connectivity",
                    status=HealthStatus.HEALTHY,
                    message="Database connection healthy",
                    duration_ms=(time.time() - start_time) * 1000,
                    metadata=pool_info,
                )
        except TimeoutError:
            return HealthCheck(
                name="database_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection timeout ({self.timeout}s)",
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheck(
                name="database_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def run_health_check(self, check_name: str) -> HealthCheck:
        """Run a specific health check."""
        if check_name not in self.health_checks:
            return HealthCheck(
                name=check_name,
                status=HealthStatus.UNKNOWN,
                message=f"Health check '{check_name}' not found",
            )

        try:
            check_func = self.health_checks[check_name]
            result = await asyncio.wait_for(check_func(), timeout=self.timeout)
            self.health_results[check_name] = result
            return result
        except TimeoutError:
            result = HealthCheck(
                name=check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check '{check_name}' timed out ({self.timeout}s)",
            )
            self.health_results[check_name] = result
            return result
        except Exception as e:
            result = HealthCheck(
                name=check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check '{check_name}' failed: {e}",
            )
            self.health_results[check_name] = result
            return result

    async def run_all_health_checks(self) -> list[HealthCheck]:
        """Run all registered health checks."""
        tasks = [
            self.run_health_check(check_name)
            for check_name in self.health_checks.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions in results
        health_checks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_name = list(self.health_checks.keys())[i]
                health_checks.append(
                    HealthCheck(
                        name=check_name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check failed: {result}",
                    )
                )
            else:
                health_checks.append(result)

        return health_checks

    def get_service_health(self) -> ServiceHealth:
        """Get comprehensive service health status."""
        # Run recent health checks
        checks = list(self.health_results.values())

        # Determine overall status
        if not checks:
            overall_status = HealthStatus.UNKNOWN
        elif all(check.status == HealthStatus.HEALTHY for check in checks):
            overall_status = HealthStatus.HEALTHY
        elif any(check.status == HealthStatus.UNHEALTHY for check in checks):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED

        return ServiceHealth(
            service_name=self.service_name,
            overall_status=overall_status,
            checks=checks,
            uptime_seconds=time.time() - self.start_time,
            version=self.version,
            metadata={
                "total_checks": len(checks),
                "healthy_checks": len(
                    [c for c in checks if c.status == HealthStatus.HEALTHY]
                ),
                "degraded_checks": len(
                    [c for c in checks if c.status == HealthStatus.DEGRADED]
                ),
                "unhealthy_checks": len(
                    [c for c in checks if c.status == HealthStatus.UNHEALTHY]
                ),
                "unknown_checks": len(
                    [c for c in checks if c.status == HealthStatus.UNKNOWN]
                ),
            },
        )

    async def start_monitoring(self):
        """Start periodic health monitoring."""
        if self._is_monitoring:
            logger.warning("Health monitoring already started")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Health monitoring started (interval: {self.check_interval}s)")

    async def stop_monitoring(self):
        """Stop periodic health monitoring."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Health monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop that runs health checks periodically."""
        logger.info("Health monitoring loop started")

        while self._is_monitoring:
            try:
                # Run all health checks
                await self.run_all_health_checks()

                # Log summary
                health = self.get_service_health()
                logger.debug(
                    f"Health check completed: {health.overall_status.value} "
                    f"({health.metadata['healthy_checks']}/{health.metadata['total_checks']} healthy)"
                )

                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)


class AgentHealthRegistry:
    """
    Registry for tracking health status of all agents in the system.

    Provides centralized health monitoring and cross-agent dependency tracking.
    """

    def __init__(self):
        self.agent_monitors: dict[str, HealthMonitor] = {}
        self.logger = logging.getLogger(f"{__name__}.registry")

    def register_agent(self, agent_type: str, monitor: HealthMonitor):
        """Register an agent's health monitor."""
        self.agent_monitors[agent_type] = monitor
        self.logger.info(f"Registered health monitor for {agent_type}")

    def get_agent_health(self, agent_type: str) -> ServiceHealth | None:
        """Get health status for a specific agent."""
        monitor = self.agent_monitors.get(agent_type)
        if monitor:
            return monitor.get_service_health()
        return None

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health status."""
        agent_health = {}
        overall_healthy = True
        total_checks = 0
        healthy_checks = 0

        for agent_type, monitor in self.agent_monitors.items():
            health = monitor.get_service_health()
            agent_health[agent_type] = health.to_dict()

            if health.overall_status != HealthStatus.HEALTHY:
                overall_healthy = False

            total_checks += health.metadata.get("total_checks", 0)
            healthy_checks += health.metadata.get("healthy_checks", 0)

        return {
            "system_status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.now(UTC).isoformat(),
            "agents": agent_health,
            "summary": {
                "total_agents": len(self.agent_monitors),
                "healthy_agents": len(
                    [
                        h
                        for h in agent_health.values()
                        if h["overall_status"] == "healthy"
                    ]
                ),
                "total_checks": total_checks,
                "healthy_checks": healthy_checks,
                "health_percentage": (healthy_checks / total_checks * 100)
                if total_checks > 0
                else 0,
            },
        }

    async def check_agent_dependencies(
        self, agent_type: str
    ) -> dict[str, HealthStatus]:
        """Check dependencies for a specific agent."""
        dependencies = {
            "coordinator": ["redis", "database"],
            "retrieval": ["reddit_api", "database"],
            "filter": ["database"],
            "summarise": ["gemini_api", "database"],
            "alert": ["slack_webhook", "smtp", "database"],
        }

        agent_deps = dependencies.get(agent_type, [])
        dependency_status = {}

        for dep in agent_deps:
            # This would check external dependencies
            # For now, return unknown status
            dependency_status[dep] = HealthStatus.UNKNOWN

        return dependency_status


# Global health registry
_health_registry = AgentHealthRegistry()


def get_health_registry() -> AgentHealthRegistry:
    """Get the global health registry."""
    return _health_registry


def create_health_monitor(service_name: str, version: str = "1.0.0") -> HealthMonitor:
    """Create and register a health monitor for a service."""
    monitor = HealthMonitor(service_name, version)
    _health_registry.register_agent(service_name, monitor)
    return monitor
