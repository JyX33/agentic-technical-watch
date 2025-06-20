# ABOUTME: Unit tests for the configuration module
# ABOUTME: Tests Pydantic BaseSettings validation, .env file support, and singleton pattern

import os
import tempfile
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from reddit_watcher.config import Settings, get_settings, reset_settings


class TestSettings:
    """Test the Settings configuration class."""

    def setup_method(self):
        """Reset settings singleton before each test."""
        reset_settings()

    def test_default_settings(self):
        """Test that default settings are valid."""
        settings = Settings()

        assert settings.app_name == "Reddit Technical Watcher"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.agent_port == 8000
        assert settings.monitoring_interval_hours == 4
        assert settings.relevance_threshold == 0.7

    def test_database_url_validation(self):
        """Test database URL validation."""
        # Valid PostgreSQL URLs
        valid_urls = [
            "postgresql://user:pass@localhost:5432/db",
            "postgresql+psycopg2://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ]

        for url in valid_urls:
            settings = Settings(database_url=url)
            assert settings.database_url == url

        # Invalid URLs
        invalid_urls = [
            "",
            "mysql://user:pass@localhost:3306/db",
            "sqlite:///test.db",
            "invalid-url",
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                Settings(database_url=url)

    def test_redis_url_validation(self):
        """Test Redis URL validation."""
        # Valid Redis URLs
        valid_urls = [
            "redis://localhost:6379/0",
            "rediss://user:pass@host:6380/1",
            "redis://localhost:6379",
        ]

        for url in valid_urls:
            settings = Settings(redis_url=url)
            assert settings.redis_url == url

        # Invalid URLs
        invalid_urls = [
            "",
            "http://localhost:6379",
            "postgresql://localhost:5432/db",
            "invalid-url",
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                Settings(redis_url=url)

    def test_relevance_threshold_validation(self):
        """Test relevance threshold validation."""
        # Valid thresholds
        valid_thresholds = [0.0, 0.5, 0.7, 1.0]

        for threshold in valid_thresholds:
            settings = Settings(relevance_threshold=threshold)
            assert settings.relevance_threshold == threshold

        # Invalid thresholds
        invalid_thresholds = [-0.1, 1.1, 2.0, -1.0]

        for threshold in invalid_thresholds:
            with pytest.raises(ValidationError):
                Settings(relevance_threshold=threshold)

    def test_agent_port_validation(self):
        """Test agent port validation."""
        # Valid ports
        valid_ports = [1024, 8000, 8080, 65535]

        for port in valid_ports:
            settings = Settings(agent_port=port)
            assert settings.agent_port == port

        # All integer ports are currently accepted (no validation implemented)

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        with patch.dict(
            os.environ,
            {
                "DEBUG": "true",
                "LOG_LEVEL": "DEBUG",
                "AGENT_PORT": "9000",
                "MONITORING_INTERVAL_HOURS": "6",
            },
        ):
            settings = Settings()

            assert settings.debug is True
            assert settings.log_level == "DEBUG"
            assert settings.agent_port == 9000
            assert settings.monitoring_interval_hours == 6

    def test_env_file_support(self):
        """Test loading configuration from .env file."""
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEBUG=true\n")
            f.write("LOG_LEVEL=DEBUG\n")
            f.write("AGENT_PORT=7000\n")
            f.write("REDDIT_CLIENT_ID=test_client_id\n")
            f.write("GEMINI_API_KEY=test_api_key\n")
            env_file = f.name

        try:
            # Test with explicit env_file parameter
            settings = Settings(_env_file=env_file)

            assert settings.debug is True
            assert settings.log_level == "DEBUG"
            assert settings.agent_port == 7000
            assert settings.reddit_client_id == "test_client_id"
            assert settings.gemini_api_key == "test_api_key"

        finally:
            os.unlink(env_file)

    def test_get_agent_urls(self):
        """Test get_agent_urls method."""
        settings = Settings()
        urls = settings.get_agent_urls()

        expected_urls = {
            "retrieval": "http://localhost:8001",
            "filter": "http://localhost:8002",
            "summarise": "http://localhost:8003",
            "alert": "http://localhost:8004",
            "coordinator": "http://localhost:8000",
        }

        assert urls == expected_urls

    def test_utility_methods(self):
        """Test utility methods for checking configuration state."""
        # Test defaults
        settings = Settings()

        assert settings.is_production() is True  # debug=False by default
        assert settings.has_reddit_credentials() is False  # empty by default
        assert settings.has_gemini_credentials() is False  # empty by default
        assert settings.has_slack_webhook() is False  # empty by default
        assert settings.has_smtp_config() is False  # empty by default

        # Test with credentials
        settings = Settings(
            debug=True,
            reddit_client_id="test_client_id",
            reddit_client_secret="test_client_secret",
            gemini_api_key="test_api_key",
            slack_webhook_url="https://hooks.slack.com/test",
            smtp_server="smtp.gmail.com",
            smtp_username="test@example.com",
            smtp_password="test_password",
        )

        assert settings.is_production() is False  # debug=True
        assert settings.has_reddit_credentials() is True
        assert settings.has_gemini_credentials() is True
        assert settings.has_slack_webhook() is True
        assert settings.has_smtp_config() is True


class TestSettingsSingleton:
    """Test the singleton pattern for Settings."""

    def setup_method(self):
        """Reset settings singleton before each test."""
        reset_settings()

    def test_singleton_pattern(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
        assert id(settings1) == id(settings2)

    def test_reset_settings(self):
        """Test that reset_settings creates a new instance."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2
        assert id(settings1) != id(settings2)

    def test_singleton_with_environment_changes(self):
        """Test singleton behavior with environment variable changes."""
        # Get initial settings
        settings1 = get_settings()
        initial_debug = settings1.debug

        # Change environment and reset
        with patch.dict(os.environ, {"DEBUG": "true"}):
            reset_settings()
            settings2 = get_settings()

            assert settings1 is not settings2
            assert settings2.debug is True
            assert settings2.debug != initial_debug


class TestSettingsIntegration:
    """Integration tests for Settings with external dependencies."""

    def setup_method(self):
        """Reset settings singleton before each test."""
        reset_settings()

    def test_docker_compose_environment(self):
        """Test configuration for Docker Compose environment."""
        docker_env = {
            "DATABASE_URL": "postgresql://postgres:postgres@db:5432/reddit_watcher",
            "REDIS_URL": "redis://redis:6379/0",
            "AGENT_TYPE": "coordinator",
            "AGENT_PORT": "8000",
        }

        with patch.dict(os.environ, docker_env):
            settings = Settings()

            assert "db:5432" in settings.database_url
            assert "redis:6379" in settings.redis_url
            assert settings.agent_type == "coordinator"
            assert settings.agent_port == 8000

    def test_production_configuration(self):
        """Test typical production configuration."""
        prod_env = {
            "DEBUG": "false",
            "LOG_LEVEL": "INFO",
            "DATABASE_URL": "postgresql://user:pass@prod-db:5432/reddit_watcher",
            "REDIS_URL": "rediss://user:pass@prod-redis:6380/0",
            "REDDIT_CLIENT_ID": "prod_client_id",
            "REDDIT_CLIENT_SECRET": "prod_client_secret",
            "GEMINI_API_KEY": "prod_gemini_key",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/prod",
            "MONITORING_INTERVAL_HOURS": "4",
        }

        with patch.dict(os.environ, prod_env):
            settings = Settings()

            assert settings.is_production() is True
            assert settings.has_reddit_credentials() is True
            assert settings.has_gemini_credentials() is True
            assert settings.has_slack_webhook() is True
            assert settings.monitoring_interval_hours == 4
