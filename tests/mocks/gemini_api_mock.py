# ABOUTME: Mock Gemini API server for integration testing
# ABOUTME: Provides controlled Gemini API responses without requiring real Gemini API access

import hashlib
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Gemini API", version="1.0.0")


class ContentPart(BaseModel):
    text: str


class Content(BaseModel):
    parts: list[ContentPart]


class GenerateContentRequest(BaseModel):
    contents: list[Content]
    generationConfig: dict[str, Any] | None = None


class GenerateContentResponse(BaseModel):
    candidates: list[dict[str, Any]]
    usageMetadata: dict[str, Any]


# Mock response templates
SUMMARY_TEMPLATES = {
    "claude_code": "**Claude Code Discussion Summary**\n\nKey points from the discussion:\n- Claude Code's A2A protocol is highly praised for multi-agent system development\n- Users report excellent results for AI agent building\n- Strong community interest in Reddit monitoring applications\n- Framework comparison shows competitive advantages\n\n**Community Sentiment:** Very positive\n**Engagement:** High (42 upvotes, 15 comments)\n**Technical Focus:** A2A protocol, agent development",
    "ai_framework": "**AI Framework Comparison Summary**\n\nDiscussion highlights:\n- Comparative analysis of AI development frameworks\n- Claude Code mentioned as a strong contender\n- Focus on practical implementation aspects\n- Community seeking guidance on framework selection\n\n**Community Sentiment:** Informative discussion\n**Engagement:** Moderate (28 upvotes, 8 comments)\n**Technical Focus:** Framework evaluation, development tools",
    "default": "**Content Summary**\n\nThe discussion covers various topics related to AI development and technical implementation. Key themes include:\n- Technical implementation challenges\n- Community feedback and experiences\n- Tool and framework comparisons\n- Best practices sharing\n\n**Community Sentiment:** Neutral to positive\n**Engagement:** Moderate\n**Technical Focus:** General AI development",
}


def generate_summary(content: str) -> str:
    """Generate appropriate summary based on content"""
    content_lower = content.lower()

    if "claude code" in content_lower:
        return SUMMARY_TEMPLATES["claude_code"]
    elif "framework" in content_lower and "comparison" in content_lower:
        return SUMMARY_TEMPLATES["ai_framework"]
    else:
        return SUMMARY_TEMPLATES["default"]


def generate_content_hash(content: str) -> str:
    """Generate consistent hash for content to ensure deterministic responses"""
    return hashlib.md5(content.encode()).hexdigest()[:8]


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health checks"""
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.post("/v1/models/gemini-2.5-flash:generateContent")
async def generate_content_flash(
    request: GenerateContentRequest, authorization: str | None = Header(None)
):
    """Mock Gemini 2.5 Flash content generation"""

    # Extract text content from request
    full_content = ""
    for content in request.contents:
        for part in content.parts:
            full_content += part.text + "\n"

    # Generate appropriate summary
    summary = generate_summary(full_content)
    _ = generate_content_hash(full_content)

    # Mock response structure matching Gemini API
    response = {
        "candidates": [
            {
                "content": {"parts": [{"text": summary}]},
                "finishReason": "STOP",
                "index": 0,
                "safetyRatings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "probability": "NEGLIGIBLE",
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "probability": "NEGLIGIBLE",
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "probability": "NEGLIGIBLE",
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "probability": "NEGLIGIBLE",
                    },
                ],
            }
        ],
        "usageMetadata": {
            "promptTokenCount": len(full_content.split()),
            "candidatesTokenCount": len(summary.split()),
            "totalTokenCount": len(full_content.split()) + len(summary.split()),
        },
        "modelVersion": "gemini-2.5-flash-001",
    }

    return response


@app.post("/v1/models/gemini-2.5-flash-lite:generateContent")
async def generate_content_flash_lite(
    request: GenerateContentRequest, authorization: str | None = Header(None)
):
    """Mock Gemini 2.5 Flash Lite content generation (faster, shorter responses)"""

    # Extract text content from request
    full_content = ""
    for content in request.contents:
        for part in content.parts:
            full_content += part.text + "\n"

    # Generate shorter summary for lite model
    summary = generate_summary(full_content)
    # Truncate to first paragraph for "lite" version
    summary = (
        summary.split("\n\n")[0]
        + "\n\n**Summary:** Condensed version from Gemini 2.5 Flash Lite"
    )

    _ = generate_content_hash(full_content)

    response = {
        "candidates": [
            {
                "content": {"parts": [{"text": summary}]},
                "finishReason": "STOP",
                "index": 0,
                "safetyRatings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "probability": "NEGLIGIBLE",
                    }
                ],
            }
        ],
        "usageMetadata": {
            "promptTokenCount": len(full_content.split()),
            "candidatesTokenCount": len(summary.split()),
            "totalTokenCount": len(full_content.split()) + len(summary.split()),
        },
        "modelVersion": "gemini-2.5-flash-lite-001",
    }

    return response


@app.post("/v1/models/gemini-2.5-flash:generateContent/stream")
async def generate_content_stream(
    request: GenerateContentRequest, authorization: str | None = Header(None)
):
    """Mock streaming content generation (returns non-streaming for simplicity)"""
    # For testing purposes, return the same as non-streaming
    return await generate_content_flash(request, authorization)


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(None)):
    """Mock model listing endpoint"""
    return {
        "models": [
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "description": "Fast and efficient AI model",
                "version": "001",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 8192,
                "supportedGenerationMethods": [
                    "generateContent",
                    "streamGenerateContent",
                ],
            },
            {
                "name": "models/gemini-2.5-flash-lite",
                "displayName": "Gemini 2.5 Flash Lite",
                "description": "Lightweight version of Gemini 2.5 Flash",
                "version": "001",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 4096,
                "supportedGenerationMethods": [
                    "generateContent",
                    "streamGenerateContent",
                ],
            },
        ]
    }


@app.post("/v1/test/rate-limit")
async def simulate_rate_limit():
    """Simulate rate limiting for testing retry logic"""
    raise HTTPException(
        status_code=429,
        detail={
            "error": {
                "code": 429,
                "message": "Rate limit exceeded",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )


@app.post("/v1/test/error")
async def simulate_error():
    """Simulate API error for testing error handling"""
    raise HTTPException(
        status_code=500,
        detail={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "status": "INTERNAL",
            }
        },
    )


@app.post("/v1/test/timeout")
async def simulate_timeout():
    """Simulate timeout for testing timeout handling"""
    import asyncio

    await asyncio.sleep(30)  # Simulate long delay
    return {"message": "This should timeout"}


@app.get("/v1/test/status")
async def get_mock_status():
    """Get mock API status for testing"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "requests_processed": 0,
        "rate_limit_remaining": 100,
        "model_versions": {"gemini-2.5-flash": "001", "gemini-2.5-flash-lite": "001"},
    }
