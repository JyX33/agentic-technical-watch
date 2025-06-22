#!/usr/bin/env python3
# ABOUTME: Integration test runner for A2A agent system
# ABOUTME: Orchestrates Docker Compose test environment and runs integration tests

import argparse
import os
import signal
import subprocess
import sys
import time


class IntegrationTestRunner:
    """Manages integration test execution with Docker Compose"""

    def __init__(self, compose_file: str = "docker-compose.test.yml"):
        self.compose_file = compose_file
        self.project_name = "reddit-watcher-test"
        self.test_services = [
            "test-db",
            "test-redis",
            "mock-reddit-api",
            "mock-gemini-api",
            "mock-slack",
        ]
        self.agent_services = [
            "test-coordinator-agent",
            "test-retrieval-agent",
            "test-filter-agent",
            "test-summarise-agent",
            "test-alert-agent",
        ]

    def run_command(self, cmd: list, capture_output: bool = False, check: bool = True):
        """Run a shell command"""
        print(f"🔧 Running: {' '.join(cmd)}")

        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if check and result.returncode != 0:
                print(f"❌ Command failed with code {result.returncode}")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                sys.exit(1)
            return result
        else:
            result = subprocess.run(cmd, check=check)
            return result

    def setup_environment(self):
        """Setup the test environment"""
        print("🚀 Setting up integration test environment...")

        # Stop any existing test containers
        self.cleanup_environment()

        # Start infrastructure services first
        print("📦 Starting infrastructure services...")
        self.run_command(
            [
                "docker-compose",
                "-f",
                self.compose_file,
                "-p",
                self.project_name,
                "up",
                "-d",
            ]
            + self.test_services
        )

        # Wait for infrastructure to be ready
        self.wait_for_infrastructure()

        # Start agent services
        print("🤖 Starting A2A agent services...")
        self.run_command(
            [
                "docker-compose",
                "-f",
                self.compose_file,
                "-p",
                self.project_name,
                "up",
                "-d",
            ]
            + self.agent_services
        )

        # Wait for agents to be ready
        self.wait_for_agents()

        print("✅ Test environment is ready!")

    def wait_for_infrastructure(self, timeout: int = 60):
        """Wait for infrastructure services to be healthy"""
        print("⏳ Waiting for infrastructure services...")

        start_time = time.time()
        ready_services = set()
        required_services = [
            "test-db",
            "test-redis",
            "mock-reddit-api",
            "mock-gemini-api",
            "mock-slack",
        ]

        while (
            len(ready_services) < len(required_services)
            and (time.time() - start_time) < timeout
        ):
            for service_name in required_services:
                if service_name in ready_services:
                    continue

                try:
                    if service_name == "test-db":
                        # PostgreSQL health check using pg_isready
                        result = self.run_command(
                            [
                                "docker",
                                "exec",
                                f"{self.project_name}-test-db-1",
                                "pg_isready",
                                "-U",
                                "test_user",
                                "-d",
                                "reddit_watcher_test",
                            ],
                            capture_output=True,
                            check=False,
                        )
                        if result.returncode == 0:
                            print(f"✅ {service_name} is ready")
                            ready_services.add(service_name)
                    elif service_name == "test-redis":
                        # Redis health check using redis-cli ping
                        result = self.run_command(
                            [
                                "docker",
                                "exec",
                                f"{self.project_name}-test-redis-1",
                                "redis-cli",
                                "ping",
                            ],
                            capture_output=True,
                            check=False,
                        )
                        if result.returncode == 0 and "PONG" in result.stdout:
                            print(f"✅ {service_name} is ready")
                            ready_services.add(service_name)
                    elif service_name == "mock-reddit-api":
                        # HTTP health check for mock Reddit API
                        result = self.run_command(
                            ["curl", "-f", "-s", "http://localhost:8080/health"],
                            capture_output=True,
                            check=False,
                        )
                        if result.returncode == 0:
                            print(f"✅ {service_name} is ready")
                            ready_services.add(service_name)
                    elif service_name == "mock-gemini-api":
                        # HTTP health check for mock Gemini API
                        result = self.run_command(
                            ["curl", "-f", "-s", "http://localhost:8081/health"],
                            capture_output=True,
                            check=False,
                        )
                        if result.returncode == 0:
                            print(f"✅ {service_name} is ready")
                            ready_services.add(service_name)
                    elif service_name == "mock-slack":
                        # HTTP health check for mock Slack webhook
                        result = self.run_command(
                            ["curl", "-f", "-s", "http://localhost:8082/health"],
                            capture_output=True,
                            check=False,
                        )
                        if result.returncode == 0:
                            print(f"✅ {service_name} is ready")
                            ready_services.add(service_name)
                except Exception:
                    pass

            if len(ready_services) < len(required_services):
                time.sleep(2)

        if len(ready_services) < len(required_services):
            missing = set(required_services) - ready_services
            raise RuntimeError(
                f"Infrastructure services not ready after {timeout}s: {missing}"
            )

    def wait_for_agents(self, timeout: int = 90):
        """Wait for A2A agent services to be healthy"""
        print("⏳ Waiting for A2A agents...")

        agents = {
            "coordinator": ("localhost", 8100),
            "retrieval": ("localhost", 8101),
            "filter": ("localhost", 8102),
            "summarise": ("localhost", 8103),
            "alert": ("localhost", 8104),
        }

        start_time = time.time()
        ready_agents = set()

        while len(ready_agents) < len(agents) and (time.time() - start_time) < timeout:
            for agent_name, (host, port) in agents.items():
                if agent_name in ready_agents:
                    continue

                try:
                    result = self.run_command(
                        ["curl", "-f", "-s", f"http://{host}:{port}/health"],
                        capture_output=True,
                        check=False,
                    )
                    if result.returncode == 0:
                        print(f"✅ {agent_name} agent is ready")
                        ready_agents.add(agent_name)
                except Exception:
                    pass

            if len(ready_agents) < len(agents):
                time.sleep(3)

        if len(ready_agents) < len(agents):
            missing = set(agents.keys()) - ready_agents
            raise RuntimeError(f"A2A agents not ready after {timeout}s: {missing}")

    def run_tests(self, test_args: list = None):
        """Run the integration tests"""
        print("🧪 Running integration tests...")

        test_cmd = [
            "python",
            "-m",
            "pytest",
            "-c",
            "pytest-integration.ini",
            "tests/integration/",
            "--verbose",
        ]

        if test_args:
            test_cmd.extend(test_args)

        # Set environment variables for tests
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": "postgresql://test_user:test_password@localhost:5433/reddit_watcher_test",
                "REDIS_URL": "redis://localhost:6380/0",
                "COORDINATOR_URL": "http://localhost:8100",
                "RETRIEVAL_URL": "http://localhost:8101",
                "FILTER_URL": "http://localhost:8102",
                "SUMMARISE_URL": "http://localhost:8103",
                "ALERT_URL": "http://localhost:8104",
                "TEST_MODE": "true",
            }
        )

        result = subprocess.run(test_cmd, env=env)
        return result.returncode

    def cleanup_environment(self):
        """Clean up the test environment"""
        print("🧹 Cleaning up test environment...")

        # Stop and remove containers
        self.run_command(
            [
                "docker-compose",
                "-f",
                self.compose_file,
                "-p",
                self.project_name,
                "down",
                "-v",
                "--remove-orphans",
            ],
            check=False,
        )

        # Remove any dangling volumes
        self.run_command(["docker", "volume", "prune", "-f"], check=False)

    def show_logs(self, service: str = None):
        """Show logs from test services"""
        if service:
            self.run_command(
                [
                    "docker-compose",
                    "-f",
                    self.compose_file,
                    "-p",
                    self.project_name,
                    "logs",
                    service,
                ]
            )
        else:
            self.run_command(
                [
                    "docker-compose",
                    "-f",
                    self.compose_file,
                    "-p",
                    self.project_name,
                    "logs",
                ]
            )


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received interrupt signal, cleaning up...")
    runner = IntegrationTestRunner()
    runner.cleanup_environment()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Run A2A integration tests")
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only setup environment, don't run tests",
    )
    parser.add_argument(
        "--cleanup-only", action="store_true", help="Only cleanup environment"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Don't cleanup after tests"
    )
    parser.add_argument(
        "--logs", metavar="SERVICE", help="Show logs for specific service"
    )
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--smoke", action="store_true", help="Run only smoke tests")
    parser.add_argument("test_args", nargs="*", help="Additional pytest arguments")

    args = parser.parse_args()

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    runner = IntegrationTestRunner()

    try:
        if args.cleanup_only:
            runner.cleanup_environment()
            return 0

        if args.logs:
            runner.show_logs(args.logs)
            return 0

        # Setup environment
        runner.setup_environment()

        if args.setup_only:
            print("🎯 Environment setup complete. Containers are running.")
            print(
                "💡 Run tests manually with: python -m pytest -c pytest-integration.ini tests/integration/"
            )
            return 0

        # Prepare test arguments
        test_args = list(args.test_args) if args.test_args else []

        if args.fast:
            test_args.extend(["-m", "not slow"])

        if args.smoke:
            test_args.extend(["-m", "smoke"])

        # Run tests
        exit_code = runner.run_tests(test_args)

        if exit_code == 0:
            print("✅ All integration tests passed!")
        else:
            print("❌ Some integration tests failed!")

        return exit_code

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        if not args.no_cleanup and not args.setup_only:
            runner.cleanup_environment()


if __name__ == "__main__":
    sys.exit(main())
