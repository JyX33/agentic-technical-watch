# ABOUTME: pytest configuration for A2A integration tests
# ABOUTME: Provides fixtures and configuration for integration test execution

import asyncio
import time

import aiohttp
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def integration_setup():
    """Setup for integration tests - wait for all services to be ready"""

    # Wait for services to be healthy
    services = [
        ("test-db", "localhost", 5433),
        ("test-redis", "localhost", 6380),
        ("mock-reddit-api", "localhost", 8080),
        ("mock-gemini-api", "localhost", 8081),
        ("mock-slack", "localhost", 8082),
    ]

    print("\nWaiting for test services to be ready...")

    for service_name, host, port in services:
        await _wait_for_service(service_name, host, port)

    # Wait for A2A agents to be healthy
    agents = [
        ("coordinator", "localhost", 8100),
        ("retrieval", "localhost", 8101),
        ("filter", "localhost", 8102),
        ("summarise", "localhost", 8103),
        ("alert", "localhost", 8104),
    ]

    print("Waiting for A2A agents to be ready...")

    for agent_name, host, port in agents:
        await _wait_for_agent_health(agent_name, host, port)

    print("All services and agents are ready!")

    yield

    # Cleanup (if needed)
    print("Integration test cleanup complete")


async def _wait_for_service(
    service_name: str, host: str, port: int, max_attempts: int = 30
):
    """Wait for a service to be ready"""

    for attempt in range(max_attempts):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{host}:{port}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        print(f"✅ {service_name} is ready")
                        return
        except Exception:
            pass

        if attempt < max_attempts - 1:
            await asyncio.sleep(2)

    raise RuntimeError(
        f"Service {service_name} failed to become ready after {max_attempts} attempts"
    )


async def _wait_for_agent_health(
    agent_name: str, host: str, port: int, max_attempts: int = 30
):
    """Wait for an A2A agent to be healthy"""

    for attempt in range(max_attempts):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{host}:{port}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") in ["healthy", "ok"]:
                            print(f"✅ {agent_name} agent is healthy")
                            return
        except Exception:
            pass

        if attempt < max_attempts - 1:
            await asyncio.sleep(2)

    raise RuntimeError(
        f"Agent {agent_name} failed to become healthy after {max_attempts} attempts"
    )


@pytest.fixture(autouse=True)
async def reset_mock_apis():
    """Reset mock APIs before each test to ensure clean state"""

    mock_apis = [
        ("reddit", "localhost", 8080),
        ("slack", "localhost", 8082),
    ]

    async with aiohttp.ClientSession() as session:
        for api_name, host, port in mock_apis:
            try:
                if api_name == "reddit":
                    async with session.delete(f"http://{host}:{port}/api/v1/reset"):
                        pass
                elif api_name == "slack":
                    async with session.delete(f"http://{host}:{port}/webhooks/clear"):
                        pass
            except Exception:
                # Ignore errors in cleanup
                pass


@pytest.fixture
def test_correlation_id():
    """Generate unique correlation ID for test tracking"""
    return f"test_{int(time.time() * 1000)}"


# Pytest markers for different test categories
# pytest_plugins moved to root conftest.py to avoid deprecation warning


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "a2a: marks tests as A2A protocol tests")
    config.addinivalue_line("markers", "workflow: marks tests as workflow tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers"""
    for item in items:
        # Add integration marker to all tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add specific markers based on test names
        if "workflow" in item.name:
            item.add_marker(pytest.mark.workflow)

        if "performance" in item.name:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)

        if "a2a" in item.name or "agent" in item.name:
            item.add_marker(pytest.mark.a2a)
