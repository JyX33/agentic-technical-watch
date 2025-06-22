# ABOUTME: Resource management tests for HTTP sessions, database connections, and SMTP
# ABOUTME: Validates proper cleanup of connections and prevention of resource leaks

import smtplib
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.agents.server import A2AAgentServer, A2AServiceDiscovery
from reddit_watcher.database.utils import (
    async_close_database_connections,
    close_database_connections,
    get_async_database_engine,
    get_database_engine,
)


class TestHTTPSessionManagement:
    """Test HTTP session resource management."""

    @pytest.mark.asyncio
    async def test_coordinator_http_session_lifecycle(self):
        """Test CoordinatorAgent HTTP session proper initialization and cleanup."""
        coordinator = CoordinatorAgent()

        # Test session initialization
        session = await coordinator._ensure_http_session()
        assert isinstance(session, aiohttp.ClientSession)
        assert not session.closed

        # Test session reuse
        session2 = await coordinator._ensure_http_session()
        assert session is session2  # Should reuse same session

        # Test cleanup
        await coordinator._cleanup_http_session()
        assert coordinator._http_session is None

    @pytest.mark.asyncio
    async def test_coordinator_async_context_manager(self):
        """Test CoordinatorAgent async context manager."""
        coordinator = CoordinatorAgent()

        async with coordinator as agent:
            assert isinstance(agent, CoordinatorAgent)
            # Session should be initialized
            assert coordinator._http_session is not None
            assert not coordinator._http_session.closed

        # After context exit, session should be cleaned up
        assert coordinator._http_session is None

    @pytest.mark.asyncio
    async def test_alert_agent_http_session_lifecycle(self):
        """Test AlertAgent HTTP session proper initialization and cleanup."""
        alert_agent = AlertAgent()

        # Test session initialization
        session = await alert_agent._ensure_http_session()
        assert isinstance(session, aiohttp.ClientSession)
        assert not session.closed

        # Test cleanup
        await alert_agent._cleanup_http_session()
        assert alert_agent._http_session is None

    @pytest.mark.asyncio
    async def test_alert_agent_async_context_manager(self):
        """Test AlertAgent async context manager."""
        alert_agent = AlertAgent()

        async with alert_agent as agent:
            assert isinstance(agent, AlertAgent)
            # Session should be initialized
            assert alert_agent._http_session is not None
            assert not alert_agent._http_session.closed

        # After context exit, session should be cleaned up
        assert alert_agent._http_session is None

    @pytest.mark.asyncio
    async def test_http_session_connection_pooling(self):
        """Test HTTP session connection pooling configuration."""
        coordinator = CoordinatorAgent()
        session = await coordinator._ensure_http_session()

        # Check connector configuration
        connector = session.connector
        assert isinstance(connector, aiohttp.TCPConnector)
        assert connector.limit == 100  # Total pool size
        assert connector.limit_per_host == 30  # Per host limit
        assert connector._keepalive_timeout == 30
        assert connector._cleanup_closed

        await coordinator._cleanup_http_session()


class TestDatabaseConnectionManagement:
    """Test database connection resource management."""

    def test_database_engine_configuration(self):
        """Test database engine connection pooling configuration."""
        engine = get_database_engine()

        # Check pool configuration
        assert engine.pool.size() == 20  # pool_size
        assert (
            engine.pool.overflow() + engine.pool.size() >= 30
        )  # max_overflow capacity
        assert engine.pool.pre_ping  # pool_pre_ping
        assert engine.pool.recycle == 3600  # pool_recycle

    def test_async_database_engine_configuration(self):
        """Test async database engine connection pooling configuration."""
        async_engine = get_async_database_engine()

        # Check pool configuration
        assert async_engine.pool.size() == 20  # pool_size
        assert (
            async_engine.pool.overflow() + async_engine.pool.size() >= 30
        )  # max_overflow capacity
        assert async_engine.pool.pre_ping  # pool_pre_ping
        assert async_engine.pool.recycle == 3600  # pool_recycle

    def test_sync_database_connection_cleanup(self):
        """Test synchronous database connection cleanup."""
        # Get engine to initialize it
        engine = get_database_engine()
        assert engine is not None

        # Test cleanup
        close_database_connections()

        # Engine should be disposed
        # Note: We can't easily test disposal state, but we can test that
        # the global reference is reset
        from reddit_watcher.database.utils import _engine

        assert _engine is None

    @pytest.mark.asyncio
    async def test_async_database_connection_cleanup(self):
        """Test asynchronous database connection cleanup."""
        # Get engine to initialize it
        async_engine = get_async_database_engine()
        assert async_engine is not None

        # Test cleanup
        await async_close_database_connections()

        # Engine should be disposed
        from reddit_watcher.database.utils import _async_engine

        assert _async_engine is None


class TestRedisConnectionManagement:
    """Test Redis connection resource management."""

    @pytest.mark.asyncio
    async def test_redis_service_discovery_cleanup(self):
        """Test Redis service discovery connection cleanup."""
        discovery = A2AServiceDiscovery()

        # Mock Redis client
        mock_redis = AsyncMock()
        discovery.redis_client = mock_redis

        # Test cleanup
        await discovery.cleanup()

        # Verify aclose was called and client was reset
        mock_redis.aclose.assert_called_once()
        assert discovery.redis_client is None

    @pytest.mark.asyncio
    async def test_a2a_server_resource_cleanup(self):
        """Test A2AAgentServer resource cleanup."""
        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent.agent_type = "test"
        mock_agent.name = "Test Agent"
        mock_agent.description = "Test description"
        mock_agent.version = "1.0.0"

        server = A2AAgentServer(mock_agent)

        # Mock Redis discovery to avoid connection issues
        with (
            patch.object(server.discovery, "initialize") as mock_init,
            patch.object(server.discovery, "register_agent") as mock_register,
            patch.object(server.discovery, "deregister_agent") as mock_deregister,
            patch.object(server.discovery, "cleanup") as mock_cleanup,
        ):
            # Test async context manager
            async with server as srv:
                assert isinstance(srv, A2AAgentServer)
                mock_init.assert_called_once()
                mock_register.assert_called_once_with(mock_agent)

            # Verify cleanup was called
            mock_deregister.assert_called_once_with("test")
            mock_cleanup.assert_called_once()


class TestSMTPConnectionManagement:
    """Test SMTP connection resource management."""

    @pytest.mark.asyncio
    async def test_smtp_connection_cleanup_on_success(self):
        """Test SMTP connection cleanup on successful email send."""
        alert_agent = AlertAgent()

        # Mock SMTP server
        mock_server = MagicMock()

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.return_value = mock_server

            # Create test message
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")

            # Test sync SMTP send
            alert_agent._send_smtp_sync(msg, ["test@example.com"])

            # Verify SMTP operations and cleanup
            mock_smtp_class.assert_called_once()
            mock_server.set_debuglevel.assert_called_with(0)
            mock_server.send_message.assert_called_once_with(msg)
            mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_connection_cleanup_on_error(self):
        """Test SMTP connection cleanup on error."""
        alert_agent = AlertAgent()

        # Mock SMTP server that raises exception
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Test error")

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.return_value = mock_server

            # Create test message
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")

            # Test sync SMTP send with error
            with pytest.raises(smtplib.SMTPException):
                alert_agent._send_smtp_sync(msg, ["test@example.com"])

            # Verify cleanup was still called
            mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_connection_force_cleanup(self):
        """Test SMTP connection force cleanup when quit fails."""
        alert_agent = AlertAgent()

        # Mock SMTP server where quit fails
        mock_server = MagicMock()
        mock_server.quit.side_effect = Exception("Quit failed")

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.return_value = mock_server

            # Create test message
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")

            # Test sync SMTP send
            alert_agent._send_smtp_sync(msg, ["test@example.com"])

            # Verify both quit and close were called
            mock_server.quit.assert_called_once()
            mock_server.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_health_check_connection_cleanup(self):
        """Test SMTP health check connection cleanup."""
        alert_agent = AlertAgent()

        # Mock SMTP server
        mock_server = MagicMock()

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.return_value = mock_server

            # Test SMTP connection test
            result = alert_agent._test_smtp_connection()

            # Verify operations and cleanup
            mock_smtp_class.assert_called_once()
            mock_server.set_debuglevel.assert_called_with(0)
            mock_server.noop.assert_called_once()
            mock_server.quit.assert_called_once()
            assert result == "connected"


class TestResourceLeakPrevention:
    """Test prevention of resource leaks."""

    @pytest.mark.asyncio
    async def test_multiple_session_creation_cleanup(self):
        """Test that multiple session creations don't leak."""
        coordinator = CoordinatorAgent()

        # Create and cleanup multiple sessions
        for _ in range(5):
            session = await coordinator._ensure_http_session()
            assert not session.closed
            await coordinator._cleanup_http_session()
            assert coordinator._http_session is None

    @pytest.mark.asyncio
    async def test_exception_during_cleanup(self):
        """Test resource cleanup even when exceptions occur."""
        coordinator = CoordinatorAgent()

        # Initialize session
        session = await coordinator._ensure_http_session()

        # Mock session.close to raise exception
        with patch.object(session, "close", side_effect=Exception("Close failed")):
            # Cleanup should not raise exception
            await coordinator._cleanup_http_session()
            # Session reference should still be cleared
            assert coordinator._http_session is None

    @pytest.mark.asyncio
    async def test_cleanup_with_no_active_connections(self):
        """Test cleanup when no active connections exist."""
        coordinator = CoordinatorAgent()

        # Test cleanup with no session
        await coordinator._cleanup_http_session()  # Should not raise
        assert coordinator._http_session is None

        alert_agent = AlertAgent()
        await alert_agent._cleanup_http_session()  # Should not raise
        assert alert_agent._http_session is None


@pytest.fixture(autouse=True)
def cleanup_global_connections():
    """Cleanup global connections after each test."""
    yield
    # Cleanup after test
    try:
        close_database_connections()
    except Exception:
        pass
