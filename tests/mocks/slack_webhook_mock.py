# ABOUTME: Mock Slack webhook server for integration testing
# ABOUTME: Provides controlled Slack webhook responses without requiring real Slack integration

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Mock Slack Webhook", version="1.0.0")

# Store received webhooks for testing verification
received_webhooks: list[dict[str, Any]] = []


class SlackMessage(BaseModel):
    text: str | None = None
    blocks: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None
    channel: str | None = None
    username: str | None = None
    icon_emoji: str | None = None
    icon_url: str | None = None


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health checks"""
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.post("/webhook")
async def receive_webhook(message: SlackMessage):
    """Mock Slack webhook endpoint"""

    # Store the received webhook for test verification
    webhook_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "message": message.dict(),
        "id": len(received_webhooks) + 1,
    }

    received_webhooks.append(webhook_data)

    # Mock successful Slack response
    return {"ok": True, "message": f"Message received at {webhook_data['timestamp']}"}


@app.post("/webhook/error")
async def webhook_error():
    """Simulate webhook error for testing error handling"""
    raise HTTPException(
        status_code=400,
        detail={
            "ok": False,
            "error": "invalid_payload",
            "message": "The payload is invalid",
        },
    )


@app.post("/webhook/rate-limit")
async def webhook_rate_limit():
    """Simulate rate limiting for testing retry logic"""
    raise HTTPException(
        status_code=429,
        detail={"ok": False, "error": "rate_limited", "message": "Rate limit exceeded"},
    )


@app.get("/webhooks/received")
async def get_received_webhooks():
    """Get all received webhooks for test verification"""
    return {"count": len(received_webhooks), "webhooks": received_webhooks}


@app.get("/webhooks/received/{webhook_id}")
async def get_webhook_by_id(webhook_id: int):
    """Get specific webhook by ID for test verification"""
    try:
        webhook = received_webhooks[webhook_id - 1]  # 1-based indexing
        return webhook
    except IndexError as err:
        raise HTTPException(status_code=404, detail="Webhook not found") from err


@app.get("/webhooks/received/latest")
async def get_latest_webhook():
    """Get the most recently received webhook"""
    if not received_webhooks:
        raise HTTPException(status_code=404, detail="No webhooks received")

    return received_webhooks[-1]


@app.delete("/webhooks/clear")
async def clear_webhooks():
    """Clear all received webhooks - useful for test isolation"""
    global received_webhooks
    count = len(received_webhooks)
    received_webhooks.clear()

    return {"message": f"Cleared {count} webhooks"}


@app.get("/webhooks/search")
async def search_webhooks(text: str | None = None, channel: str | None = None):
    """Search webhooks by text content or channel"""
    filtered_webhooks = received_webhooks

    if text:
        filtered_webhooks = [
            w
            for w in filtered_webhooks
            if (
                w["message"].get("text")
                and text.lower() in w["message"]["text"].lower()
            )
            or (
                w["message"].get("blocks")
                and any(
                    block.get("text", {}).get("text", "").lower().find(text.lower())
                    >= 0
                    for block in w["message"]["blocks"]
                )
            )
        ]

    if channel:
        filtered_webhooks = [
            w for w in filtered_webhooks if w["message"].get("channel") == channel
        ]

    return {"count": len(filtered_webhooks), "webhooks": filtered_webhooks}


@app.get("/webhooks/stats")
async def get_webhook_stats():
    """Get statistics about received webhooks"""
    if not received_webhooks:
        return {
            "total_count": 0,
            "channels": {},
            "message_types": {},
            "first_received": None,
            "last_received": None,
        }

    # Analyze channels
    channels = {}
    message_types = {"text": 0, "blocks": 0, "attachments": 0}

    for webhook in received_webhooks:
        message = webhook["message"]

        # Count channels
        channel = message.get("channel", "unknown")
        channels[channel] = channels.get(channel, 0) + 1

        # Count message types
        if message.get("text"):
            message_types["text"] += 1
        if message.get("blocks"):
            message_types["blocks"] += 1
        if message.get("attachments"):
            message_types["attachments"] += 1

    return {
        "total_count": len(received_webhooks),
        "channels": channels,
        "message_types": message_types,
        "first_received": received_webhooks[0]["timestamp"],
        "last_received": received_webhooks[-1]["timestamp"],
    }


@app.post("/webhooks/test-message")
async def send_test_message(message: dict[str, Any]):
    """Send a test message to simulate webhook reception"""
    webhook_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "message": message,
        "id": len(received_webhooks) + 1,
        "test_message": True,
    }

    received_webhooks.append(webhook_data)

    return {
        "ok": True,
        "webhook_id": webhook_data["id"],
        "message": "Test message received",
    }


# Legacy endpoint for compatibility
@app.post("/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX")
async def legacy_webhook_endpoint(request: Request):
    """Legacy Slack webhook format for compatibility testing"""
    body = await request.json()

    webhook_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "message": body,
        "id": len(received_webhooks) + 1,
        "legacy_format": True,
    }

    received_webhooks.append(webhook_data)

    return {"ok": True}
