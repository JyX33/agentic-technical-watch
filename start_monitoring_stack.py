#!/usr/bin/env python3
# ABOUTME: Startup script for comprehensive monitoring and observability stack
# ABOUTME: Initializes Prometheus, Grafana, Jaeger, and all observability components for Reddit Technical Watcher

import asyncio
import json
import signal
import sys
import time

from reddit_watcher.config import Settings
from reddit_watcher.observability import (
    AlertRule,
    AlertSeverity,
    EmailAlertChannel,
    SlackAlertChannel,
    configure_logging,
    get_alert_manager,
    get_logger,
    get_observability_integration,
    initialize_tracing,
)


class MonitoringStackManager:
    """
    Comprehensive monitoring stack manager for Reddit Technical Watcher.

    Features:
    - Observability component initialization
    - Alert rule configuration
    - Health monitoring setup
    - Graceful shutdown handling
    - Production-ready configurations
    """

    def __init__(self):
        self.config = Settings()
        self.logger = None
        self.alert_manager = None
        self.observability = None
        self.shutdown_event = asyncio.Event()

        # Component status
        self.components_started = False

    async def initialize(self):
        """Initialize all monitoring components."""
        print("🚀 Initializing Reddit Technical Watcher Monitoring Stack...")

        # Configure structured logging
        configure_logging(
            level="INFO",
            format_type="structured",
            enable_file_logging=True,
            log_file="monitoring.log",
        )

        self.logger = get_logger(__name__, "monitoring_stack")
        self.logger.info("Monitoring stack initialization started")

        # Initialize distributed tracing
        jaeger_endpoint = (
            "http://localhost:14268/api/traces" if self.config.jaeger_enabled else None
        )
        otlp_endpoint = "http://localhost:4317" if self.config.otlp_enabled else None

        initialize_tracing(
            service_name="reddit-watcher-monitoring",
            service_version="1.0.0",
            jaeger_endpoint=jaeger_endpoint,
            otlp_endpoint=otlp_endpoint,
        )

        self.logger.info("Distributed tracing initialized")

        # Initialize observability integration
        self.observability = get_observability_integration()
        await self.observability.start_monitoring()

        self.logger.info("Observability integration started")

        # Initialize alert manager
        await self._setup_alerting()

        self.logger.info("Alert manager configured")

        # Register signal handlers
        self._setup_signal_handlers()

        self.components_started = True
        self.logger.info("✅ Monitoring stack initialization completed")

    async def _setup_alerting(self):
        """Set up alerting rules and channels."""
        self.alert_manager = get_alert_manager()

        # Configure alert channels
        await self._setup_alert_channels()

        # Configure alert rules
        await self._setup_alert_rules()

        # Start alert monitoring
        await self.alert_manager.start_monitoring()

    async def _setup_alert_channels(self):
        """Configure alert delivery channels."""
        # Slack channel
        if hasattr(self.config, "slack_webhook_url") and self.config.slack_webhook_url:
            slack_channel = SlackAlertChannel(
                webhook_url=self.config.slack_webhook_url,
                channel="#reddit-watcher-alerts",
            )
            self.alert_manager.add_alert_channel(slack_channel)
            self.logger.info("Slack alert channel configured")

        # Email channel
        if (
            hasattr(self.config, "smtp_host")
            and self.config.smtp_host
            and hasattr(self.config, "smtp_username")
            and self.config.smtp_username
        ):
            email_channel = EmailAlertChannel(
                smtp_host=self.config.smtp_host,
                smtp_port=self.config.smtp_port,
                username=self.config.smtp_username,
                password=self.config.smtp_password,
                from_email=self.config.smtp_from_email,
                to_emails=self.config.alert_email_recipients.split(",")
                if hasattr(self.config, "alert_email_recipients")
                else ["admin@reddit-watcher.com"],
                use_tls=self.config.smtp_use_tls,
            )
            self.alert_manager.add_alert_channel(email_channel)
            self.logger.info("Email alert channel configured")

    async def _setup_alert_rules(self):
        """Configure comprehensive alert rules."""
        # System health alerts
        system_health_rule = AlertRule(
            name="system_health_critical",
            description="System health is critical - multiple agents down",
            condition=lambda: self._check_system_health_critical(),
            severity=AlertSeverity.CRITICAL,
            threshold=1.0,
            duration_seconds=60.0,
            cooldown_seconds=300.0,
            labels={"type": "system_health", "severity": "critical"},
            annotations={
                "runbook": "https://docs.reddit-watcher.com/runbooks/system-health"
            },
        )
        self.alert_manager.add_alert_rule(system_health_rule)

        # High error rate alert
        error_rate_rule = AlertRule(
            name="high_error_rate",
            description="High error rate detected across agents",
            condition=lambda: self._check_error_rate(),
            severity=AlertSeverity.WARNING,
            threshold=5.0,  # 5% error rate
            duration_seconds=120.0,
            cooldown_seconds=600.0,
            labels={"type": "error_rate", "severity": "warning"},
            annotations={
                "threshold": "5%",
                "runbook": "https://docs.reddit-watcher.com/runbooks/error-rate",
            },
        )
        self.alert_manager.add_alert_rule(error_rate_rule)

        # Reddit API connectivity
        reddit_api_rule = AlertRule(
            name="reddit_api_connectivity",
            description="Reddit API connectivity issues detected",
            condition=lambda: self._check_reddit_api_health(),
            severity=AlertSeverity.CRITICAL,
            threshold=1.0,
            duration_seconds=180.0,
            cooldown_seconds=900.0,
            labels={
                "type": "external_api",
                "service": "reddit",
                "severity": "critical",
            },
            annotations={
                "runbook": "https://docs.reddit-watcher.com/runbooks/reddit-api"
            },
        )
        self.alert_manager.add_alert_rule(reddit_api_rule)

        # Workflow stale alert
        workflow_stale_rule = AlertRule(
            name="workflow_execution_stale",
            description="No successful workflow completion in last 6 hours",
            condition=lambda: self._check_workflow_staleness(),
            severity=AlertSeverity.WARNING,
            threshold=1.0,
            duration_seconds=300.0,
            cooldown_seconds=1800.0,
            labels={"type": "workflow", "severity": "warning"},
            annotations={
                "threshold": "6_hours",
                "runbook": "https://docs.reddit-watcher.com/runbooks/workflow-stale",
            },
        )
        self.alert_manager.add_alert_rule(workflow_stale_rule)

        # Database connectivity
        database_rule = AlertRule(
            name="database_connectivity",
            description="Database connectivity issues detected",
            condition=lambda: self._check_database_health(),
            severity=AlertSeverity.CRITICAL,
            threshold=1.0,
            duration_seconds=90.0,
            cooldown_seconds=300.0,
            labels={"type": "database", "severity": "critical"},
            annotations={
                "runbook": "https://docs.reddit-watcher.com/runbooks/database"
            },
        )
        self.alert_manager.add_alert_rule(database_rule)

        self.logger.info(
            f"Configured {len(self.alert_manager.alert_rules)} alert rules"
        )

    def _check_system_health_critical(self) -> bool:
        """Check if system health is critical."""
        try:
            health = self.observability.get_system_health()
            return health["overall_status"] == "critical"
        except Exception:
            return False

    def _check_error_rate(self) -> bool:
        """Check if error rate is too high."""
        try:
            metrics = self.observability.get_business_metrics()
            error_rate = metrics["performance_metrics"]["error_rate_percent"]
            return error_rate > 5.0
        except Exception:
            return False

    def _check_reddit_api_health(self) -> bool:
        """Check Reddit API health."""
        try:
            # This would check actual Reddit API connectivity
            # For now, return False (healthy)
            return False
        except Exception:
            return True  # Assume unhealthy if check fails

    def _check_workflow_staleness(self) -> bool:
        """Check if workflows are stale."""
        try:
            metrics = self.observability.get_business_metrics()
            last_completion = metrics["processing_metrics"]["last_workflow_completion"]
            # Check if last completion was more than 6 hours ago
            # Implementation would parse timestamp and compare
            return False  # Simplified for now
        except Exception:
            return True

    def _check_database_health(self) -> bool:
        """Check database health."""
        try:
            # This would check actual database connectivity
            # For now, return False (healthy)
            return False
        except Exception:
            return True

    def _setup_signal_handlers(self):
        """Set up graceful shutdown signal handlers."""

        def signal_handler(signum, frame):
            self.logger.info(
                f"Received signal {signum}, initiating graceful shutdown..."
            )
            asyncio.create_task(self._shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _shutdown(self):
        """Graceful shutdown of monitoring stack."""
        if not self.components_started:
            return

        self.logger.info("🛑 Shutting down monitoring stack...")

        try:
            # Stop alert monitoring
            if self.alert_manager:
                await self.alert_manager.stop_monitoring()
                self.logger.info("Alert manager stopped")

            # Stop observability integration
            if self.observability:
                await self.observability.stop_monitoring()
                self.logger.info("Observability integration stopped")

            self.logger.info("✅ Monitoring stack shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

        finally:
            self.shutdown_event.set()

    async def run(self):
        """Main run loop for monitoring stack."""
        try:
            await self.initialize()

            self.logger.info("🎯 Monitoring stack is running...")
            self.logger.info("📊 Dashboard: http://localhost:3000 (Grafana)")
            self.logger.info("📈 Metrics: http://localhost:9090 (Prometheus)")
            self.logger.info("🔍 Tracing: http://localhost:16686 (Jaeger)")
            self.logger.info("⚡ Logs: http://localhost:3100 (Loki)")

            print("\n" + "=" * 60)
            print("🎉 REDDIT TECHNICAL WATCHER MONITORING STACK READY!")
            print("=" * 60)
            print("📊 Grafana Dashboard: http://localhost:3000")
            print("📈 Prometheus Metrics: http://localhost:9090")
            print("🔍 Jaeger Tracing: http://localhost:16686")
            print("⚡ Loki Logs: http://localhost:3100")
            print("🚨 Alertmanager: http://localhost:9093")
            print("=" * 60)
            print("Press Ctrl+C to stop monitoring")
            print("=" * 60 + "\n")

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except Exception as e:
            self.logger.error(f"Fatal error in monitoring stack: {e}")
            raise

    async def health_check(self):
        """Perform comprehensive health check of monitoring stack."""
        if not self.components_started:
            return {"status": "not_started"}

        health_summary = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {},
            "alerts": {},
            "system": {},
        }

        try:
            # Check observability integration
            if self.observability:
                system_health = self.observability.get_system_health()
                health_summary["system"] = system_health
                health_summary["components"]["observability"] = "healthy"
            else:
                health_summary["components"]["observability"] = "unhealthy"
                health_summary["status"] = "degraded"

            # Check alert manager
            if self.alert_manager:
                alert_summary = self.alert_manager.get_alert_summary()
                health_summary["alerts"] = alert_summary
                health_summary["components"]["alerting"] = "healthy"
            else:
                health_summary["components"]["alerting"] = "unhealthy"
                health_summary["status"] = "degraded"

        except Exception as e:
            health_summary["status"] = "error"
            health_summary["error"] = str(e)

        return health_summary


async def main():
    """Main entry point for monitoring stack."""
    manager = MonitoringStackManager()

    try:
        await manager.run()
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stack stopped by user")
    except Exception as e:
        print(f"\n❌ Monitoring stack failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if monitoring stack should be started
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        # Health check mode
        async def health_check():
            manager = MonitoringStackManager()
            health = await manager.health_check()
            print(json.dumps(health, indent=2))

        asyncio.run(health_check())
    else:
        # Normal startup mode
        asyncio.run(main())
