# Integration tests for CoordinatorAgent circuit breaker functionality
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.circuit_breaker import CircuitState
from reddit_watcher.config import Settings


class TestCoordinatorAgentCircuitBreaker:
    """Test circuit breaker integration in CoordinatorAgent."""

    @pytest.fixture
    def settings_with_circuit_breaker(self):
        """Settings with circuit breaker enabled."""
        return Settings(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_recovery_timeout=1,
            circuit_breaker_success_threshold=1,
            circuit_breaker_half_open_max_calls=2,
            circuit_breaker_call_timeout=5.0,
            database_url="postgresql://test:test@localhost:5432/test",
            redis_url="redis://localhost:6379/0",
        )

    @pytest.fixture
    def settings_without_circuit_breaker(self):
        """Settings with circuit breaker disabled."""
        return Settings(
            circuit_breaker_enabled=False,
            database_url="postgresql://test:test@localhost:5432/test",
            redis_url="redis://localhost:6379/0",
        )

    @pytest.fixture
    def coordinator_with_cb(self, settings_with_circuit_breaker):
        """CoordinatorAgent with circuit breaker enabled."""
        return CoordinatorAgent(settings_with_circuit_breaker)

    @pytest.fixture
    def coordinator_without_cb(self, settings_without_circuit_breaker):
        """CoordinatorAgent with circuit breaker disabled."""
        return CoordinatorAgent(settings_without_circuit_breaker)

    @pytest.mark.asyncio
    async def test_circuit_breaker_initialization(self, coordinator_with_cb):
        """Test that circuit breakers are properly initialized."""
        assert coordinator_with_cb._circuit_breakers_enabled is True
        assert coordinator_with_cb._circuit_breaker_config["failure_threshold"] == 2
        assert coordinator_with_cb._circuit_breaker_config["recovery_timeout"] == 1

        # Check that registry is accessible
        assert coordinator_with_cb._circuit_breaker_registry is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_disabled(self, coordinator_without_cb):
        """Test behavior when circuit breakers are disabled."""
        assert coordinator_without_cb._circuit_breakers_enabled is False

        # Should still have registry but not use it
        assert coordinator_without_cb._circuit_breaker_registry is not None

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_for_agent(self, coordinator_with_cb):
        """Test getting circuit breaker for specific agent."""
        cb = await coordinator_with_cb._get_circuit_breaker("retrieval")

        assert cb is not None
        assert cb.name == "coordinator_to_retrieval"
        assert cb.failure_threshold == 2
        assert cb.recovery_timeout == 1

        # Getting the same agent again should return the same instance
        cb2 = await coordinator_with_cb._get_circuit_breaker("retrieval")
        assert cb is cb2

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_disabled(self, coordinator_without_cb):
        """Test getting circuit breaker when disabled."""
        cb = await coordinator_without_cb._get_circuit_breaker("retrieval")
        assert cb is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_status_skill_enabled(self, coordinator_with_cb):
        """Test circuit breaker status skill when enabled."""
        result = await coordinator_with_cb._get_circuit_breaker_status({})

        assert result["skill"] == "get_circuit_breaker_status"
        assert result["status"] == "success"
        assert result["result"]["configuration"]["enabled"] is True
        assert "health_summary" in result["result"]
        assert "detailed_metrics" in result["result"]

    @pytest.mark.asyncio
    async def test_circuit_breaker_status_skill_disabled(self, coordinator_without_cb):
        """Test circuit breaker status skill when disabled."""
        result = await coordinator_without_cb._get_circuit_breaker_status({})

        assert result["skill"] == "get_circuit_breaker_status"
        assert result["status"] == "success"
        assert result["result"]["enabled"] is False
        assert result["result"]["message"] == "Circuit breakers are disabled"

    @pytest.mark.asyncio
    async def test_health_check_includes_circuit_breaker_info(
        self, coordinator_with_cb
    ):
        """Test that health check includes circuit breaker information."""
        with patch.object(
            coordinator_with_cb, "_check_single_agent_health", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = {"status": "healthy"}

            with patch.object(
                coordinator_with_cb,
                "_get_recent_workflow_status",
                new_callable=AsyncMock,
            ) as mock_workflow:
                mock_workflow.return_value = {"recent_count": 0, "workflows": []}

                result = await coordinator_with_cb._health_check({})

        assert result["status"] == "success"
        circuit_breaker_info = result["result"]["coordinator_specific"][
            "circuit_breakers"
        ]
        assert circuit_breaker_info["enabled"] is True
        assert "total_circuit_breakers" in circuit_breaker_info

    @pytest.mark.asyncio
    async def test_make_agent_request_success(self, coordinator_with_cb):
        """Test successful agent request through circuit breaker."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"status": "success", "data": "test"}
        )

        with patch.object(coordinator_with_cb, "_ensure_http_session") as mock_session:
            mock_http_session = AsyncMock()
            mock_http_session.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value = mock_http_session

            result = await coordinator_with_cb._make_agent_request(
                "retrieval", "http://localhost:8001", {"skill": "test"}, 1
            )

        assert result == {"status": "success", "data": "test"}

    @pytest.mark.asyncio
    async def test_make_agent_request_http_error(self, coordinator_with_cb):
        """Test agent request with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.request_info = MagicMock()
        mock_response.history = ()

        with patch.object(coordinator_with_cb, "_ensure_http_session") as mock_session:
            mock_http_session = AsyncMock()
            mock_http_session.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value = mock_http_session

            with pytest.raises(aiohttp.ClientResponseError):
                await coordinator_with_cb._make_agent_request(
                    "retrieval", "http://localhost:8001", {"skill": "test"}, 1
                )

    @pytest.mark.asyncio
    async def test_make_agent_request_timeout(self, coordinator_with_cb):
        """Test agent request timeout."""
        with patch.object(coordinator_with_cb, "_ensure_http_session") as mock_session:
            mock_http_session = AsyncMock()
            mock_http_session.post.side_effect = TimeoutError()
            mock_session.return_value = mock_http_session

            with pytest.raises(asyncio.TimeoutError):
                await coordinator_with_cb._make_agent_request(
                    "retrieval", "http://localhost:8001", {"skill": "test"}, 1
                )

    @pytest.mark.asyncio
    async def test_delegate_to_agent_with_circuit_breaker_success(
        self, coordinator_with_cb
    ):
        """Test successful delegation with circuit breaker."""
        with patch.object(
            coordinator_with_cb, "_create_agent_task", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = 1

            with patch.object(
                coordinator_with_cb, "_complete_agent_task", new_callable=AsyncMock
            ) as mock_complete:
                with patch.object(
                    coordinator_with_cb, "_make_agent_request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = {"status": "success", "data": "test"}

                    result = await coordinator_with_cb._delegate_to_agent(
                        "retrieval", {"skill": "test"}, 1
                    )

        assert result == {"status": "success", "data": "test"}
        mock_complete.assert_called_once_with(
            1, "completed", {"status": "success", "data": "test"}
        )

    @pytest.mark.asyncio
    async def test_delegate_to_agent_circuit_breaker_failure(self, coordinator_with_cb):
        """Test delegation when circuit breaker fails."""
        # First, open the circuit breaker by simulating failures
        cb = await coordinator_with_cb._get_circuit_breaker("retrieval")

        # Manually open the circuit
        cb.state = CircuitState.OPEN
        cb.failure_count = 5
        cb.last_failure_time = asyncio.get_event_loop().time()
        cb.next_attempt_time = cb.last_failure_time + 10  # 10 seconds in future

        with patch.object(
            coordinator_with_cb, "_create_agent_task", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = 1

            with patch.object(
                coordinator_with_cb, "_complete_agent_task", new_callable=AsyncMock
            ) as mock_complete:
                result = await coordinator_with_cb._delegate_to_agent(
                    "retrieval", {"skill": "test"}, 1
                )

        assert result["status"] == "error"
        assert "Circuit breaker is open" in result["error"]
        mock_complete.assert_called_once()
        call_args = mock_complete.call_args[0]
        assert call_args[1] == "failed"  # status
        assert "circuit_breaker" in call_args[2]  # result_data

    @pytest.mark.asyncio
    async def test_delegate_to_agent_without_circuit_breaker(
        self, coordinator_without_cb
    ):
        """Test delegation without circuit breaker uses fallback method."""
        with patch.object(
            coordinator_without_cb,
            "_delegate_to_agent_without_circuit_breaker",
            new_callable=AsyncMock,
        ) as mock_fallback:
            mock_fallback.return_value = {"status": "success", "data": "fallback"}

            with patch.object(
                coordinator_without_cb, "_create_agent_task", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = 1

                result = await coordinator_without_cb._delegate_to_agent(
                    "retrieval", {"skill": "test"}, 1
                )

        assert result == {"status": "success", "data": "fallback"}
        mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions_during_delegation(
        self, coordinator_with_cb
    ):
        """Test circuit breaker state transitions during multiple delegations."""
        call_count = {"value": 0}

        async def mock_agent_request(*args, **kwargs):
            call_count["value"] += 1
            if call_count["value"] <= 2:  # First 2 calls fail
                raise aiohttp.ClientError("Service unavailable")
            else:  # Subsequent calls succeed
                return {"status": "success", "call": call_count["value"]}

        with patch.object(
            coordinator_with_cb, "_create_agent_task", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = 1

            with patch.object(
                coordinator_with_cb, "_complete_agent_task", new_callable=AsyncMock
            ):
                with patch.object(
                    coordinator_with_cb,
                    "_make_agent_request",
                    side_effect=mock_agent_request,
                ):
                    # First call - should fail but circuit stays closed
                    result1 = await coordinator_with_cb._delegate_to_agent(
                        "retrieval", {"skill": "test"}, 1
                    )
                    assert result1["status"] == "error"

                    cb = await coordinator_with_cb._get_circuit_breaker("retrieval")
                    assert (
                        cb.get_state() == CircuitState.CLOSED
                    )  # Still closed, only 1 failure

                    # Second call - should fail and open circuit (failure_threshold=2)
                    result2 = await coordinator_with_cb._delegate_to_agent(
                        "retrieval", {"skill": "test"}, 1
                    )
                    assert result2["status"] == "error"
                    assert cb.get_state() == CircuitState.OPEN  # Now open

                    # Wait for recovery timeout
                    await asyncio.sleep(1.1)  # recovery_timeout is 1 second

                    # Third call - should succeed and close circuit
                    result3 = await coordinator_with_cb._delegate_to_agent(
                        "retrieval", {"skill": "test"}, 1
                    )
                    assert result3 == {"status": "success", "call": 3}
                    assert cb.get_state() == CircuitState.CLOSED  # Closed again

    @pytest.mark.asyncio
    async def test_multiple_agents_independent_circuit_breakers(
        self, coordinator_with_cb
    ):
        """Test that different agents have independent circuit breakers."""
        # Get circuit breakers for different agents
        cb_retrieval = await coordinator_with_cb._get_circuit_breaker("retrieval")
        cb_filter = await coordinator_with_cb._get_circuit_breaker("filter")

        assert cb_retrieval is not cb_filter
        assert cb_retrieval.name == "coordinator_to_retrieval"
        assert cb_filter.name == "coordinator_to_filter"

        # Manually fail one circuit breaker
        cb_retrieval.state = CircuitState.OPEN

        assert cb_retrieval.get_state() == CircuitState.OPEN
        assert cb_filter.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics_collection(self, coordinator_with_cb):
        """Test that circuit breaker metrics are properly collected."""
        # Create some circuit breakers by calling the method
        await coordinator_with_cb._get_circuit_breaker("retrieval")
        await coordinator_with_cb._get_circuit_breaker("filter")

        # Get status with metrics
        result = await coordinator_with_cb._get_circuit_breaker_status({})

        detailed_metrics = result["result"]["detailed_metrics"]
        assert "coordinator_to_retrieval" in detailed_metrics
        assert "coordinator_to_filter" in detailed_metrics

        # Check metric structure
        retrieval_metrics = detailed_metrics["coordinator_to_retrieval"]
        assert "configuration" in retrieval_metrics
        assert "current_counters" in retrieval_metrics
        assert "total_metrics" in retrieval_metrics
        assert "health_status" in retrieval_metrics

    @pytest.mark.asyncio
    async def test_health_status_includes_circuit_breaker_summary(
        self, coordinator_with_cb
    ):
        """Test that get_health_status includes circuit breaker information."""
        # Create some circuit breakers
        await coordinator_with_cb._get_circuit_breaker("retrieval")
        await coordinator_with_cb._get_circuit_breaker("filter")

        health_status = coordinator_with_cb.get_health_status()

        cb_info = health_status["coordinator_specific"]["circuit_breakers"]
        assert cb_info["enabled"] is True
        assert cb_info["configuration"]["failure_threshold"] == 2

        health_summary = cb_info["health_summary"]
        assert "total_circuit_breakers" in health_summary
        assert health_summary["total_circuit_breakers"] == 2
