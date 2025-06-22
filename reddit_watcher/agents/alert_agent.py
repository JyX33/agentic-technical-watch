# ABOUTME: AlertAgent for multi-channel notifications via Slack webhooks and SMTP email
# ABOUTME: Implements A2A skills for sending alerts with rich formatting, deduplication, and delivery tracking

import hashlib
import json
import logging
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiohttp
from jinja2 import Template

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import (
    BaseA2AAgent,
)
from reddit_watcher.models import AlertStatus

logger = logging.getLogger(__name__)


class AlertAgent(BaseA2AAgent):
    """
    AlertAgent for delivering multi-channel notifications via Slack and email.

    Implements A2A skills for:
    - Sending Slack webhook notifications with rich formatting
    - Sending SMTP email alerts with HTML/text templates
    - Alert deduplication and delivery tracking
    - Configurable channel routing and formatting
    """

    def __init__(self):
        super().__init__(
            agent_type="alert",
            name="Alert Notification Agent",
            description="Delivers notifications via Slack webhooks and SMTP email with rich formatting",
            version="1.0.0",
        )

        # Template cache for message formatting
        self._slack_template_cache: dict[str, Template] = {}
        self._email_template_cache: dict[str, Template] = {}

        # Delivery tracking for deduplication
        self._delivery_hashes: set[str] = set()

    def get_skills(self) -> list[AgentSkill]:
        """Define the alert notification skills."""
        return [
            AgentSkill(
                id="sendSlack",
                name="sendSlack",
                description="Send rich formatted notification to Slack via webhook",
                tags=["notification", "slack", "webhook"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="sendEmail",
                name="sendEmail",
                description="Send formatted email alert via SMTP",
                tags=["notification", "email", "smtp"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="health_check",
                name="health_check",
                description="Check agent health and notification service connectivity",
                tags=["health", "status", "connectivity"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
        ]

    async def execute_skill(
        self, skill_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a specific alert skill with given parameters."""
        try:
            if skill_name == "sendSlack":
                return await self._send_slack_alert(parameters)
            elif skill_name == "sendEmail":
                return await self._send_email_alert(parameters)
            elif skill_name == "health_check":
                return await self._health_check(parameters)
            else:
                raise ValueError(f"Unknown skill: {skill_name}")

        except Exception as e:
            self.logger.error(f"Error executing skill {skill_name}: {e}", exc_info=True)
            return {
                "status": "error",
                "skill": skill_name,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }

    async def _send_slack_alert(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Send alert via Slack webhook with rich formatting."""
        message = parameters.get("message", "")
        title = parameters.get("title", "Reddit Alert")
        priority = parameters.get("priority", "medium").lower()
        metadata = parameters.get("metadata", {})

        if not self.settings.has_slack_webhook():
            raise ValueError("Slack webhook not configured")

        # Generate deduplication hash
        dedup_hash = self._generate_dedup_hash("slack", message, title, metadata)
        if dedup_hash in self._delivery_hashes:
            return {
                "status": "skipped",
                "reason": "duplicate_alert",
                "deduplication_hash": dedup_hash,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # Format Slack message with rich formatting
        slack_payload = self._format_slack_message(message, title, priority, metadata)

        # Send webhook request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.settings.slack_webhook_url,
                    json=slack_payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        # Track successful delivery
                        self._delivery_hashes.add(dedup_hash)
                        await self._track_delivery("slack", dedup_hash, "success")

                        return {
                            "status": "success",
                            "channel": "slack",
                            "deduplication_hash": dedup_hash,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    else:
                        error_text = await response.text()
                        raise Exception(
                            f"Slack API error {response.status}: {error_text}"
                        )

        except TimeoutError as e:
            raise Exception("Slack webhook request timed out") from e
        except aiohttp.ClientError as e:
            raise Exception(f"Slack webhook connection error: {e}") from e

    async def _send_email_alert(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Send alert via SMTP email with HTML/text templates."""
        message = parameters.get("message", "")
        subject = parameters.get("subject", "Reddit Alert")
        recipients = parameters.get("recipients", self.settings.email_recipients)
        priority = parameters.get("priority", "medium").lower()
        html_template = parameters.get("html_template", "default")
        metadata = parameters.get("metadata", {})

        if not self.settings.has_smtp_config():
            raise ValueError("SMTP configuration not available")

        if not recipients:
            raise ValueError("No email recipients configured")

        # Generate deduplication hash
        dedup_hash = self._generate_dedup_hash("email", message, subject, metadata)
        if dedup_hash in self._delivery_hashes:
            return {
                "status": "skipped",
                "reason": "duplicate_alert",
                "deduplication_hash": dedup_hash,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # Format email content
        html_content, text_content = self._format_email_content(
            message, subject, priority, html_template, metadata
        )

        # Send email
        try:
            await self._send_smtp_email(recipients, subject, html_content, text_content)

            # Track successful delivery
            self._delivery_hashes.add(dedup_hash)
            await self._track_delivery("email", dedup_hash, "success", recipients)

            return {
                "status": "success",
                "channel": "email",
                "recipients": recipients,
                "deduplication_hash": dedup_hash,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            await self._track_delivery(
                "email", dedup_hash, "failed", recipients, str(e)
            )
            raise

    async def _health_check(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Perform health check and optionally test connectivity."""
        check_connectivity = parameters.get("check_connectivity", False)

        health_status = self.get_common_health_status()
        health_status.update(
            {
                "slack_configured": self.settings.has_slack_webhook(),
                "smtp_configured": self.settings.has_smtp_config(),
                "email_recipients": len(self.settings.email_recipients),
            }
        )

        if check_connectivity:
            # Test Slack connectivity
            slack_status = "not_configured"
            if self.settings.has_slack_webhook():
                try:
                    async with aiohttp.ClientSession() as session:
                        # Send a test ping (empty payload)
                        async with session.post(
                            self.settings.slack_webhook_url,
                            json={"text": ""},
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as response:
                            slack_status = (
                                "connected"
                                if response.status in [200, 400]
                                else "error"
                            )
                except Exception:
                    slack_status = "connection_failed"

            # Test SMTP connectivity
            smtp_status = "not_configured"
            if self.settings.has_smtp_config():
                try:
                    # Test SMTP connection
                    server = smtplib.SMTP(
                        self.settings.smtp_server, self.settings.smtp_port
                    )
                    if self.settings.smtp_use_tls:
                        server.starttls()
                    server.login(
                        self.settings.smtp_username, self.settings.smtp_password
                    )
                    server.quit()
                    smtp_status = "connected"
                except Exception:
                    smtp_status = "connection_failed"

            health_status.update(
                {
                    "connectivity": {
                        "slack": slack_status,
                        "smtp": smtp_status,
                    }
                }
            )

        return health_status

    def _format_slack_message(
        self, message: str, title: str, priority: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Format message for Slack with rich formatting."""
        # Priority colors and emojis
        priority_config = {
            "low": {"color": "#36a64f", "emoji": "🟢"},
            "medium": {"color": "#ff9500", "emoji": "🟡"},
            "high": {"color": "#ff0000", "emoji": "🔴"},
            "critical": {"color": "#8b0000", "emoji": "🚨"},
        }

        config = priority_config.get(priority, priority_config["medium"])

        # Build attachment with rich formatting
        attachment = {
            "color": config["color"],
            "title": f"{config['emoji']} {title}",
            "text": message,
            "footer": "Reddit Technical Watcher",
            "ts": int(datetime.now(UTC).timestamp()),
            "fields": [],
        }

        # Add metadata fields
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, dict | list):
                    value = json.dumps(value, indent=2)
                attachment["fields"].append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": len(str(value)) < 50,
                    }
                )

        return {
            "username": "Reddit Watcher",
            "icon_emoji": ":robot_face:",
            "attachments": [attachment],
        }

    def _format_email_content(
        self,
        message: str,
        subject: str,
        priority: str,
        template_name: str,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        """Format email content with HTML and text versions."""
        # Get or create templates
        html_template = self._get_html_template(template_name)
        text_template = self._get_text_template()

        # Template context
        context = {
            "message": message,
            "subject": subject,
            "priority": priority,
            "metadata": metadata,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "priority_emoji": {
                "low": "🟢",
                "medium": "🟡",
                "high": "🔴",
                "critical": "🚨",
            }.get(priority, "🟡"),
        }

        # Render templates
        html_content = html_template.render(**context)
        text_content = text_template.render(**context)

        return html_content, text_content

    def _get_html_template(self, template_name: str) -> Template:
        """Get or create HTML email template."""
        if template_name not in self._email_template_cache:
            # Default HTML template
            html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ subject }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #f4f4f4; padding: 20px; text-align: center; }
        .priority-high { border-left: 5px solid #ff0000; }
        .priority-critical { border-left: 5px solid #8b0000; background-color: #ffe6e6; }
        .priority-medium { border-left: 5px solid #ff9500; }
        .priority-low { border-left: 5px solid #36a64f; }
        .content { padding: 20px; }
        .metadata { margin-top: 20px; padding: 15px; background-color: #f9f9f9; }
        .footer { font-size: 12px; color: #666; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header priority-{{ priority }}">
        <h1>{{ priority_emoji }} {{ subject }}</h1>
    </div>
    <div class="content">
        <p>{{ message | replace('\n', '<br>') }}</p>
        {% if metadata %}
        <div class="metadata">
            <h3>Additional Information:</h3>
            {% for key, value in metadata.items() %}
            <p><strong>{{ key | replace('_', ' ') | title }}:</strong> {{ value }}</p>
            {% endfor %}
        </div>
        {% endif %}
    </div>
    <div class="footer">
        <p>Reddit Technical Watcher • {{ timestamp }}</p>
    </div>
</body>
</html>
            """.strip()
            self._email_template_cache[template_name] = Template(html_template)

        return self._email_template_cache[template_name]

    def _get_text_template(self) -> Template:
        """Get or create text email template."""
        if "text" not in self._email_template_cache:
            text_template = """
{{ priority_emoji }} {{ subject }}

{{ message }}

{% if metadata %}
Additional Information:
{% for key, value in metadata.items() %}
{{ key | replace('_', ' ') | title }}: {{ value }}
{% endfor %}
{% endif %}

--
Reddit Technical Watcher
{{ timestamp }}
            """.strip()
            self._email_template_cache["text"] = Template(text_template)

        return self._email_template_cache["text"]

    async def _send_smtp_email(
        self, recipients: list[str], subject: str, html_content: str, text_content: str
    ) -> None:
        """Send email via SMTP server."""
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.settings.smtp_username
        msg["To"] = ", ".join(recipients)

        # Add text and HTML parts
        text_part = MIMEText(text_content, "plain")
        html_part = MIMEText(html_content, "html")
        msg.attach(text_part)
        msg.attach(html_part)

        # Send email
        server = smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port)
        try:
            if self.settings.smtp_use_tls:
                server.starttls()
            server.login(self.settings.smtp_username, self.settings.smtp_password)
            server.send_message(msg)
        finally:
            server.quit()

    def _generate_dedup_hash(
        self,
        channel: str,
        message: str,
        title_or_subject: str,
        metadata: dict[str, Any],
    ) -> str:
        """Generate deduplication hash for alerts."""
        # Create hash from content to detect duplicates
        content = f"{channel}:{title_or_subject}:{message}:{json.dumps(metadata, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _track_delivery(
        self,
        channel: str,
        dedup_hash: str,
        status: str,
        recipients: list[str] = None,
        error: str = None,
    ) -> None:
        """Track alert delivery for monitoring and debugging."""
        try:
            # For now, we'll just log the delivery since the full AlertBatch system
            # isn't implemented yet. In a complete implementation, we'd create an
            # AlertBatch first, then create AlertDelivery records for each channel.

            alert_status = (
                AlertStatus.SENT if status == "success" else AlertStatus.FAILED
            )

            self.logger.info(
                f"Alert delivery tracked: channel={channel}, status={alert_status.value}, "
                f"dedup_hash={dedup_hash}, recipients={recipients}, error={error}"
            )

            # TODO: Implement full AlertBatch and AlertDelivery tracking when needed
            # This would require:
            # 1. Create or find AlertBatch for this notification cycle
            # 2. Create AlertDelivery record with alert_batch_id
            # 3. Update delivery status and timing information

        except Exception as e:
            # Don't fail alert delivery if tracking fails
            self.logger.warning(f"Failed to track delivery: {e}")

    def get_health_status(self) -> dict[str, Any]:
        """Get agent health status."""
        status = self.get_common_health_status()
        status.update(
            {
                "notification_channels": {
                    "slack": self.settings.has_slack_webhook(),
                    "email": self.settings.has_smtp_config(),
                },
                "email_recipients_count": len(self.settings.email_recipients),
                "delivery_cache_size": len(self._delivery_hashes),
            }
        )
        return status


if __name__ == "__main__":
    import asyncio

    from .server import A2AAgentServer

    async def main():
        agent = AlertAgent()
        server = A2AAgentServer(agent)
        await server.start_server()

    asyncio.run(main())
