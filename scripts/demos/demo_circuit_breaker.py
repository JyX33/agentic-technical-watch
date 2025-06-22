#!/usr/bin/env python3
"""
Demo script showing circuit breaker functionality in action.

This script demonstrates how the circuit breaker pattern works with:
1. Normal operation (CLOSED state)
2. Service failures leading to OPEN state
3. Recovery attempts and HALF_OPEN state
4. Service recovery and return to CLOSED state
"""

import asyncio
import logging
from typing import Any

from reddit_watcher.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
)

# Configure logging to see circuit breaker state changes
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class MockService:
    """Mock service that can be configured to fail or succeed."""

    def __init__(self):
        self.call_count = 0
        self.should_fail = False
        self.failure_count = 0

    async def call_service(self) -> dict[str, Any]:
        """Simulate a service call that may fail."""
        self.call_count += 1

        if self.should_fail:
            self.failure_count += 1
            logger.info(
                f"🔴 Service call #{self.call_count} - FAILING (failure #{self.failure_count})"
            )
            raise ConnectionError(f"Service unavailable (call #{self.call_count})")
        else:
            logger.info(f"🟢 Service call #{self.call_count} - SUCCESS")
            return {
                "status": "success",
                "call_number": self.call_count,
                "message": "Service is healthy",
            }

    def make_service_fail(self):
        """Configure service to fail."""
        self.should_fail = True
        logger.info("🔧 Configured service to FAIL")

    def make_service_recover(self):
        """Configure service to succeed."""
        self.should_fail = False
        logger.info("🔧 Configured service to RECOVER")


async def demo_circuit_breaker():
    """Demonstrate circuit breaker functionality."""
    logger.info("=" * 80)
    logger.info("🚀 CIRCUIT BREAKER DEMO STARTING")
    logger.info("=" * 80)

    # Create mock service and circuit breaker
    service = MockService()
    circuit_breaker = CircuitBreaker(
        name="demo_service",
        failure_threshold=3,  # Open after 3 failures
        recovery_timeout=2,  # Wait 2 seconds before trying again
        success_threshold=2,  # Need 2 successes to close
        half_open_max_calls=3,  # Allow up to 3 calls in HALF_OPEN
        call_timeout=5.0,  # 5 second timeout per call
    )

    logger.info("📊 Circuit Breaker Configuration:")
    logger.info(f"   - Failure Threshold: {circuit_breaker.failure_threshold}")
    logger.info(f"   - Recovery Timeout: {circuit_breaker.recovery_timeout}s")
    logger.info(f"   - Success Threshold: {circuit_breaker.success_threshold}")
    logger.info(f"   - Initial State: {circuit_breaker.get_state().value}")
    logger.info("")

    # Phase 1: Normal operation (CLOSED state)
    logger.info("🔵 PHASE 1: Normal Operation (CLOSED state)")
    logger.info("-" * 50)

    for i in range(3):
        try:
            result = await circuit_breaker.call(service.call_service)
            logger.info(f"✅ Call {i + 1} successful: {result['message']}")
        except Exception as e:
            logger.error(f"❌ Call {i + 1} failed: {e}")

        await asyncio.sleep(0.5)

    logger.info(
        f"📊 State: {circuit_breaker.get_state().value}, Failures: {circuit_breaker.failure_count}"
    )
    logger.info("")

    # Phase 2: Service starts failing
    logger.info("🟠 PHASE 2: Service Failures (approaching OPEN state)")
    logger.info("-" * 50)

    service.make_service_fail()

    for i in range(3):  # This should open the circuit on the 3rd failure
        try:
            result = await circuit_breaker.call(service.call_service)
            logger.info(f"✅ Call {i + 1} successful: {result}")
        except ConnectionError as e:
            logger.error(f"❌ Call {i + 1} failed: {e}")
        except CircuitBreakerError as e:
            logger.error(f"⚡ Call {i + 1} blocked by circuit breaker: {e}")

        logger.info(
            f"📊 State: {circuit_breaker.get_state().value}, Failures: {circuit_breaker.failure_count}"
        )
        await asyncio.sleep(0.5)

    logger.info("")

    # Phase 3: Circuit is now OPEN - calls should be rejected
    logger.info("🔴 PHASE 3: Circuit OPEN (calls rejected)")
    logger.info("-" * 50)

    for i in range(3):
        try:
            result = await circuit_breaker.call(service.call_service)
            logger.info(f"✅ Call {i + 1} successful: {result}")
        except ConnectionError as e:
            logger.error(f"❌ Call {i + 1} failed: {e}")
        except CircuitBreakerError as e:
            logger.error(f"⚡ Call {i + 1} blocked by circuit breaker: {e}")

        await asyncio.sleep(0.5)

    metrics = circuit_breaker.get_metrics()
    logger.info(
        f"📊 Circuit Open Rejections: {metrics['total_metrics']['total_circuit_open_rejections']}"
    )
    logger.info("")

    # Phase 4: Wait for recovery timeout
    logger.info("⏰ PHASE 4: Waiting for Recovery Timeout")
    logger.info("-" * 50)

    logger.info(
        f"Waiting {circuit_breaker.recovery_timeout} seconds for recovery timeout..."
    )
    await asyncio.sleep(circuit_breaker.recovery_timeout + 0.5)
    logger.info("Recovery timeout elapsed - next call should transition to HALF_OPEN")
    logger.info("")

    # Phase 5: Service still failing - HALF_OPEN should immediately go back to OPEN
    logger.info("🟡 PHASE 5: First Recovery Attempt (service still failing)")
    logger.info("-" * 50)

    try:
        result = await circuit_breaker.call(service.call_service)
        logger.info(f"✅ Recovery call successful: {result}")
    except ConnectionError as e:
        logger.error(f"❌ Recovery call failed: {e}")
    except CircuitBreakerError as e:
        logger.error(f"⚡ Recovery call blocked: {e}")

    logger.info(f"📊 State after failed recovery: {circuit_breaker.get_state().value}")
    logger.info("")

    # Phase 6: Wait again and fix the service
    logger.info("🔧 PHASE 6: Service Recovery")
    logger.info("-" * 50)

    logger.info(f"Waiting another {circuit_breaker.recovery_timeout} seconds...")
    await asyncio.sleep(circuit_breaker.recovery_timeout + 0.5)

    # Fix the service
    service.make_service_recover()

    # Make enough successful calls to close the circuit
    logger.info("Attempting service calls with recovered service...")
    for i in range(circuit_breaker.success_threshold + 1):
        try:
            result = await circuit_breaker.call(service.call_service)
            logger.info(f"✅ Recovery call {i + 1} successful: {result['message']}")
            logger.info(
                f"📊 State: {circuit_breaker.get_state().value}, Successes: {circuit_breaker.success_count}"
            )
        except Exception as e:
            logger.error(f"❌ Recovery call {i + 1} failed: {e}")

        await asyncio.sleep(0.5)

    logger.info("")

    # Phase 7: Normal operation resumed
    logger.info("✅ PHASE 7: Normal Operation Resumed")
    logger.info("-" * 50)

    for i in range(3):
        try:
            result = await circuit_breaker.call(service.call_service)
            logger.info(f"✅ Normal call {i + 1} successful: {result['message']}")
        except Exception as e:
            logger.error(f"❌ Normal call {i + 1} failed: {e}")

        await asyncio.sleep(0.5)

    # Final metrics
    logger.info("")
    logger.info("📊 FINAL METRICS:")
    logger.info("-" * 50)

    final_metrics = circuit_breaker.get_metrics()
    logger.info(f"Final State: {final_metrics['state']}")
    logger.info(f"Total Calls: {final_metrics['total_metrics']['total_calls']}")
    logger.info(f"Total Successes: {final_metrics['total_metrics']['total_successes']}")
    logger.info(f"Total Failures: {final_metrics['total_metrics']['total_failures']}")
    logger.info(
        f"Circuit Open Rejections: {final_metrics['total_metrics']['total_circuit_open_rejections']}"
    )
    logger.info(
        f"Success Rate: {final_metrics['total_metrics']['success_rate_percent']}%"
    )
    logger.info(f"Is Healthy: {final_metrics['health_status']['is_healthy']}")

    logger.info("")
    logger.info("=" * 80)
    logger.info("🎉 CIRCUIT BREAKER DEMO COMPLETED")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_circuit_breaker())
