# ABOUTME: AlertAgent for multi-channel notifications via Slack webhooks and SMTP email
# ABOUTME: Implements A2A skills for sending alerts with rich formatting, deduplication, and delivery tracking

import asyncio
import hashlib
import json
import logging
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiohttp
from jinja2 import BaseLoader, Environment, Template, select_autoescape

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import (
    BaseA2AAgent,
)
from reddit_watcher.config import Settings
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

    def __init__(self, config: Settings):
        super().__init__(
            config=config,
            agent_type="alert",
            name="Alert Notification Agent",
            description="Delivers notifications via Slack webhooks and SMTP email with rich formatting",
            version="1.0.0",
        )

        # Configure Jinja2 with autoescape for security
        self.jinja_env = Environment(
            autoescape=select_autoescape(["html", "xml"]), loader=BaseLoader()
        )

        # Template cache for message formatting
        self._slack_template_cache: dict[str, Template] = {}
        self._email_template_cache: dict[str, Template] = {}

        # Delivery tracking for deduplication
        self._delivery_hashes: set[str] = set()

        # HTTP session for webhook requests
        self._http_session: aiohttp.ClientSession | None = None

    async def _ensure_http_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session is initialized for webhook requests."""
        if not self._http_session or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(
                limit=10,  # Total connection pool size
                limit_per_host=5,  # Connections per host
                ttl_dns_cache=300,  # DNS cache TTL in seconds
                use_dns_cache=True,
                keepalive_timeout=30,  # Keep-alive timeout
                enable_cleanup_closed=True,
            )
            self._http_session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                raise_for_status=False,  # Handle status codes manually
            )
        return self._http_session

    async def _cleanup_http_session(self) -> None:
        """Cleanup HTTP session resources properly."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            # Wait for proper cleanup
            await asyncio.sleep(0.1)
        self._http_session = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_http_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup_http_session()

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, "_http_session") and self._http_session:
            if not self._http_session.closed:
                # Use try/except for graceful cleanup during shutdown
                try:
                    import asyncio

                    if asyncio.get_event_loop().is_running():
                        asyncio.create_task(self._cleanup_http_session())
                except RuntimeError:
                    # Event loop is not running, can't clean up async resources
                    logger.warning(
                        "Could not cleanup HTTP session during deletion - event loop not running"
                    )
                    pass

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

        if not self.config.has_slack_webhook():
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

        # Send webhook request using managed session
        try:
            session = await self._ensure_http_session()
            async with session.post(
                self.config.slack_webhook_url,
                json=slack_payload,
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
                    raise Exception(f"Slack API error {response.status}: {error_text}")

        except TimeoutError as e:
            raise Exception("Slack webhook request timed out") from e
        except aiohttp.ClientError as e:
            raise Exception(f"Slack webhook connection error: {e}") from e

    async def _send_email_alert(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Send alert via SMTP email with HTML/text templates."""
        message = parameters.get("message", "")
        subject = parameters.get("subject", "Reddit Alert")
        recipients = parameters.get("recipients", self.config.email_recipients)
        priority = parameters.get("priority", "medium").lower()
        html_template = parameters.get("html_template", "default")
        metadata = parameters.get("metadata", {})

        if not self.config.has_smtp_config():
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
                "slack_configured": self.config.has_slack_webhook(),
                "smtp_configured": self.config.has_smtp_config(),
                "email_recipients": len(self.config.email_recipients),
            }
        )

        if check_connectivity:
            # Test Slack connectivity
            slack_status = "not_configured"
            if self.config.has_slack_webhook():
                try:
                    session = await self._ensure_http_session()
                    # Send a test ping (empty payload)
                    async with session.post(
                        self.config.slack_webhook_url,
                        json={"text": ""},
                    ) as response:
                        slack_status = (
                            "connected" if response.status in [200, 400] else "error"
                        )
                except Exception:
                    slack_status = "connection_failed"

            # Test SMTP connectivity
            smtp_status = "not_configured"
            if self.config.has_smtp_config():
                try:
                    # Test SMTP connection asynchronously
                    smtp_status = await asyncio.to_thread(self._test_smtp_connection)
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
        """Get or create HTML email template with proper escaping."""
        if template_name not in self._email_template_cache:
            # Default HTML template with proper escaping
            html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ subject | e }}</title>
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
    <div class="header priority-{{ priority | e }}">
        <h1>{{ priority_emoji | e }} {{ subject | e }}</h1>
    </div>
    <div class="content">
        <p>{{ message | e | replace('\n', '<br>') | safe }}</p>
        {% if metadata %}
        <div class="metadata">
            <h3>Additional Information:</h3>
            {% for key, value in metadata.items() %}
            <p><strong>{{ key | e | replace('_', ' ') | title }}:</strong> {{ value | e }}</p>
            {% endfor %}
        </div>
        {% endif %}
    </div>
    <div class="footer">
        <p>Reddit Technical Watcher • {{ timestamp | e }}</p>
    </div>
</body>
</html>
            """.strip()
            self._email_template_cache[template_name] = self.jinja_env.from_string(
                html_template
            )

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
            # Text templates don't need autoescape, but we use the same environment for consistency
            self._email_template_cache["text"] = self.jinja_env.from_string(
                text_template
            )

        return self._email_template_cache["text"]

    async def _send_smtp_email(
        self, recipients: list[str], subject: str, html_content: str, text_content: str
    ) -> None:
        """Send email via SMTP server with proper connection management."""
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.smtp_username
        msg["To"] = ", ".join(recipients)

        # Add text and HTML parts
        text_part = MIMEText(text_content, "plain")
        html_part = MIMEText(html_content, "html")
        msg.attach(text_part)
        msg.attach(html_part)

        # Send email with proper connection management
        try:
            # Run SMTP operations in thread to avoid blocking
            await asyncio.to_thread(self._send_smtp_sync, msg, recipients)
        except Exception as e:
            logger.error(f"SMTP email sending failed: {e}")
            raise

    def _send_smtp_sync(self, msg: MIMEMultipart, recipients: list[str]) -> None:
        """Send SMTP email synchronously with proper connection cleanup."""
        server = None
        try:
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.set_debuglevel(0)  # Disable debug output

            if self.config.smtp_use_tls:
                server.starttls()

            server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(msg)
            logger.debug(f"Email sent successfully to {len(recipients)} recipients")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            raise
        finally:
            if server:
                try:
                    server.quit()
                except Exception as e:
                    logger.warning(f"Error closing SMTP connection: {e}")
                    # Try force close if quit fails
                    try:
                        server.close()
                    except Exception:
                        pass

    def _test_smtp_connection(self) -> str:
        """Test SMTP connection synchronously."""
        server = None
        try:
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.set_debuglevel(0)  # Disable debug output

            if self.config.smtp_use_tls:
                server.starttls()

            server.login(self.config.smtp_username, self.config.smtp_password)
            server.noop()  # Send a no-op command to test the connection
            return "connected"
        except smtplib.SMTPException:
            return "connection_failed"
        except Exception:
            return "connection_failed"
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    # Try force close if quit fails
                    try:
                        server.close()
                    except Exception:
                        pass

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
                    "slack": self.config.has_slack_webhook(),
                    "email": self.config.has_smtp_config(),
                },
                "email_recipients_count": len(self.config.email_recipients),
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
