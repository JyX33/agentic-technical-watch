# ABOUTME: Configuration management for Reddit Technical Watcher using Pydantic BaseSettings
# ABOUTME: Provides unified settings for A2A agents, databases, and external APIs with .env support

from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Unified configuration for the Reddit Technical Watcher A2A system.

    Supports configuration via environment variables and .env files.
    Can be used as a singleton via get_settings() or as dependency injection
    via create_config() for better testability and architecture.

    Note: This class implements the ConfigProvider protocol from agents.base
    to support dependency injection while maintaining backward compatibility.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        # V3-ready configurations
        validate_default=False,  # Performance optimization
        frozen=False,  # Explicit mutability control
    )

    # Application Settings
    app_name: str = Field(
        default="Reddit Technical Watcher", description="Application name"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database Configuration
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/reddit_watcher",
        description="PostgreSQL database connection URL",
    )
    database_pool_size: int = Field(
        default=10, description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=20, description="Database connection pool max overflow"
    )

    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for A2A service discovery",
    )
    redis_pool_size: int = Field(default=10, description="Redis connection pool size")

    # A2A Agent Configuration
    agent_type: str | None = Field(default=None, description="Type of A2A agent")
    a2a_port: int = Field(default=8000, description="Port for A2A agent HTTP server")
    agent_port: int = Field(default=8000, description="Legacy alias for a2a_port")
    a2a_host: str = Field(
        default="0.0.0.0",
        description="Host for A2A agent HTTP server",
    )
    a2a_api_key: str = Field(default="", description="API key for A2A authentication")
    a2a_bearer_token: str = Field(
        default="",
        description="Bearer token for A2A authentication",
    )
    jwt_secret: str = Field(
        default="", description="JWT secret key for token authentication"
    )

    # A2A Agent Endpoints
    retrieval_agent_url: str = Field(
        default="http://localhost:8001",
        description="URL for the retrieval agent",
    )
    filter_agent_url: str = Field(
        default="http://localhost:8002",
        description="URL for the filter agent",
    )
    summarise_agent_url: str = Field(
        default="http://localhost:8003",
        description="URL for the summarise agent",
    )
    alert_agent_url: str = Field(
        default="http://localhost:8004",
        description="URL for the alert agent",
    )
    coordinator_agent_url: str = Field(
        default="http://localhost:8000",
        description="URL for the coordinator agent",
    )

    # A2A Service Discovery
    service_discovery_ttl: int = Field(
        default=30,
        description="TTL for service discovery in seconds",
    )
    agent_card_refresh_interval: int = Field(
        default=60,
        description="Agent card refresh interval in seconds",
    )

    # Reddit API Configuration
    reddit_client_id: str = Field(default="", description="Reddit OAuth2 client ID")
    reddit_client_secret: str = Field(
        default="",
        description="Reddit OAuth2 client secret",
    )
    reddit_user_agent: str = Field(
        default="Reddit Technical Watcher v0.1.0 by u/TechnicalWatcher",
        description="Reddit API user agent string",
    )
    reddit_rate_limit: int = Field(
        default=100,
        description="Reddit API rate limit (requests per minute)",
    )

    # Monitoring Topics
    reddit_topics: list[str] = Field(
        default=["Claude Code", "A2A", "Agent-to-Agent"],
        description="Topics to monitor on Reddit",
    )
    processing_interval: int = Field(
        default=14400,  # 4 hours in seconds
        description="Processing interval in seconds",
    )

    # Gemini API Configuration
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model_primary: str = Field(
        default="gemini-2.5-flash-lite-preview-06-17",
        description="Primary Gemini model for summarization",
    )
    gemini_model_fallback: str = Field(
        default="gemini-2.5-flash",
        description="Fallback Gemini model for summarization",
    )
    gemini_rate_limit: int = Field(
        default=100,
        description="Gemini API rate limit (requests per minute)",
    )

    # Notification Configuration
    slack_webhook_url: str = Field(
        default="",
        description="Slack webhook URL for notifications",
    )

    # SMTP Email Configuration
    smtp_server: str = Field(default="", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")

    # Email Recipients
    email_recipients: list[str] = Field(
        default=[],
        description="List of email recipients for alerts",
    )
    alert_email: str = Field(
        default="",
        description="Primary email address for alerts",
    )

    # Scheduling Configuration
    monitoring_interval_hours: int = Field(
        default=4,
        description="Monitoring cycle interval in hours",
    )

    # Content Filtering
    relevance_threshold: float = Field(
        default=0.7,
        description="Minimum relevance score for content filtering",
    )

    # Security Configuration
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="Maximum requests per minute per IP address",
    )
    rate_limit_requests_per_hour: int = Field(
        default=1000,
        description="Maximum requests per hour per IP address",
    )
    rate_limit_burst_limit: int = Field(
        default=10,
        description="Maximum burst requests in 10 seconds per IP",
    )
    rate_limit_whitelist: list[str] = Field(
        default=["127.0.0.1", "::1"],
        description="IP addresses exempt from rate limiting",
    )
    max_content_length: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum request content length in bytes",
    )
    cors_allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="CORS allowed origins",
    )
    security_headers_enabled: bool = Field(
        default=True,
        description="Enable security headers middleware",
    )

    # Circuit Breaker Configuration
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker pattern for agent communication",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        description="Number of consecutive failures to open circuit breaker",
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=60,
        description="Seconds to wait before attempting circuit breaker recovery",
    )
    circuit_breaker_success_threshold: int = Field(
        default=3,
        description="Successful calls needed in HALF_OPEN to close circuit breaker",
    )
    circuit_breaker_half_open_max_calls: int = Field(
        default=5,
        description="Maximum calls allowed in HALF_OPEN state",
    )
    circuit_breaker_call_timeout: float = Field(
        default=30.0,
        description="Maximum timeout for individual calls through circuit breaker",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Validate PostgreSQL database URL format."""
        if not v:
            raise ValueError("Database URL cannot be empty")

        parsed = urlparse(v)
        if parsed.scheme not in [
            "postgresql",
            "postgresql+psycopg2",
            "postgresql+asyncpg",
        ]:
            raise ValueError("Database URL must use postgresql scheme")

        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v:
            raise ValueError("Redis URL cannot be empty")

        parsed = urlparse(v)
        if parsed.scheme not in ["redis", "rediss"]:
            raise ValueError("Redis URL must use redis or rediss scheme")

        return v

    @field_validator("relevance_threshold")
    @classmethod
    def validate_relevance_threshold(cls, v):
        """Validate relevance threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Relevance threshold must be between 0.0 and 1.0")
        return v

    @field_validator("a2a_port")
    @classmethod
    def validate_a2a_port(cls, v):
        """Validate A2A port is in valid range."""
        if not 1024 <= v <= 65535:
            raise ValueError("A2A port must be between 1024 and 65535")
        return v

    @field_validator("circuit_breaker_failure_threshold")
    @classmethod
    def validate_circuit_breaker_failure_threshold(cls, v):
        """Validate circuit breaker failure threshold."""
        if v < 1:
            raise ValueError("Circuit breaker failure threshold must be at least 1")
        if v > 100:
            raise ValueError("Circuit breaker failure threshold should not exceed 100")
        return v

    @field_validator("circuit_breaker_recovery_timeout")
    @classmethod
    def validate_circuit_breaker_recovery_timeout(cls, v):
        """Validate circuit breaker recovery timeout."""
        if v < 1:
            raise ValueError(
                "Circuit breaker recovery timeout must be at least 1 second"
            )
        if v > 3600:
            raise ValueError(
                "Circuit breaker recovery timeout should not exceed 1 hour"
            )
        return v

    @field_validator("circuit_breaker_success_threshold")
    @classmethod
    def validate_circuit_breaker_success_threshold(cls, v):
        """Validate circuit breaker success threshold."""
        if v < 1:
            raise ValueError("Circuit breaker success threshold must be at least 1")
        if v > 20:
            raise ValueError("Circuit breaker success threshold should not exceed 20")
        return v

    @field_validator("circuit_breaker_call_timeout")
    @classmethod
    def validate_circuit_breaker_call_timeout(cls, v):
        """Validate circuit breaker call timeout."""
        if v <= 0:
            raise ValueError("Circuit breaker call timeout must be positive")
        if v > 300:
            raise ValueError("Circuit breaker call timeout should not exceed 5 minutes")
        return v

    def get_agent_urls(self) -> dict[str, str]:
        """Get all A2A agent URLs as a dictionary."""
        return {
            "retrieval": self.retrieval_agent_url,
            "filter": self.filter_agent_url,
            "summarise": self.summarise_agent_url,
            "alert": self.alert_agent_url,
            "coordinator": self.coordinator_agent_url,
        }

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug

    def has_reddit_credentials(self) -> bool:
        """Check if Reddit API credentials are configured."""
        return bool(self.reddit_client_id and self.reddit_client_secret)

    def has_gemini_credentials(self) -> bool:
        """Check if Gemini API credentials are configured."""
        return bool(self.gemini_api_key)

    def has_slack_webhook(self) -> bool:
        """Check if Slack webhook is configured."""
        return bool(self.slack_webhook_url)

    def has_smtp_config(self) -> bool:
        """Check if SMTP configuration is complete."""
        return bool(self.smtp_server and self.smtp_username and self.smtp_password)

    def get_circuit_breaker_config(self) -> dict[str, Any]:
        """Get circuit breaker configuration as a dictionary."""
        return {
            "enabled": self.circuit_breaker_enabled,
            "failure_threshold": self.circuit_breaker_failure_threshold,
            "recovery_timeout": self.circuit_breaker_recovery_timeout,
            "success_threshold": self.circuit_breaker_success_threshold,
            "half_open_max_calls": self.circuit_breaker_half_open_max_calls,
            "call_timeout": self.circuit_breaker_call_timeout,
        }


# Singleton instance (maintained for backward compatibility)
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get the singleton Settings instance.

    This ensures consistent configuration access across all A2A agents.
    Maintained for backward compatibility with existing code.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the singleton instance. Used for testing."""
    global _settings
    _settings = None


def create_config() -> Settings:
    """
    Create a new Settings instance for dependency injection.

    This function provides a factory method for creating Settings instances
    that can be injected into agents, avoiding the singleton pattern.

    Returns:
        New Settings instance
    """
    return Settings()


def create_config_from_env(env_file: str | None = None) -> Settings:
    """
    Create a new Settings instance from environment file.

    Args:
        env_file: Optional path to environment file

    Returns:
        New Settings instance with environment configuration
    """
    if env_file:
        return Settings(_env_file=env_file)
    return Settings()
