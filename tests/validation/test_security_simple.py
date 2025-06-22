# ABOUTME: Simple security test that runs a minimal agent server for testing security features
# ABOUTME: Tests authentication, rate limiting, security headers, and input validation without external dependencies

import asyncio
import json
import logging
import os
import time

import aiohttp
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from reddit_watcher.auth_middleware import AuthMiddleware
from reddit_watcher.config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TEST_API_KEY = "test-security-simple-key-xyz789"
INVALID_API_KEY = "invalid-key-should-fail-abc123"
TEST_PORT = 8099


class SimpleTestServer:
    """Simple test server for security validation."""

    def __init__(self, port: int = TEST_PORT):
        self.port = port
        # Set environment variable first
        os.environ["A2A_API_KEY"] = TEST_API_KEY
        self.config = Settings()
        # Also set manually to ensure it's set
        self.config.a2a_api_key = TEST_API_KEY
        self.auth = AuthMiddleware(self.config)
        self.security = HTTPBearer()

        # Debug print
        print(f"DEBUG: Server config a2a_api_key = '{self.config.a2a_api_key}'")
        print(f"DEBUG: Expected API key = '{TEST_API_KEY}'")
        print(f"DEBUG: Keys match = {self.config.a2a_api_key == TEST_API_KEY}")
        self.app = None

    def create_app(self) -> FastAPI:
        """Create test FastAPI application."""
        app = FastAPI(title="Security Test Server")

        # Add security middleware
        from reddit_watcher.security_middleware import (
            InputValidationMiddleware,
            RateLimitingMiddleware,
            SecurityAuditMiddleware,
            SecurityHeadersMiddleware,
        )

        app.add_middleware(SecurityHeadersMiddleware, config=self.config)
        app.add_middleware(RateLimitingMiddleware, config=self.config)
        app.add_middleware(InputValidationMiddleware, config=self.config)
        app.add_middleware(SecurityAuditMiddleware, config=self.config)

        # Public endpoints (no auth required)
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": time.time()}

        @app.get("/.well-known/agent.json")
        async def agent_card():
            """Agent card endpoint."""
            return {
                "name": "Security Test Agent",
                "version": "1.0.0",
                "type": "test",
                "skills": ["health_check"],
            }

        @app.get("/discover")
        async def discover():
            """Service discovery endpoint."""
            return {"agents": []}

        # Protected endpoints (auth required)
        @app.post("/skills/test")
        async def test_skill(
            request: dict,
            credentials: HTTPAuthorizationCredentials = Depends(self.security),
        ):
            """Test skill endpoint requiring authentication."""
            # Verify the token using our auth middleware
            try:
                user = await self.auth.verify_token(credentials)
                return {
                    "message": "Authenticated request successful",
                    "user": user,
                    "request": request,
                }
            except HTTPException as e:
                # Re-raise the HTTP exception
                raise e

        @app.post("/a2a")
        async def a2a_endpoint(request: dict):
            """A2A JSON-RPC endpoint (may or may not require auth)."""
            return {
                "jsonrpc": "2.0",
                "result": {"message": "A2A request processed"},
                "id": request.get("id"),
            }

        self.app = app
        return app

    async def start_server(self):
        """Start the test server."""
        app = self.create_app()

        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="info", access_log=False
        )

        server = uvicorn.Server(config)
        await server.serve()


async def run_security_tests():
    """Run security tests against the test server."""
    base_url = f"http://127.0.0.1:{TEST_PORT}"

    async with aiohttp.ClientSession() as session:
        results = {
            "timestamp": time.time(),
            "base_url": base_url,
            "tests": [],
            "passed": 0,
            "failed": 0,
        }

        # Test 1: Public endpoints should be accessible
        try:
            async with session.get(f"{base_url}/health", timeout=5) as response:
                if response.status == 200:
                    results["tests"].append(
                        {
                            "test": "public_endpoint_health",
                            "status": "PASS",
                            "message": "Health endpoint accessible",
                        }
                    )
                    results["passed"] += 1
                else:
                    results["tests"].append(
                        {
                            "test": "public_endpoint_health",
                            "status": "FAIL",
                            "message": f"Health endpoint returned {response.status}",
                        }
                    )
                    results["failed"] += 1
        except Exception as e:
            results["tests"].append(
                {
                    "test": "public_endpoint_health",
                    "status": "ERROR",
                    "message": f"Health endpoint error: {str(e)}",
                }
            )
            results["failed"] += 1

        # Test 2: Protected endpoint should require authentication
        try:
            async with session.post(
                f"{base_url}/skills/test", json={"test": "data"}, timeout=5
            ) as response:
                if response.status == 401:
                    results["tests"].append(
                        {
                            "test": "auth_required_endpoint",
                            "status": "PASS",
                            "message": "Protected endpoint properly requires auth (401)",
                        }
                    )
                    results["passed"] += 1
                else:
                    results["tests"].append(
                        {
                            "test": "auth_required_endpoint",
                            "status": "FAIL",
                            "message": f"Protected endpoint returned {response.status} instead of 401",
                        }
                    )
                    results["failed"] += 1
        except Exception as e:
            results["tests"].append(
                {
                    "test": "auth_required_endpoint",
                    "status": "ERROR",
                    "message": f"Auth test error: {str(e)}",
                }
            )
            results["failed"] += 1

        # Test 3: Valid API key should work
        try:
            headers = {"Authorization": f"Bearer {TEST_API_KEY}"}
            print(f"DEBUG: Sending request with header: {headers}")
            async with session.post(
                f"{base_url}/skills/test",
                json={"test": "data"},
                headers=headers,
                timeout=5,
            ) as response:
                response_text = await response.text()
                print(
                    f"DEBUG: Valid API key test - Status: {response.status}, Response: {response_text}"
                )
                if response.status == 200:
                    results["tests"].append(
                        {
                            "test": "valid_api_key",
                            "status": "PASS",
                            "message": "Valid API key accepted",
                        }
                    )
                    results["passed"] += 1
                else:
                    results["tests"].append(
                        {
                            "test": "valid_api_key",
                            "status": "FAIL",
                            "message": f"Valid API key returned {response.status} - {response_text}",
                        }
                    )
                    results["failed"] += 1
        except Exception as e:
            results["tests"].append(
                {
                    "test": "valid_api_key",
                    "status": "ERROR",
                    "message": f"Valid API key test error: {str(e)}",
                }
            )
            results["failed"] += 1

        # Test 4: Invalid API key should be rejected
        try:
            headers = {"Authorization": f"Bearer {INVALID_API_KEY}"}
            async with session.post(
                f"{base_url}/skills/test",
                json={"test": "data"},
                headers=headers,
                timeout=5,
            ) as response:
                if response.status == 403:
                    results["tests"].append(
                        {
                            "test": "invalid_api_key",
                            "status": "PASS",
                            "message": "Invalid API key properly rejected (403)",
                        }
                    )
                    results["passed"] += 1
                else:
                    results["tests"].append(
                        {
                            "test": "invalid_api_key",
                            "status": "FAIL",
                            "message": f"Invalid API key returned {response.status} instead of 403",
                        }
                    )
                    results["failed"] += 1
        except Exception as e:
            results["tests"].append(
                {
                    "test": "invalid_api_key",
                    "status": "ERROR",
                    "message": f"Invalid API key test error: {str(e)}",
                }
            )
            results["failed"] += 1

        # Test 5: Security headers should be present
        try:
            async with session.get(f"{base_url}/health", timeout=5) as response:
                expected_headers = [
                    "X-Content-Type-Options",
                    "X-Frame-Options",
                    "X-XSS-Protection",
                    "Content-Security-Policy",
                ]

                present_headers = [h for h in expected_headers if h in response.headers]

                if len(present_headers) >= 3:
                    results["tests"].append(
                        {
                            "test": "security_headers",
                            "status": "PASS",
                            "message": f"Security headers present: {present_headers}",
                        }
                    )
                    results["passed"] += 1
                else:
                    results["tests"].append(
                        {
                            "test": "security_headers",
                            "status": "FAIL",
                            "message": f"Insufficient security headers: {present_headers}",
                        }
                    )
                    results["failed"] += 1
        except Exception as e:
            results["tests"].append(
                {
                    "test": "security_headers",
                    "status": "ERROR",
                    "message": f"Security headers test error: {str(e)}",
                }
            )
            results["failed"] += 1

        # Test 6: Rate limiting headers should be present
        try:
            async with session.get(f"{base_url}/health", timeout=5) as response:
                rate_limit_headers = ["X-RateLimit-Limit", "X-RateLimit-Remaining"]

                present_headers = [
                    h for h in rate_limit_headers if h in response.headers
                ]

                if len(present_headers) >= 1:
                    results["tests"].append(
                        {
                            "test": "rate_limit_headers",
                            "status": "PASS",
                            "message": f"Rate limit headers present: {present_headers}",
                        }
                    )
                    results["passed"] += 1
                else:
                    results["tests"].append(
                        {
                            "test": "rate_limit_headers",
                            "status": "INFO",
                            "message": "No rate limit headers found (may be by design)",
                        }
                    )
                    # Don't count as failed since it might be intentional
        except Exception as e:
            results["tests"].append(
                {
                    "test": "rate_limit_headers",
                    "status": "ERROR",
                    "message": f"Rate limit headers test error: {str(e)}",
                }
            )
            results["failed"] += 1

        return results


async def main():
    """Main security test function."""
    print("=" * 80)
    print("REDDIT TECHNICAL WATCHER - SIMPLE SECURITY TEST")
    print("=" * 80)

    # Start test server in background
    server = SimpleTestServer()
    server_task = asyncio.create_task(server.start_server())

    # Wait for server to start
    await asyncio.sleep(2)

    try:
        # Run security tests
        logger.info("Running security tests...")
        results = await run_security_tests()

        # Print results
        print("\n" + "=" * 60)
        print("SECURITY TEST RESULTS")
        print("=" * 60)

        for test in results["tests"]:
            status = test["status"]
            test_name = test["test"]
            message = test["message"]

            status_symbol = {"PASS": "✓", "FAIL": "✗", "INFO": "ℹ", "ERROR": "💥"}.get(
                status, "?"
            )

            print(f"  {status_symbol} {test_name}: {message}")

        # Print summary
        total_tests = results["passed"] + results["failed"]
        success_rate = (results["passed"] / total_tests * 100) if total_tests > 0 else 0

        print("\n" + "=" * 60)
        print("SECURITY TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Success Rate: {success_rate:.1f}%")

        if success_rate >= 80:
            print("Overall Status: ✓ SECURE")
        elif success_rate >= 60:
            print("Overall Status: ⚠ ACCEPTABLE")
        else:
            print("Overall Status: ✗ NEEDS IMPROVEMENT")

        # Save results
        with open(
            "/home/jyx/git/agentic-technical-watch/simple_security_test_report.json",
            "w",
        ) as f:
            json.dump(results, f, indent=2)

        print("\nDetailed results saved to: simple_security_test_report.json")

    finally:
        # Stop server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
