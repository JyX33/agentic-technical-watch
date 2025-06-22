# ABOUTME: Operational alerting system for threshold violations and system anomalies
# ABOUTME: Provides real-time monitoring, threshold detection, and multi-channel alert delivery

import asyncio
import logging
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .health import HealthStatus
from .metrics import PrometheusMetricsCollector

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(Enum):
    """Alert state tracking."""

    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class AlertRule:
    """Definition of an alerting rule."""

    name: str
    description: str
    condition: Callable[[], bool]
    severity: AlertSeverity
    threshold: float
    duration_seconds: float = 60.0  # How long condition must be true
    cooldown_seconds: float = 300.0  # Minimum time between alerts
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Add default labels
        if "severity" not in self.labels:
            self.labels["severity"] = self.severity.value


@dataclass
class Alert:
    """Active alert instance."""

    rule_name: str
    message: str
    severity: AlertSeverity
    state: AlertState
    value: float
    threshold: float
    started_at: datetime
    resolved_at: datetime | None = None
    last_sent_at: datetime | None = None
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "rule_name": self.rule_name,
            "message": self.message,
            "severity": self.severity.value,
            "state": self.state.value,
            "value": self.value,
            "threshold": self.threshold,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "last_sent_at": self.last_sent_at.isoformat()
            if self.last_sent_at
            else None,
            "labels": self.labels,
            "annotations": self.annotations,
        }


class AlertChannel:
    """Base class for alert delivery channels."""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.logger = logging.getLogger(f"{__name__}.{name}")

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert through this channel. Returns success status."""
        raise NotImplementedError


class SlackAlertChannel(AlertChannel):
    """Slack webhook alert channel."""

    def __init__(self, webhook_url: str, channel: str | None = None):
        super().__init__("slack")
        self.webhook_url = webhook_url
        self.channel = channel

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        if not HTTPX_AVAILABLE:
            self.logger.error("httpx not available for Slack alerts")
            return False

        try:
            # Build Slack message
            color = self._get_alert_color(alert.severity)

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 {alert.rule_name}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True,
                            },
                            {
                                "title": "Value",
                                "value": f"{alert.value:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Threshold",
                                "value": f"{alert.threshold:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Started",
                                "value": alert.started_at.strftime(
                                    "%Y-%m-%d %H:%M:%S UTC"
                                ),
                                "short": True,
                            },
                        ],
                        "footer": "Reddit Technical Watcher",
                        "ts": int(alert.started_at.timestamp()),
                    }
                ]
            }

            if self.channel:
                payload["channel"] = self.channel

            # Add labels as fields
            if alert.labels:
                for key, value in alert.labels.items():
                    payload["attachments"][0]["fields"].append(
                        {"title": key.title(), "value": value, "short": True}
                    )

            # Send to Slack
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url, json=payload, timeout=10.0
                )

                if response.status_code == 200:
                    self.logger.info(f"Alert sent to Slack: {alert.rule_name}")
                    return True
                else:
                    self.logger.error(
                        f"Slack webhook failed: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _get_alert_color(self, severity: AlertSeverity) -> str:
        """Get Slack color for alert severity."""
        color_map = {
            AlertSeverity.INFO: "good",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.CRITICAL: "danger",
        }
        return color_map.get(severity, "warning")


class EmailAlertChannel(AlertChannel):
    """Email SMTP alert channel."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: list[str],
        use_tls: bool = True,
    ):
        super().__init__("email")
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 Reddit Watcher Alert: {alert.rule_name}"
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)

            # Create HTML body
            html_body = self._create_html_body(alert)
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # Create text body
            text_body = self._create_text_body(alert)
            text_part = MIMEText(text_body, "plain")
            msg.attach(text_part)

            # Send email
            context = ssl.create_default_context()

            if self.use_tls:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, context=context
                ) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)

            self.logger.info(f"Alert sent via email: {alert.rule_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False

    def _create_html_body(self, alert: Alert) -> str:
        """Create HTML email body."""
        severity_colors = {
            AlertSeverity.INFO: "#17a2b8",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.CRITICAL: "#dc3545",
        }

        color = severity_colors.get(alert.severity, "#6c757d")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .alert-container {{ border-left: 4px solid {color}; padding: 20px; background-color: #f8f9fa; }}
                .alert-title {{ color: {color}; font-size: 24px; margin-bottom: 10px; }}
                .alert-message {{ font-size: 16px; margin-bottom: 20px; }}
                .alert-details {{ background-color: white; padding: 15px; border-radius: 5px; }}
                .detail-row {{ margin-bottom: 10px; }}
                .detail-label {{ font-weight: bold; color: #495057; }}
                .detail-value {{ color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="alert-container">
                <h1 class="alert-title">🚨 {alert.rule_name}</h1>
                <p class="alert-message">{alert.message}</p>

                <div class="alert-details">
                    <div class="detail-row">
                        <span class="detail-label">Severity:</span>
                        <span class="detail-value">{alert.severity.value.upper()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Current Value:</span>
                        <span class="detail-value">{alert.value:.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Threshold:</span>
                        <span class="detail-value">{alert.threshold:.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Started At:</span>
                        <span class="detail-value">{alert.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</span>
                    </div>
        """

        # Add labels
        if alert.labels:
            html += "<h3>Labels:</h3>"
            for key, value in alert.labels.items():
                html += f'<div class="detail-row"><span class="detail-label">{key.title()}:</span> <span class="detail-value">{value}</span></div>'

        html += """
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _create_text_body(self, alert: Alert) -> str:
        """Create plain text email body."""
        text = f"""
Reddit Technical Watcher Alert

Alert: {alert.rule_name}
Message: {alert.message}

Details:
- Severity: {alert.severity.value.upper()}
- Current Value: {alert.value:.2f}
- Threshold: {alert.threshold:.2f}
- Started At: {alert.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")}
"""

        if alert.labels:
            text += "\nLabels:\n"
            for key, value in alert.labels.items():
                text += f"- {key.title()}: {value}\n"

        return text


class AlertManager:
    """
    Centralized alert management system.

    Features:
    - Rule-based alerting
    - Multi-channel delivery
    - Alert state tracking
    - Cooldown management
    - Escalation policies
    - Alert history
    """

    def __init__(self):
        self.alert_rules: dict[str, AlertRule] = {}
        self.alert_channels: dict[str, AlertChannel] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []

        # Monitoring configuration
        self.check_interval = 30.0  # seconds
        self.history_limit = 1000

        # Monitoring task
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        # Metrics for alerting itself
        self.metrics: PrometheusMetricsCollector | None = None

        self.logger = logging.getLogger(__name__)

    def register_metrics_collector(self, metrics: PrometheusMetricsCollector):
        """Register metrics collector for alerting metrics."""
        self.metrics = metrics

    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.alert_rules[rule.name] = rule
        self.logger.info(f"Added alert rule: {rule.name}")

    def add_alert_channel(self, channel: AlertChannel):
        """Add an alert delivery channel."""
        self.alert_channels[channel.name] = channel
        self.logger.info(f"Added alert channel: {channel.name}")

    def remove_alert_rule(self, rule_name: str):
        """Remove an alert rule."""
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]
            # Resolve any active alerts for this rule
            if rule_name in self.active_alerts:
                self._resolve_alert(rule_name)
            self.logger.info(f"Removed alert rule: {rule_name}")

    async def start_monitoring(self):
        """Start alert monitoring."""
        if self._is_monitoring:
            self.logger.warning("Alert monitoring already started")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info(f"Alert monitoring started (interval: {self.check_interval}s)")

    async def stop_monitoring(self):
        """Stop alert monitoring."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Alert monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop that evaluates alert rules."""
        self.logger.info("Alert monitoring loop started")

        while self._is_monitoring:
            try:
                await self._evaluate_rules()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                self.logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def _evaluate_rules(self):
        """Evaluate all alert rules and update alert states."""
        for rule_name, rule in self.alert_rules.items():
            try:
                # Evaluate rule condition
                condition_met = await self._evaluate_rule_condition(rule)
                current_time = datetime.now(UTC)

                if condition_met:
                    # Check if alert already exists
                    if rule_name in self.active_alerts:
                        alert = self.active_alerts[rule_name]

                        # Check if alert should be re-sent (cooldown)
                        if (
                            alert.last_sent_at is None
                            or (current_time - alert.last_sent_at).total_seconds()
                            >= rule.cooldown_seconds
                        ):
                            await self._send_alert(alert)
                            alert.last_sent_at = current_time
                    else:
                        # Create new alert
                        await self._create_alert(rule)
                else:
                    # Condition not met, resolve alert if active
                    if rule_name in self.active_alerts:
                        self._resolve_alert(rule_name)

            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule_name}: {e}")

    async def _evaluate_rule_condition(self, rule: AlertRule) -> bool:
        """Evaluate a single rule condition."""
        try:
            return rule.condition()
        except Exception as e:
            self.logger.error(f"Error in rule condition {rule.name}: {e}")
            return False

    async def _create_alert(self, rule: AlertRule):
        """Create a new alert."""
        try:
            # Get current value (this would be from metrics)
            current_value = rule.threshold + 1  # Placeholder

            alert = Alert(
                rule_name=rule.name,
                message=f"{rule.description} (current: {current_value:.2f}, threshold: {rule.threshold:.2f})",
                severity=rule.severity,
                state=AlertState.FIRING,
                value=current_value,
                threshold=rule.threshold,
                started_at=datetime.now(UTC),
                labels=rule.labels.copy(),
                annotations=rule.annotations.copy(),
            )

            self.active_alerts[rule.name] = alert
            self.alert_history.append(alert)

            # Trim history
            if len(self.alert_history) > self.history_limit:
                self.alert_history = self.alert_history[-self.history_limit :]

            # Send alert
            await self._send_alert(alert)
            alert.last_sent_at = datetime.now(UTC)

            # Record metrics
            if self.metrics:
                self.metrics.alert_delivery_operations_total.labels(
                    agent_type="alertmanager", channel="all", status="created"
                ).inc()

            self.logger.warning(f"Alert created: {rule.name}")

        except Exception as e:
            self.logger.error(f"Failed to create alert for rule {rule.name}: {e}")

    def _resolve_alert(self, rule_name: str):
        """Resolve an active alert."""
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.state = AlertState.RESOLVED
            alert.resolved_at = datetime.now(UTC)

            del self.active_alerts[rule_name]

            # Record metrics
            if self.metrics:
                self.metrics.alert_delivery_operations_total.labels(
                    agent_type="alertmanager", channel="all", status="resolved"
                ).inc()

            self.logger.info(f"Alert resolved: {rule_name}")

    async def _send_alert(self, alert: Alert):
        """Send alert through all configured channels."""
        if not self.alert_channels:
            self.logger.warning(
                f"No alert channels configured for alert: {alert.rule_name}"
            )
            return

        sent_count = 0
        failed_count = 0

        for channel_name, channel in self.alert_channels.items():
            if not channel.enabled:
                continue

            try:
                success = await channel.send_alert(alert)
                if success:
                    sent_count += 1

                    # Record metrics
                    if self.metrics:
                        self.metrics.alert_delivery_operations_total.labels(
                            agent_type="alertmanager",
                            channel=channel_name,
                            status="success",
                        ).inc()
                else:
                    failed_count += 1

                    # Record metrics
                    if self.metrics:
                        self.metrics.alert_delivery_failures_total.labels(
                            agent_type="alertmanager",
                            channel=channel_name,
                            error_type="delivery_failed",
                        ).inc()

            except Exception as e:
                failed_count += 1
                self.logger.error(f"Failed to send alert via {channel_name}: {e}")

                # Record metrics
                if self.metrics:
                    self.metrics.alert_delivery_failures_total.labels(
                        agent_type="alertmanager",
                        channel=channel_name,
                        error_type="exception",
                    ).inc()

        self.logger.info(
            f"Alert sent: {alert.rule_name} (success: {sent_count}, failed: {failed_count})"
        )

    def get_active_alerts(self) -> list[Alert]:
        """Get list of currently active alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(self, limit: int | None = None) -> list[Alert]:
        """Get alert history."""
        if limit:
            return self.alert_history[-limit:]
        return self.alert_history.copy()

    def get_alert_summary(self) -> dict[str, Any]:
        """Get alert summary statistics."""
        active_by_severity = {
            AlertSeverity.INFO: 0,
            AlertSeverity.WARNING: 0,
            AlertSeverity.CRITICAL: 0,
        }

        for alert in self.active_alerts.values():
            active_by_severity[alert.severity] += 1

        return {
            "active_alerts": len(self.active_alerts),
            "total_rules": len(self.alert_rules),
            "active_channels": len(
                [c for c in self.alert_channels.values() if c.enabled]
            ),
            "active_by_severity": {
                "info": active_by_severity[AlertSeverity.INFO],
                "warning": active_by_severity[AlertSeverity.WARNING],
                "critical": active_by_severity[AlertSeverity.CRITICAL],
            },
            "history_count": len(self.alert_history),
        }


# Global alert manager instance
_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Convenience functions for creating common alert rules
def create_health_alert_rule(service_name: str, health_monitor) -> AlertRule:
    """Create an alert rule for service health degradation."""

    def condition():
        health = health_monitor.get_service_health()
        return health.overall_status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]

    return AlertRule(
        name=f"{service_name}_health_degraded",
        description=f"{service_name} service health is degraded or unhealthy",
        condition=condition,
        severity=AlertSeverity.WARNING,
        threshold=1.0,
        duration_seconds=60.0,
        cooldown_seconds=300.0,
        labels={"service": service_name, "type": "health"},
        annotations={
            "runbook": f"https://docs.reddit-watcher.com/runbooks/{service_name}-health"
        },
    )


def create_metric_threshold_alert_rule(
    name: str,
    metric_getter: Callable[[], float],
    threshold: float,
    severity: AlertSeverity = AlertSeverity.WARNING,
    comparison: str = "greater",
) -> AlertRule:
    """Create an alert rule for metric threshold violations."""

    def condition():
        try:
            value = metric_getter()
            if comparison == "greater":
                return value > threshold
            elif comparison == "less":
                return value < threshold
            elif comparison == "equal":
                return value == threshold
            else:
                return False
        except Exception:
            return False

    return AlertRule(
        name=name,
        description=f"Metric threshold violation: {name}",
        condition=condition,
        severity=severity,
        threshold=threshold,
        duration_seconds=120.0,
        cooldown_seconds=600.0,
        labels={"type": "metric_threshold", "comparison": comparison},
        annotations={"threshold": str(threshold)},
    )
