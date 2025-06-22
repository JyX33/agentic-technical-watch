# ABOUTME: Custom A2A protocol implementation to avoid SDK conflicts
# ABOUTME: Provides clean protocol types and interfaces for agent communication

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class In(Enum):
    """Location for API key security schemes."""

    COOKIE = "cookie"
    HEADER = "header"
    QUERY = "query"


@dataclass
class AgentSkill:
    """Represents a skill that an agent can perform."""

    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    inputModes: list[str] = field(
        default_factory=lambda: ["text/plain", "application/json"]
    )
    outputModes: list[str] = field(default_factory=lambda: ["application/json"])
    examples: list[dict] = field(default_factory=list)


@dataclass
class AgentCapabilities:
    """Defines the capabilities of an agent."""

    input_modes: list[str] = field(
        default_factory=lambda: ["text/plain", "application/json"]
    )
    output_modes: list[str] = field(
        default_factory=lambda: ["text/plain", "application/json"]
    )
    streaming: bool = True
    authentication_required: bool = False


@dataclass
class AgentProvider:
    """Information about the agent provider."""

    organization: str
    url: str


@dataclass
class APIKeySecurityScheme:
    """API Key security scheme configuration."""

    name: str
    description: str
    in_: In
    type: str = "apiKey"


@dataclass
class HTTPAuthSecurityScheme:
    """HTTP authentication security scheme."""

    name: str
    description: str
    scheme: str = "Bearer"
    type: str = "http"


@dataclass
class AgentCard:
    """Agent Card for service discovery and capabilities description."""

    name: str
    description: str
    version: str
    provider: AgentProvider
    url: str
    defaultInputModes: list[str]
    defaultOutputModes: list[str]
    capabilities: AgentCapabilities
    skills: list[AgentSkill]
    securitySchemes: list[Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "provider": {
                "organization": self.provider.organization,
                "url": self.provider.url,
            },
            "url": self.url,
            "defaultInputModes": self.defaultInputModes,
            "defaultOutputModes": self.defaultOutputModes,
            "capabilities": {
                "input_modes": self.capabilities.input_modes,
                "output_modes": self.capabilities.output_modes,
                "streaming": self.capabilities.streaming,
                "authentication_required": self.capabilities.authentication_required,
            },
            "skills": [
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "tags": skill.tags,
                    "inputModes": skill.inputModes,
                    "outputModes": skill.outputModes,
                    "examples": skill.examples,
                }
                for skill in self.skills
            ],
            "securitySchemes": [
                {
                    "name": scheme.name,
                    "type": scheme.type,
                    "description": scheme.description,
                    **({"in": scheme.in_.value} if hasattr(scheme, "in_") else {}),
                    **({"scheme": scheme.scheme} if hasattr(scheme, "scheme") else {}),
                }
                for scheme in (self.securitySchemes or [])
            ],
        }


class RequestContext:
    """Context for an A2A request."""

    def __init__(self, message: str | None = None, metadata: dict | None = None):
        self.message = message
        self.metadata = metadata or {}


class EventQueue:
    """Queue for sending events back to clients."""

    def __init__(self):
        self._events: list[Any] = []

    async def enqueue_event(self, event: Any) -> None:
        """Add an event to the queue."""
        self._events.append(event)

    def get_events(self) -> list[Any]:
        """Get all events (for testing)."""
        return self._events

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._events.clear()


class AgentExecutor(Protocol):
    """Protocol for agent execution."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute an agent request."""
        ...

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel an ongoing task."""
        ...


def new_agent_text_message(text: str) -> dict[str, Any]:
    """Create a new agent text message."""
    return {"type": "agent_message", "content": text, "content_type": "text/plain"}


def new_agent_json_message(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new agent JSON message."""
    return {
        "type": "agent_message",
        "content": json.dumps(data),
        "content_type": "application/json",
    }
