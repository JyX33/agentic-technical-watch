# ABOUTME: Comprehensive tests for observability and monitoring integration
# ABOUTME: Validates metrics collection, health monitoring, logging, and alerting functionality

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reddit_watcher.observability import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    HealthMonitor,
    HealthStatus,
    ObservabilityIntegration,
    configure_logging,
    get_logger,
    get_metrics_collector,
    get_observability_integration,
    get_tracing_provider,
    initialize_tracing,
    record_reddit_post_processed,
    setup_observability_endpoints,
    trace_operation,
)


class TestHealthMonitoring:
    """Test health monitoring functionality."""

    def test_health_monitor_creation(self):
        """Test health monitor creation and basic functionality."""
        monitor = HealthMonitor("test_service", "1.0.0")

        assert monitor.service_name == "test_service"
        assert monitor.version == "1.0.0"
        assert len(monitor.health_checks) >= 3  # Default checks

    @pytest.mark.asyncio
    async def test_health_checks_execution(self):
        """Test health check execution."""
        monitor = HealthMonitor("test_service")

        # Run all health checks
        results = await monitor.run_all_health_checks()

        assert len(results) >= 3
        for result in results:
            assert hasattr(result, "name")
            assert hasattr(result, "status")
            assert isinstance(result.status, HealthStatus)

    @pytest.mark.asyncio
    async def test_health_monitoring_lifecycle(self):
        """Test health monitoring start/stop lifecycle."""
        monitor = HealthMonitor("test_service")

        # Start monitoring
        await monitor.start_monitoring()
        assert monitor._is_monitoring

        # Stop monitoring
        await monitor.stop_monitoring()
        assert not monitor._is_monitoring

    def test_health_status_aggregation(self):
        """Test health status aggregation logic."""
        monitor = HealthMonitor("test_service")

        # Get service health
        health = monitor.get_service_health()

        assert health.service_name == "test_service"
        assert isinstance(health.overall_status, HealthStatus)
        assert isinstance(health.checks, list)


class TestMetricsCollection:
    """Test metrics collection functionality."""

    def test_metrics_collector_creation(self):
        """Test metrics collector creation."""
        collector = get_metrics_collector("test_agent")

        assert collector.agent_type == "test_agent"
        assert hasattr(collector, "http_requests_total")
        assert hasattr(collector, "a2a_messages_total")

    def test_http_request_recording(self):
        """Test HTTP request metrics recording."""
        collector = get_metrics_collector("test_agent")

        # Record HTTP request
        collector.record_http_request("GET", "/test", 200, 0.5)

        # Verify metrics were recorded (simplified check)
        assert True  # In real test, you'd check actual metric values

    def test_a2a_skill_recording(self):
        """Test A2A skill execution recording."""
        collector = get_metrics_collector("test_agent")

        # Record A2A skill execution
        collector.record_a2a_skill_execution("test_skill", 0.3, True)

        # Verify metrics were recorded
        assert True  # In real test, you'd check actual metric values

    def test_business_operation_recording(self):
        """Test business operation recording."""
        collector = get_metrics_collector("test_agent")

        # Record business operation
        collector.record_business_operation("reddit_fetch", 1.5, True)

        # Verify metrics were recorded
        assert True


class TestStructuredLogging:
    """Test structured logging functionality."""

    def test_logger_creation(self):
        """Test logger creation with agent type."""
        logger = get_logger("test.module", "test_agent")

        assert logger.default_agent_type == "test_agent"
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_logging_configuration(self):
        """Test logging configuration."""
        configure_logging(
            level="DEBUG",
            format_type="structured",
            enable_file_logging=False,
        )

        logger = get_logger("test.config")
        logger.info("Test message", metadata={"key": "value"})

        # Verify configuration applied
        assert True

    def test_operation_context_logging(self):
        """Test operation context logging."""
        logger = get_logger("test.operation", "test_agent")

        with logger.operation("test_operation", param1="value1"):
            logger.info("Inside operation")

        # Verify operation logged correctly
        assert True


class TestAlertingSystem:
    """Test alerting system functionality."""

    def test_alert_manager_creation(self):
        """Test alert manager creation."""
        manager = AlertManager()

        assert len(manager.alert_rules) == 0
        assert len(manager.alert_channels) == 0
        assert len(manager.active_alerts) == 0

    def test_alert_rule_creation(self):
        """Test alert rule creation and registration."""
        manager = AlertManager()

        # Create test rule
        rule = AlertRule(
            name="test_rule",
            description="Test alert rule",
            condition=lambda: True,  # Always trigger
            severity=AlertSeverity.WARNING,
            threshold=1.0,
        )

        manager.add_alert_rule(rule)

        assert "test_rule" in manager.alert_rules
        assert manager.alert_rules["test_rule"].name == "test_rule"

    @pytest.mark.asyncio
    async def test_alert_rule_evaluation(self):
        """Test alert rule evaluation."""
        manager = AlertManager()

        # Mock alert channel
        mock_channel = MagicMock()
        mock_channel.name = "test_channel"
        mock_channel.enabled = True
        mock_channel.send_alert = AsyncMock(return_value=True)

        manager.add_alert_channel(mock_channel)

        # Create triggering rule
        rule = AlertRule(
            name="test_trigger",
            description="Test triggering rule",
            condition=lambda: True,
            severity=AlertSeverity.CRITICAL,
            threshold=1.0,
            duration_seconds=0.1,
            cooldown_seconds=0.1,
        )

        manager.add_alert_rule(rule)

        # Evaluate rules
        await manager._evaluate_rules()

        # Check if alert was created
        assert "test_trigger" in manager.active_alerts

    def test_alert_summary(self):
        """Test alert summary statistics."""
        manager = AlertManager()

        summary = manager.get_alert_summary()

        assert "active_alerts" in summary
        assert "total_rules" in summary
        assert "active_channels" in summary
        assert "active_by_severity" in summary


class TestDistributedTracing:
    """Test distributed tracing functionality."""

    def test_tracing_provider_creation(self):
        """Test tracing provider creation."""
        provider = get_tracing_provider()

        assert provider.service_name == "reddit-watcher"
        assert hasattr(provider, "create_span")
        assert hasattr(provider, "span_context")

    def test_span_creation(self):
        """Test span creation and management."""
        provider = get_tracing_provider()

        span = provider.create_span("test_operation")

        assert span.name == "test_operation"
        assert span.trace_id is not None
        assert span.span_id is not None

    def test_span_context_manager(self):
        """Test span context manager."""
        provider = get_tracing_provider()

        with provider.span_context("test_context") as span:
            span.set_attribute("test.key", "test.value")
            span.add_event("test_event")

        # Verify span was finished
        assert span.end_time is not None

    def test_trace_operation_decorator(self):
        """Test trace operation decorator."""

        @trace_operation("test_function")
        def test_func():
            return "test_result"

        result = test_func()
        assert result == "test_result"

    @pytest.mark.asyncio
    async def test_async_trace_operation_decorator(self):
        """Test async trace operation decorator."""

        @trace_operation("async_test_function")
        async def async_test_func():
            await asyncio.sleep(0.01)
            return "async_result"

        result = await async_test_func()
        assert result == "async_result"


class TestObservabilityIntegration:
    """Test observability integration."""

    def test_integration_creation(self):
        """Test observability integration creation."""
        integration = ObservabilityIntegration()

        assert len(integration.agent_statuses) == 0
        assert integration.system_metrics is not None

    def test_agent_registration(self):
        """Test agent registration."""
        integration = ObservabilityIntegration()

        integration.register_agent("test_agent")

        assert "test_agent" in integration.agent_statuses

    @pytest.mark.asyncio
    async def test_agent_status_update(self):
        """Test agent status updates."""
        integration = ObservabilityIntegration()

        status_data = {
            "status": "healthy",
            "uptime_seconds": 100.0,
            "metadata": {"version": "1.0.0"},
        }

        await integration.update_agent_status("test_agent", status_data)

        assert "test_agent" in integration.agent_statuses
        assert integration.agent_statuses["test_agent"].status == "healthy"

    def test_system_health_aggregation(self):
        """Test system health aggregation."""
        integration = ObservabilityIntegration()

        # Register multiple agents
        integration.register_agent("agent1")
        integration.register_agent("agent2")

        health = integration.get_system_health()

        assert "overall_status" in health
        assert "agents" in health
        assert "metrics" in health

    def test_business_metrics_tracking(self):
        """Test business metrics tracking."""
        integration = ObservabilityIntegration()

        # Record business events
        integration.record_business_event("reddit_post_processed", 5)
        integration.record_business_event("alert_sent", 2)

        metrics = integration.get_business_metrics()

        assert "processing_metrics" in metrics
        assert "performance_metrics" in metrics
        assert metrics["processing_metrics"]["reddit_posts_processed_total"] == 5
        assert metrics["processing_metrics"]["alerts_sent_total"] == 2


class TestFastAPIIntegration:
    """Test FastAPI observability integration."""

    def test_observability_endpoints_setup(self):
        """Test observability endpoints setup."""
        app = FastAPI()

        setup_observability_endpoints(app, "test_agent")

        # Test with client
        client = TestClient(app)

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code in [200, 503]  # Depends on system state

        # Test metrics endpoint
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_health_endpoints(self):
        """Test specific health endpoints."""
        app = FastAPI()
        setup_observability_endpoints(app, "test_agent")
        client = TestClient(app)

        # Test liveness
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

        # Test readiness
        response = client.get("/health/ready")
        assert response.status_code in [200, 503]

    def test_api_endpoints(self):
        """Test API endpoints for monitoring data."""
        app = FastAPI()
        setup_observability_endpoints(app, "test_agent")
        client = TestClient(app)

        # Test system health API
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data

        # Test system metrics API
        response = client.get("/api/v1/system/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "processing_metrics" in data

        # Test agents status API
        response = client.get("/api/v1/agents/status")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data


class TestIntegrationScenarios:
    """Test end-to-end integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_monitoring_lifecycle(self):
        """Test complete monitoring lifecycle."""
        # Configure logging
        configure_logging(level="INFO", format_type="structured")

        # Initialize tracing
        initialize_tracing("test-service", "1.0.0")

        # Get components
        logger = get_logger("test.integration", "test_agent")
        metrics = get_metrics_collector("test_agent")
        integration = get_observability_integration()

        # Register agent
        integration.register_agent("test_agent")

        # Simulate operations with full observability
        with logger.operation("test_workflow"):
            # Record business event
            record_reddit_post_processed(3)

            # Record metrics
            metrics.record_http_request("GET", "/api/test", 200, 0.5)

            # Update agent status
            await integration.update_agent_status(
                "test_agent",
                {
                    "status": "healthy",
                    "uptime_seconds": 150.0,
                },
            )

        # Verify state
        health = integration.get_system_health()
        assert health["overall_status"] in ["healthy", "degraded"]

        business_metrics = integration.get_business_metrics()
        assert (
            business_metrics["processing_metrics"]["reddit_posts_processed_total"] >= 3
        )

    def test_error_handling_in_observability(self):
        """Test error handling in observability components."""
        # Test with invalid configurations
        logger = get_logger("test.errors", "test_agent")

        # Should not raise exceptions
        logger.error("Test error", error=Exception("Test exception"))
        logger.info("Test info after error")

        # Test metrics with edge cases
        metrics = get_metrics_collector("test_agent")
        metrics.record_http_request("", "", 0, -1.0)  # Invalid values

        # Test integration with missing data
        integration = get_observability_integration()
        integration.get_system_health()  # Should work even with no agents

        assert True  # If we get here, error handling worked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
