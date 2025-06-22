# ABOUTME: Security validation script to test security measures and generate security report
# ABOUTME: Validates authentication, authorization, rate limiting, input validation, and security headers

import asyncio
import json
import logging
import os
import time

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TEST_API_KEY = "test-security-validation-key-abc123"
INVALID_API_KEY = "invalid-key-should-fail-xyz789"
TEST_BASE_URL = "http://localhost:8000"


class SecurityValidator:
    """Security validation test suite."""

    def __init__(self, base_url: str = TEST_BASE_URL):
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def validate_authentication_security(self) -> dict:
        """Validate authentication security measures."""
        results = {
            "test_name": "authentication_security",
            "tests": [],
            "passed": 0,
            "failed": 0,
        }

        # Test 1: Valid API key authentication
        test_result = await self._test_valid_authentication()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        # Test 2: Invalid API key rejection
        test_result = await self._test_invalid_authentication()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        # Test 3: Missing authentication rejection
        test_result = await self._test_missing_authentication()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        # Test 4: Public endpoints accessibility
        test_result = await self._test_public_endpoints()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        return results

    async def _test_valid_authentication(self) -> dict:
        """Test valid API key authentication."""
        try:
            headers = {"Authorization": f"Bearer {TEST_API_KEY}"}
            async with self.session.post(
                f"{self.base_url}/skills/health_check",
                json={"parameters": {}},
                headers=headers,
                timeout=10,
            ) as response:
                if response.status in [
                    200,
                    404,
                ]:  # 404 means skill not found but auth worked
                    return {
                        "test": "valid_api_key_authentication",
                        "status": "PASS",
                        "message": f"Valid API key accepted (status: {response.status})",
                    }
                else:
                    return {
                        "test": "valid_api_key_authentication",
                        "status": "FAIL",
                        "message": f"Expected 200/404, got {response.status}",
                    }
        except Exception as e:
            return {
                "test": "valid_api_key_authentication",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def _test_invalid_authentication(self) -> dict:
        """Test invalid API key rejection."""
        try:
            headers = {"Authorization": f"Bearer {INVALID_API_KEY}"}
            async with self.session.post(
                f"{self.base_url}/skills/health_check",
                json={"parameters": {}},
                headers=headers,
                timeout=10,
            ) as response:
                if response.status == 403:
                    return {
                        "test": "invalid_api_key_rejection",
                        "status": "PASS",
                        "message": "Invalid API key properly rejected (403)",
                    }
                else:
                    return {
                        "test": "invalid_api_key_rejection",
                        "status": "FAIL",
                        "message": f"Expected 403, got {response.status}",
                    }
        except Exception as e:
            return {
                "test": "invalid_api_key_rejection",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def _test_missing_authentication(self) -> dict:
        """Test missing authentication rejection."""
        try:
            async with self.session.post(
                f"{self.base_url}/skills/health_check",
                json={"parameters": {}},
                timeout=10,
            ) as response:
                if response.status == 401:
                    return {
                        "test": "missing_authentication_rejection",
                        "status": "PASS",
                        "message": "Missing authentication properly rejected (401)",
                    }
                else:
                    return {
                        "test": "missing_authentication_rejection",
                        "status": "FAIL",
                        "message": f"Expected 401, got {response.status}",
                    }
        except Exception as e:
            return {
                "test": "missing_authentication_rejection",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def _test_public_endpoints(self) -> dict:
        """Test public endpoints accessibility."""
        public_endpoints = ["/.well-known/agent.json", "/health", "/discover"]

        accessible_count = 0
        total_endpoints = len(public_endpoints)

        try:
            for endpoint in public_endpoints:
                async with self.session.get(
                    f"{self.base_url}{endpoint}", timeout=10
                ) as response:
                    if response.status == 200:
                        accessible_count += 1

            if accessible_count == total_endpoints:
                return {
                    "test": "public_endpoints_accessibility",
                    "status": "PASS",
                    "message": f"All {total_endpoints} public endpoints accessible",
                }
            else:
                return {
                    "test": "public_endpoints_accessibility",
                    "status": "FAIL",
                    "message": f"Only {accessible_count}/{total_endpoints} public endpoints accessible",
                }
        except Exception as e:
            return {
                "test": "public_endpoints_accessibility",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def validate_rate_limiting(self) -> dict:
        """Validate rate limiting implementation."""
        results = {"test_name": "rate_limiting", "tests": [], "passed": 0, "failed": 0}

        # Test rate limiting on public endpoint
        test_result = await self._test_rate_limiting_enforcement()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        # Test rate limit headers
        test_result = await self._test_rate_limit_headers()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        return results

    async def _test_rate_limiting_enforcement(self) -> dict:
        """Test rate limiting enforcement."""
        try:
            # Send rapid requests to trigger rate limiting
            requests_sent = 0
            rate_limited = False

            for i in range(20):  # Send 20 rapid requests
                async with self.session.get(
                    f"{self.base_url}/health", timeout=5
                ) as response:
                    requests_sent += 1
                    if response.status == 429:  # Too Many Requests
                        rate_limited = True
                        break
                    # Small delay to avoid overwhelming
                    await asyncio.sleep(0.1)

            if rate_limited:
                return {
                    "test": "rate_limiting_enforcement",
                    "status": "PASS",
                    "message": f"Rate limiting active - blocked after {requests_sent} requests",
                }
            else:
                return {
                    "test": "rate_limiting_enforcement",
                    "status": "INFO",
                    "message": f"No rate limiting detected after {requests_sent} requests",
                }
        except Exception as e:
            return {
                "test": "rate_limiting_enforcement",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def _test_rate_limit_headers(self) -> dict:
        """Test rate limit headers presence."""
        try:
            async with self.session.get(
                f"{self.base_url}/health", timeout=10
            ) as response:
                headers = response.headers

                rate_limit_headers = [
                    "X-RateLimit-Limit",
                    "X-RateLimit-Remaining",
                    "X-RateLimit-Reset",
                ]

                present_headers = [h for h in rate_limit_headers if h in headers]

                if len(present_headers) >= 2:
                    return {
                        "test": "rate_limit_headers",
                        "status": "PASS",
                        "message": f"Rate limit headers present: {present_headers}",
                    }
                else:
                    return {
                        "test": "rate_limit_headers",
                        "status": "INFO",
                        "message": f"Rate limit headers: {present_headers}",
                    }
        except Exception as e:
            return {
                "test": "rate_limit_headers",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def validate_security_headers(self) -> dict:
        """Validate security headers implementation."""
        results = {
            "test_name": "security_headers",
            "tests": [],
            "passed": 0,
            "failed": 0,
        }

        test_result = await self._test_security_headers_presence()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        return results

    async def _test_security_headers_presence(self) -> dict:
        """Test security headers presence."""
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Referrer-Policy",
        ]

        try:
            async with self.session.get(
                f"{self.base_url}/health", timeout=10
            ) as response:
                headers = response.headers

                present_headers = [h for h in expected_headers if h in headers]
                missing_headers = [h for h in expected_headers if h not in headers]

                if len(present_headers) >= 4:
                    return {
                        "test": "security_headers_presence",
                        "status": "PASS",
                        "message": f"Security headers present: {present_headers}",
                        "missing": missing_headers,
                    }
                else:
                    return {
                        "test": "security_headers_presence",
                        "status": "FAIL",
                        "message": f"Insufficient security headers. Present: {present_headers}, Missing: {missing_headers}",
                    }
        except Exception as e:
            return {
                "test": "security_headers_presence",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def validate_input_validation(self) -> dict:
        """Validate input validation implementation."""
        results = {
            "test_name": "input_validation",
            "tests": [],
            "passed": 0,
            "failed": 0,
        }

        # Test malicious input handling
        test_result = await self._test_malicious_input_handling()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        # Test oversized request handling
        test_result = await self._test_oversized_request_handling()
        results["tests"].append(test_result)
        if test_result["status"] == "PASS":
            results["passed"] += 1
        else:
            results["failed"] += 1

        return results

    async def _test_malicious_input_handling(self) -> dict:
        """Test handling of malicious input."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "javascript:alert('xss')",
            "../../../etc/passwd",
        ]

        try:
            for malicious_input in malicious_inputs:
                # Test in URL parameter
                url = f"{self.base_url}/health?param={malicious_input}"
                async with self.session.get(url, timeout=10) as response:
                    # Should either accept and sanitize, or reject with 400
                    if response.status not in [200, 400, 404]:
                        return {
                            "test": "malicious_input_handling",
                            "status": "FAIL",
                            "message": f"Unexpected response to malicious input: {response.status}",
                        }

            return {
                "test": "malicious_input_handling",
                "status": "PASS",
                "message": "Malicious input handled appropriately",
            }
        except Exception as e:
            return {
                "test": "malicious_input_handling",
                "status": "ERROR",
                "message": f"Test failed: {str(e)}",
            }

    async def _test_oversized_request_handling(self) -> dict:
        """Test handling of oversized requests."""
        try:
            # Create oversized payload (larger than configured limit)
            large_payload = {"data": "x" * (11 * 1024 * 1024)}  # 11MB

            async with self.session.post(
                f"{self.base_url}/health", json=large_payload, timeout=30
            ) as response:
                if response.status == 413:  # Payload Too Large
                    return {
                        "test": "oversized_request_handling",
                        "status": "PASS",
                        "message": "Oversized request properly rejected (413)",
                    }
                else:
                    return {
                        "test": "oversized_request_handling",
                        "status": "INFO",
                        "message": f"Oversized request returned: {response.status}",
                    }
        except Exception as e:
            # Connection errors are expected for oversized requests
            if "payload" in str(e).lower() or "size" in str(e).lower():
                return {
                    "test": "oversized_request_handling",
                    "status": "PASS",
                    "message": "Oversized request rejected at connection level",
                }
            else:
                return {
                    "test": "oversized_request_handling",
                    "status": "ERROR",
                    "message": f"Test failed: {str(e)}",
                }

    async def run_comprehensive_validation(self) -> dict:
        """Run comprehensive security validation."""
        logger.info("Starting comprehensive security validation...")

        validation_results = {
            "timestamp": time.time(),
            "base_url": self.base_url,
            "test_suites": [],
            "summary": {},
        }

        # Run all validation test suites
        test_suites = [
            ("Authentication Security", self.validate_authentication_security),
            ("Rate Limiting", self.validate_rate_limiting),
            ("Security Headers", self.validate_security_headers),
            ("Input Validation", self.validate_input_validation),
        ]

        total_passed = 0
        total_failed = 0
        total_tests = 0

        for suite_name, suite_method in test_suites:
            logger.info(f"Running {suite_name} validation...")

            try:
                suite_results = await suite_method()
                suite_results["suite_name"] = suite_name
                validation_results["test_suites"].append(suite_results)

                total_passed += suite_results["passed"]
                total_failed += suite_results["failed"]
                total_tests += len(suite_results["tests"])

            except Exception as e:
                logger.error(f"Error in {suite_name} validation: {e}")
                validation_results["test_suites"].append(
                    {
                        "suite_name": suite_name,
                        "error": str(e),
                        "passed": 0,
                        "failed": 1,
                        "tests": [],
                    }
                )
                total_failed += 1
                total_tests += 1

        # Generate summary
        security_score = (total_passed / total_tests * 100) if total_tests > 0 else 0
        validation_results["summary"] = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "security_score": round(security_score, 1),
            "overall_status": self._determine_overall_status(
                total_failed, security_score
            ),
        }

        return validation_results

    def _determine_overall_status(self, failed_tests: int, score: float) -> str:
        """Determine overall security validation status."""
        if failed_tests == 0 and score >= 90:
            return "EXCELLENT"
        elif failed_tests <= 1 and score >= 80:
            return "GOOD"
        elif failed_tests <= 3 and score >= 60:
            return "ACCEPTABLE"
        else:
            return "NEEDS_IMPROVEMENT"


async def main():
    """Run security validation."""
    # Set test API key
    os.environ["A2A_API_KEY"] = TEST_API_KEY

    print("=" * 80)
    print("REDDIT TECHNICAL WATCHER - SECURITY VALIDATION")
    print("=" * 80)

    async with SecurityValidator() as validator:
        results = await validator.run_comprehensive_validation()

    # Print results
    print("\n" + "=" * 60)
    print("SECURITY VALIDATION RESULTS")
    print("=" * 60)

    for suite in results["test_suites"]:
        print(f"\n{suite['suite_name'].upper()}:")
        print("-" * 40)

        if "error" in suite:
            print(f"  ✗ ERROR: {suite['error']}")
            continue

        for test in suite["tests"]:
            status = test["status"]
            test_name = test["test"]
            message = test["message"]

            status_symbol = {"PASS": "✓", "FAIL": "✗", "INFO": "ℹ", "ERROR": "💥"}.get(
                status, "?"
            )

            print(f"  {status_symbol} {test_name}: {message}")

    # Print summary
    summary = results["summary"]
    print("\n" + "=" * 60)
    print("SECURITY VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {summary['total_passed']}")
    print(f"Failed: {summary['total_failed']}")
    print(f"Security Score: {summary['security_score']}%")
    print(f"Overall Status: {summary['overall_status']}")

    # Save results
    with open(
        "/home/jyx/git/agentic-technical-watch/security_validation_report.json", "w"
    ) as f:
        json.dump(results, f, indent=2)

    print("\nDetailed results saved to: security_validation_report.json")

    return results


if __name__ == "__main__":
    asyncio.run(main())
