# Test suite for circuit breaker pattern implementation
import asyncio
from datetime import datetime, timedelta

import pytest

from reddit_watcher.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
    get_circuit_breaker_registry,
)


class TestCircuitBreaker:
    """Test suite for CircuitBreaker implementation."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker instance for testing."""
        return CircuitBreaker(
            name="test_circuit",
            failure_threshold=3,
            recovery_timeout=1,  # Short timeout for testing
            success_threshold=2,
            half_open_max_calls=3,
            call_timeout=1.0,
        )

    @pytest.fixture
    def async_func_success(self):
        """Mock successful async function."""

        async def success_func():
            await asyncio.sleep(0.01)
            return {"status": "success", "data": "test"}

        return success_func

    @pytest.fixture
    def async_func_failure(self):
        """Mock failing async function."""

        async def failure_func():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        return failure_func

    @pytest.fixture
    def async_func_timeout(self):
        """Mock timeout async function."""

        async def timeout_func():
            await asyncio.sleep(2.0)  # Longer than call_timeout
            return {"status": "success"}

        return timeout_func

    @pytest.mark.asyncio
    async def test_circuit_breaker_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state."""
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.total_calls == 0

    @pytest.mark.asyncio
    async def test_successful_call_in_closed_state(
        self, circuit_breaker, async_func_success
    ):
        """Test successful call in CLOSED state."""
        result = await circuit_breaker.call(async_func_success)

        assert result == {"status": "success", "data": "test"}
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.total_calls == 1
        assert circuit_breaker.total_successes == 1
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_count_increment(self, circuit_breaker, async_func_failure):
        """Test failure count increment without opening circuit."""
        # Should not open circuit until failure_threshold is reached
        for i in range(2):  # failure_threshold is 3
            with pytest.raises(ValueError):
                await circuit_breaker.call(async_func_failure)
            assert circuit_breaker.failure_count == i + 1
            assert circuit_breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_on_failure_threshold(
        self, circuit_breaker, async_func_failure
    ):
        """Test circuit opens when failure threshold is reached."""
        # Reach failure threshold
        for _ in range(3):  # failure_threshold is 3
            with pytest.raises(ValueError):
                await circuit_breaker.call(async_func_failure)

        assert circuit_breaker.get_state() == CircuitState.OPEN
        assert circuit_breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_rejects_calls_when_open(
        self, circuit_breaker, async_func_success
    ):
        """Test circuit rejects calls when in OPEN state."""
        # Force circuit to OPEN state
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.failure_count = 3
        circuit_breaker.last_failure_time = datetime.now()
        circuit_breaker.next_attempt_time = datetime.now() + timedelta(seconds=10)

        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(async_func_success)

        assert "Circuit breaker 'test_circuit' is OPEN" in str(exc_info.value)
        assert circuit_breaker.total_circuit_open_rejections == 1

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(
        self, circuit_breaker, async_func_failure
    ):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(async_func_failure)

        assert circuit_breaker.get_state() == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)  # recovery_timeout is 1 second

        # Next call should transition to HALF_OPEN
        with pytest.raises(ValueError):  # Still fails but transitions state
            await circuit_breaker.call(async_func_failure)

        assert (
            circuit_breaker.get_state() == CircuitState.OPEN
        )  # Goes back to OPEN on failure

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(
        self, circuit_breaker, async_func_success
    ):
        """Test successful calls in HALF_OPEN state close the circuit."""
        # Manually set to HALF_OPEN state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.success_count = 0

        # Make successful calls to reach success_threshold (2)
        for _ in range(2):
            result = await circuit_breaker.call(async_func_success)
            assert result == {"status": "success", "data": "test"}

        assert circuit_breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_opens_circuit(
        self, circuit_breaker, async_func_failure
    ):
        """Test failure in HALF_OPEN state immediately opens circuit."""
        # Manually set to HALF_OPEN state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.success_count = 1  # Just one success short of closing

        with pytest.raises(ValueError):
            await circuit_breaker.call(async_func_failure)

        assert circuit_breaker.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_max_calls_limit(self, circuit_breaker, async_func_success):
        """Test HALF_OPEN state respects max calls limit."""
        # Manually set to HALF_OPEN state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.half_open_calls = 3  # At max limit

        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(async_func_success)

        assert "max calls" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_handling(self, circuit_breaker, async_func_timeout):
        """Test circuit breaker handles timeouts correctly."""
        with pytest.raises(asyncio.TimeoutError):
            await circuit_breaker.call(async_func_timeout)

        assert circuit_breaker.total_timeouts == 1
        assert circuit_breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_decorator_functionality(self, circuit_breaker, async_func_success):
        """Test circuit breaker works as a decorator."""

        @circuit_breaker
        async def decorated_func():
            return await async_func_success()

        result = await decorated_func()
        assert result == {"status": "success", "data": "test"}
        assert circuit_breaker.total_calls == 1

    @pytest.mark.asyncio
    async def test_reset_functionality(self, circuit_breaker, async_func_failure):
        """Test manual reset functionality."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(async_func_failure)

        assert circuit_breaker.get_state() == CircuitState.OPEN

        # Reset the circuit
        await circuit_breaker.reset()

        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0

    @pytest.mark.asyncio
    async def test_is_call_permitted(self, circuit_breaker):
        """Test is_call_permitted method."""
        # CLOSED state
        assert circuit_breaker.is_call_permitted() is True

        # OPEN state (recent failure)
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.next_attempt_time = datetime.now() + timedelta(seconds=10)
        assert circuit_breaker.is_call_permitted() is False

        # OPEN state (ready for retry)
        circuit_breaker.next_attempt_time = datetime.now() - timedelta(seconds=1)
        assert circuit_breaker.is_call_permitted() is True

        # HALF_OPEN state (within limits)
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.half_open_calls = 1
        assert circuit_breaker.is_call_permitted() is True

        # HALF_OPEN state (at limit)
        circuit_breaker.half_open_calls = 3  # max is 3
        assert circuit_breaker.is_call_permitted() is False

    def test_get_metrics(self, circuit_breaker):
        """Test metrics collection."""
        metrics = circuit_breaker.get_metrics()

        assert metrics["name"] == "test_circuit"
        assert metrics["state"] == CircuitState.CLOSED.value
        assert "configuration" in metrics
        assert "current_counters" in metrics
        assert "total_metrics" in metrics
        assert "timestamps" in metrics
        assert "health_status" in metrics

        # Check configuration
        config = metrics["configuration"]
        assert config["failure_threshold"] == 3
        assert config["recovery_timeout"] == 1
        assert config["success_threshold"] == 2

        # Check health status
        health = metrics["health_status"]
        assert health["is_healthy"] is True
        assert health["can_accept_calls"] is True


class TestCircuitBreakerRegistry:
    """Test suite for CircuitBreakerRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a circuit breaker registry for testing."""
        return CircuitBreakerRegistry()

    @pytest.mark.asyncio
    async def test_get_or_create(self, registry):
        """Test get_or_create functionality."""
        cb1 = await registry.get_or_create("test1", failure_threshold=5)
        cb2 = await registry.get_or_create("test1")  # Should return existing

        assert cb1 is cb2
        assert cb1.name == "test1"
        assert cb1.failure_threshold == 5

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, registry):
        """Test getting non-existent circuit breaker."""
        cb = registry.get("nonexistent")
        assert cb is None

    @pytest.mark.asyncio
    async def test_get_all_metrics(self, registry):
        """Test getting metrics for all circuit breakers."""
        await registry.get_or_create("test1")
        await registry.get_or_create("test2")

        metrics = registry.get_all_metrics()
        assert len(metrics) == 2
        assert "test1" in metrics
        assert "test2" in metrics

    @pytest.mark.asyncio
    async def test_reset_all(self, registry):
        """Test resetting all circuit breakers."""
        cb1 = await registry.get_or_create("test1")
        cb2 = await registry.get_or_create("test2")

        # Manually set some failure counts
        cb1.failure_count = 2
        cb2.failure_count = 3

        await registry.reset_all()

        assert cb1.failure_count == 0
        assert cb2.failure_count == 0

    def test_get_health_summary(self, registry):
        """Test health summary generation."""
        summary = registry.get_health_summary()

        assert "total_circuit_breakers" in summary
        assert "healthy_circuit_breakers" in summary
        assert "health_percentage" in summary
        assert "circuit_breaker_states" in summary


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_global_registry_functions(self):
        """Test global registry access functions."""
        registry = get_circuit_breaker_registry()
        assert isinstance(registry, CircuitBreakerRegistry)

        # Test that we get the same instance
        registry2 = get_circuit_breaker_registry()
        assert registry is registry2

        # Test get_circuit_breaker function
        cb = await get_circuit_breaker("global_test", failure_threshold=10)
        assert cb.name == "global_test"
        assert cb.failure_threshold == 10

    @pytest.mark.asyncio
    async def test_complex_failure_and_recovery_scenario(self):
        """Test complex scenario with failures and recovery."""
        cb = CircuitBreaker(
            name="integration_test",
            failure_threshold=3,
            recovery_timeout=0.1,  # Very short for testing
            success_threshold=2,
            half_open_max_calls=3,
            call_timeout=0.5,
        )

        # Mock functions
        call_count = {"value": 0}

        async def flaky_function():
            call_count["value"] += 1
            if call_count["value"] <= 3:
                raise ValueError("Service unavailable")
            elif call_count["value"] <= 5:
                return {"status": "success", "attempt": call_count["value"]}
            else:
                raise ValueError("Service down again")

        # Phase 1: Fail until circuit opens
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(flaky_function)
        assert cb.get_state() == CircuitState.OPEN

        # Phase 2: Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Phase 3: Service recovers, circuit should close
        for _ in range(2):  # success_threshold is 2
            result = await cb.call(flaky_function)
            assert result["status"] == "success"
        assert cb.get_state() == CircuitState.CLOSED

        # Phase 4: Service fails again, circuit should open
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(flaky_function)
        assert cb.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_concurrent_calls(self):
        """Test circuit breaker with concurrent calls."""
        cb = CircuitBreaker(
            name="concurrent_test",
            failure_threshold=5,
            recovery_timeout=1,
            success_threshold=3,
            call_timeout=1.0,
        )

        call_count = {"value": 0}

        async def concurrent_function():
            call_count["value"] += 1
            await asyncio.sleep(0.01)
            if call_count["value"] % 2 == 0:
                raise ValueError("Intermittent failure")
            return {"status": "success", "call": call_count["value"]}

        # Run multiple concurrent calls
        tasks = []
        for _ in range(10):
            task = asyncio.create_task(cb.call(concurrent_function))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that we got some successes and some failures
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) > 0
        assert len(failures) > 0
        assert cb.total_calls == 10

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_aiohttp_errors(self):
        """Test circuit breaker with aiohttp-style errors."""
        import aiohttp

        cb = CircuitBreaker(
            name="aiohttp_test",
            failure_threshold=2,
            recovery_timeout=0.1,
            expected_exception=aiohttp.ClientError,
        )

        async def http_function():
            raise aiohttp.ClientConnectorError(connection_key=None, os_error=None)

        # Should trigger circuit breaker
        for _ in range(2):
            with pytest.raises(aiohttp.ClientConnectorError):
                await cb.call(http_function)

        assert cb.get_state() == CircuitState.OPEN

        # Non-aiohttp errors should not trigger circuit breaker in this case
        async def other_error_function():
            raise ValueError("Not an aiohttp error")

        cb.state = CircuitState.CLOSED  # Reset for test
        cb.failure_count = 0

        with pytest.raises(ValueError):
            await cb.call(other_error_function)

        # Should still be closed because ValueError is not expected_exception
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0
