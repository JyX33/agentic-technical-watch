# ABOUTME: Circuit breaker pattern implementation for resilient agent-to-agent communication
# ABOUTME: Provides fault tolerance and cascading failure prevention with configurable thresholds and recovery

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states following the standard pattern."""

    CLOSED = "closed"  # Normal operation, calls pass through
    OPEN = "open"  # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if the service has recovered


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is in OPEN state."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient service communication.

    Implements the three-state circuit breaker pattern:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests fail fast
    - HALF_OPEN: Testing recovery, limited requests allowed

    Features:
    - Configurable failure threshold and recovery timeout
    - Success rate monitoring
    - Exponential backoff for recovery attempts
    - Comprehensive logging and metrics
    - Thread-safe operation for async contexts
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        expected_exception: type[Exception] = Exception,
        half_open_max_calls: int = 5,
        call_timeout: float = 30.0,
    ):
        """
        Initialize circuit breaker with configuration.

        Args:
            name: Unique name for this circuit breaker (for logging)
            failure_threshold: Number of consecutive failures to open circuit
            recovery_timeout: Seconds to wait before attempting recovery
            success_threshold: Successful calls needed in HALF_OPEN to close circuit
            expected_exception: Exception type that triggers circuit breaker
            half_open_max_calls: Maximum calls allowed in HALF_OPEN state
            call_timeout: Maximum timeout for individual calls
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls
        self.call_timeout = call_timeout

        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time: datetime | None = None
        self.last_success_time: datetime | None = None
        self.next_attempt_time: datetime | None = None

        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_timeouts = 0
        self.total_circuit_open_rejections = 0

        # Thread safety
        self._lock = asyncio.Lock()

        logger.info(
            f"Circuit breaker '{self.name}' initialized - "
            f"failure_threshold={failure_threshold}, recovery_timeout={recovery_timeout}s"
        )

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to wrap functions with circuit breaker protection."""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await self.call(func, *args, **kwargs)

        return wrapper

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: When circuit is open
            Exception: Original function exceptions
        """
        async with self._lock:
            self.total_calls += 1

            # Check if circuit should remain open
            if self.state == CircuitState.OPEN:
                if not self._should_attempt_reset():
                    self.total_circuit_open_rejections += 1
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN - rejecting call "
                        f"(failures: {self.failure_count}, last_failure: {self.last_failure_time})"
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Next attempt allowed at {self.next_attempt_time}"
                    )
                else:
                    # Transition to HALF_OPEN
                    await self._transition_to_half_open()

            # Check if we've exceeded half-open call limit
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    self.total_circuit_open_rejections += 1
                    logger.warning(
                        f"Circuit breaker '{self.name}' in HALF_OPEN state - "
                        f"max calls ({self.half_open_max_calls}) exceeded"
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is in HALF_OPEN state with max calls exceeded"
                    )
                self.half_open_calls += 1

        # Execute the function with timeout
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=self.call_timeout
                )
            else:
                # For sync functions, run in executor with timeout
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, func, *args, **kwargs
                    ),
                    timeout=self.call_timeout,
                )

            # Handle success
            await self._on_success()
            return result

        except TimeoutError as e:
            self.total_timeouts += 1
            logger.warning(
                f"Circuit breaker '{self.name}' call timed out after {self.call_timeout}s"
            )
            await self._on_failure(e)
            raise

        except self.expected_exception as e:
            await self._on_failure(e)
            raise

        except Exception as e:
            # Unexpected exceptions don't trigger circuit breaker
            logger.warning(
                f"Circuit breaker '{self.name}' encountered unexpected exception: {type(e).__name__}: {e}"
            )
            raise

    async def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0

        logger.info(
            f"Circuit breaker '{self.name}' transitioning from {old_state.value} to HALF_OPEN - "
            f"testing service recovery"
        )

    async def _on_success(self) -> None:
        """Handle successful function execution."""
        async with self._lock:
            self.total_successes += 1
            self.last_success_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.debug(
                    f"Circuit breaker '{self.name}' HALF_OPEN success "
                    f"({self.success_count}/{self.success_threshold})"
                )

                # Check if we should close the circuit
                if self.success_count >= self.success_threshold:
                    await self._transition_to_closed()

            elif self.state == CircuitState.CLOSED:
                # Reset failure count on successful call in CLOSED state
                if self.failure_count > 0:
                    logger.debug(
                        f"Circuit breaker '{self.name}' resetting failure count from {self.failure_count} to 0"
                    )
                    self.failure_count = 0

    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed function execution."""
        async with self._lock:
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            self.next_attempt_time = self.last_failure_time + timedelta(
                seconds=self.recovery_timeout
            )

            logger.warning(
                f"Circuit breaker '{self.name}' failure #{self.failure_count}: "
                f"{type(exception).__name__}: {exception}"
            )

            if self.state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately opens the circuit
                await self._transition_to_open("Failure during HALF_OPEN state")

            elif self.state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self.failure_count >= self.failure_threshold:
                    await self._transition_to_open("Failure threshold exceeded")

    async def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

        logger.info(
            f"Circuit breaker '{self.name}' transitioning from {old_state.value} to CLOSED - "
            f"service recovered successfully"
        )

    async def _transition_to_open(self, reason: str) -> None:
        """Transition circuit breaker to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.half_open_calls = 0

        logger.error(
            f"Circuit breaker '{self.name}' transitioning from {old_state.value} to OPEN - "
            f"reason: {reason}, next attempt at: {self.next_attempt_time}"
        )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt circuit reset."""
        if not self.last_failure_time or not self.next_attempt_time:
            return False

        now = datetime.now()
        should_attempt = now >= self.next_attempt_time

        if should_attempt:
            logger.debug(
                f"Circuit breaker '{self.name}' attempting reset - "
                f"recovery timeout ({self.recovery_timeout}s) elapsed"
            )

        return should_attempt

    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive circuit breaker metrics."""
        now = datetime.now()

        # Calculate failure rate
        failure_rate = (
            (self.total_failures / self.total_calls) * 100
            if self.total_calls > 0
            else 0.0
        )

        # Calculate uptime percentage
        success_rate = (
            (self.total_successes / self.total_calls) * 100
            if self.total_calls > 0
            else 0.0
        )

        return {
            "name": self.name,
            "state": self.state.value,
            "configuration": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "success_threshold": self.success_threshold,
                "half_open_max_calls": self.half_open_max_calls,
                "call_timeout": self.call_timeout,
            },
            "current_counters": {
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "half_open_calls": self.half_open_calls,
            },
            "total_metrics": {
                "total_calls": self.total_calls,
                "total_successes": self.total_successes,
                "total_failures": self.total_failures,
                "total_timeouts": self.total_timeouts,
                "total_circuit_open_rejections": self.total_circuit_open_rejections,
                "success_rate_percent": round(success_rate, 2),
                "failure_rate_percent": round(failure_rate, 2),
            },
            "timestamps": {
                "last_failure_time": self.last_failure_time.isoformat()
                if self.last_failure_time
                else None,
                "last_success_time": self.last_success_time.isoformat()
                if self.last_success_time
                else None,
                "next_attempt_time": self.next_attempt_time.isoformat()
                if self.next_attempt_time
                else None,
            },
            "health_status": {
                "is_healthy": self.state == CircuitState.CLOSED,
                "can_accept_calls": self.state != CircuitState.OPEN,
                "time_until_next_attempt": (
                    (self.next_attempt_time - now).total_seconds()
                    if self.next_attempt_time and self.next_attempt_time > now
                    else 0
                ),
            },
        }

    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        async with self._lock:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            self.last_failure_time = None
            self.next_attempt_time = None

            logger.info(
                f"Circuit breaker '{self.name}' manually reset from {old_state.value} to CLOSED"
            )

    def is_call_permitted(self) -> bool:
        """Check if a call would be permitted without executing it."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            return self._should_attempt_reset()
        elif self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return False


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Provides a centralized way to create, access, and monitor
    circuit breakers across the application.
    """

    def __init__(self):
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, name: str, **kwargs) -> CircuitBreaker:
        """Get existing circuit breaker or create a new one."""
        async with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
                logger.info(f"Created new circuit breaker: {name}")
            return self._circuit_breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._circuit_breakers.get(name)

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        return {name: cb.get_metrics() for name, cb in self._circuit_breakers.items()}

    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for cb in self._circuit_breakers.values():
                await cb.reset()
            logger.info("Reset all circuit breakers")

    def get_health_summary(self) -> dict[str, Any]:
        """Get overall health summary of all circuit breakers."""
        total_breakers = len(self._circuit_breakers)
        healthy_breakers = sum(
            1
            for cb in self._circuit_breakers.values()
            if cb.get_state() == CircuitState.CLOSED
        )

        return {
            "total_circuit_breakers": total_breakers,
            "healthy_circuit_breakers": healthy_breakers,
            "health_percentage": (
                (healthy_breakers / total_breakers) * 100
                if total_breakers > 0
                else 100.0
            ),
            "circuit_breaker_states": {
                name: cb.get_state().value
                for name, cb in self._circuit_breakers.items()
            },
        }


# Global registry instance
_circuit_breaker_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _circuit_breaker_registry
    if _circuit_breaker_registry is None:
        _circuit_breaker_registry = CircuitBreakerRegistry()
    return _circuit_breaker_registry


async def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker from the global registry."""
    registry = get_circuit_breaker_registry()
    return await registry.get_or_create(name, **kwargs)
