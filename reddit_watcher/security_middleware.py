# ABOUTME: Security middleware for A2A agent endpoints with rate limiting, request validation, and security headers
# ABOUTME: Provides comprehensive security measures including DDoS protection, input validation, and secure headers

import ipaddress
import logging
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from reddit_watcher.config import Settings

logger = logging.getLogger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with sliding window algorithm.

    Implements per-IP rate limiting with configurable thresholds
    and time windows to prevent abuse and DDoS attacks.
    """

    def __init__(self, app, config: Settings):
        super().__init__(app)
        self.config = config

        # Rate limiting configuration
        self.requests_per_minute = getattr(config, "rate_limit_requests_per_minute", 60)
        self.requests_per_hour = getattr(config, "rate_limit_requests_per_hour", 1000)
        self.burst_limit = getattr(config, "rate_limit_burst_limit", 10)

        # Sliding window storage: IP -> deque of timestamps
        self.request_windows: dict[str, deque] = defaultdict(lambda: deque())
        self.cleanup_interval = 300  # Clean up old entries every 5 minutes
        self.last_cleanup = time.time()

        # Whitelist for trusted IPs (localhost, internal networks)
        self.whitelisted_ips = self._get_whitelisted_ips()

    def _get_whitelisted_ips(self) -> set[str]:
        """Get set of whitelisted IP addresses."""
        whitelist = {"127.0.0.1", "::1", "localhost"}

        # Add private network ranges

        # Add any additional whitelisted IPs from configuration
        if hasattr(self.config, "rate_limit_whitelist"):
            whitelist.update(self.config.rate_limit_whitelist)

        return whitelist

    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted."""
        if ip in self.whitelisted_ips:
            return True

        # Check if IP is in private ranges
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private or ip_obj.is_loopback
        except ValueError:
            return False

    def _cleanup_old_entries(self):
        """Clean up old request timestamps."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # Remove entries older than 1 hour

        for ip, window in list(self.request_windows.items()):
            # Remove old timestamps
            while window and window[0] < cutoff_time:
                window.popleft()

            # Remove empty windows
            if not window:
                del self.request_windows[ip]

        self.last_cleanup = current_time

    def _check_rate_limit(self, ip: str) -> dict | None:
        """
        Check if request should be rate limited.

        Returns:
            None if request is allowed, or dict with error details if rate limited
        """
        if self._is_whitelisted(ip):
            return None

        current_time = time.time()

        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries()

        window = self.request_windows[ip]

        # Check burst limit (requests in last 10 seconds)
        burst_cutoff = current_time - 10
        burst_count = sum(1 for ts in window if ts > burst_cutoff)

        if burst_count >= self.burst_limit:
            return {
                "error": "Rate limit exceeded - too many requests in short time",
                "retry_after": 10,
                "limit_type": "burst",
            }

        # Check per-minute limit
        minute_cutoff = current_time - 60
        minute_count = sum(1 for ts in window if ts > minute_cutoff)

        if minute_count >= self.requests_per_minute:
            return {
                "error": "Rate limit exceeded - too many requests per minute",
                "retry_after": 60,
                "limit_type": "per_minute",
            }

        # Check per-hour limit
        hour_cutoff = current_time - 3600
        hour_count = sum(1 for ts in window if ts > hour_cutoff)

        if hour_count >= self.requests_per_hour:
            return {
                "error": "Rate limit exceeded - too many requests per hour",
                "retry_after": 3600,
                "limit_type": "per_hour",
            }

        # Record this request
        window.append(current_time)

        return None

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        rate_limit_error = self._check_rate_limit(client_ip)

        if rate_limit_error:
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}: {rate_limit_error}"
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": rate_limit_error["error"],
                    "retry_after": rate_limit_error["retry_after"],
                },
                headers={
                    "Retry-After": str(rate_limit_error["retry_after"]),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        window = self.request_windows[client_ip]
        current_time = time.time()
        minute_cutoff = current_time - 60
        minute_count = sum(1 for ts in window if ts > minute_cutoff)
        remaining = max(0, self.requests_per_minute - minute_count)

        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + 60))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers middleware.

    Adds security-related HTTP headers to all responses
    to protect against common web vulnerabilities.
    """

    def __init__(self, app, config: Settings):
        super().__init__(app)
        self.config = config

        # Security headers configuration
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": self._get_csp_policy(),
            "Permissions-Policy": self._get_permissions_policy(),
        }

    def _get_csp_policy(self) -> str:
        """Get Content Security Policy."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

    def _get_permissions_policy(self) -> str:
        """Get Permissions Policy."""
        return (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)

        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value

        # Add server header removal
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Input validation and sanitization middleware.

    Validates and sanitizes incoming requests to prevent
    injection attacks and malformed data processing.
    """

    def __init__(self, app, config: Settings):
        super().__init__(app)
        self.config = config

        # Validation settings
        self.max_content_length = getattr(
            config, "max_content_length", 10 * 1024 * 1024
        )  # 10MB
        self.max_header_length = 8192
        self.max_url_length = 2048

        # Dangerous patterns to detect
        self.dangerous_patterns = [
            b"<script",
            b"javascript:",
            b"vbscript:",
            b"onload=",
            b"onerror=",
            b"eval(",
            b"setTimeout(",
            b"setInterval(",
            b"document.cookie",
            b"document.write",
            b"../",
            b"..\\",
            b"DROP TABLE",
            b"DELETE FROM",
            b"INSERT INTO",
            b"UPDATE SET",
            b"UNION SELECT",
            b"OR 1=1",
            b"AND 1=1",
            b"' OR '1'='1",
            b'" OR "1"="1',
        ]

    async def dispatch(self, request: Request, call_next):
        """Validate and sanitize request."""
        try:
            # Validate request size
            if not await self._validate_request_size(request):
                return JSONResponse(
                    status_code=413, content={"error": "Request too large"}
                )

            # Validate URL length
            if len(str(request.url)) > self.max_url_length:
                return JSONResponse(status_code=414, content={"error": "URL too long"})

            # Validate headers
            if not self._validate_headers(request):
                return JSONResponse(
                    status_code=400, content={"error": "Invalid headers"}
                )

            # Check for dangerous patterns in URL and headers
            if self._contains_dangerous_patterns(str(request.url).encode()):
                logger.warning(f"Dangerous pattern detected in URL: {request.url}")
                return JSONResponse(
                    status_code=400, content={"error": "Invalid request"}
                )

            # Process request
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Input validation error: {e}")
            return JSONResponse(
                status_code=500, content={"error": "Internal server error"}
            )

    async def _validate_request_size(self, request: Request) -> bool:
        """Validate request content length."""
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                length = int(content_length)
                return length <= self.max_content_length
            except ValueError:
                return False

        return True

    def _validate_headers(self, request: Request) -> bool:
        """Validate request headers."""
        for name, value in request.headers.items():
            # Check header length
            if len(name) + len(value) > self.max_header_length:
                return False

            # Check for dangerous patterns in headers
            if self._contains_dangerous_patterns(value.encode()):
                return False

        return True

    def _contains_dangerous_patterns(self, data: bytes) -> bool:
        """Check if data contains dangerous patterns."""
        data_lower = data.lower()

        for pattern in self.dangerous_patterns:
            if pattern in data_lower:
                return True

        return False


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Security audit logging middleware.

    Logs security-relevant events for monitoring and analysis.
    """

    def __init__(self, app, config: Settings):
        super().__init__(app)
        self.config = config
        self.security_logger = logging.getLogger("security_audit")

        # Configure security logging
        if not self.security_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - SECURITY - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.security_logger.addHandler(handler)
            self.security_logger.setLevel(logging.INFO)

    async def dispatch(self, request: Request, call_next):
        """Log security events."""
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")

        # Log authentication attempts
        if request.url.path.startswith("/skills/") or request.url.path == "/a2a":
            auth_header = request.headers.get("authorization")
            if auth_header:
                self.security_logger.info(
                    f"AUTH_ATTEMPT: IP={client_ip}, Path={request.url.path}, "
                    f"Method={request.method}, UserAgent={user_agent}"
                )
            else:
                self.security_logger.warning(
                    f"UNAUTH_ACCESS: IP={client_ip}, Path={request.url.path}, "
                    f"Method={request.method}, UserAgent={user_agent}"
                )

        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # Log suspicious activity
        if response.status_code in [401, 403, 429]:
            self.security_logger.warning(
                f"SECURITY_EVENT: Status={response.status_code}, IP={client_ip}, "
                f"Path={request.url.path}, Method={request.method}, "
                f"ProcessTime={process_time:.3f}s"
            )

        # Log slow requests (potential DoS)
        if process_time > 10.0:
            self.security_logger.warning(
                f"SLOW_REQUEST: IP={client_ip}, Path={request.url.path}, "
                f"ProcessTime={process_time:.3f}s"
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

        return "unknown"


def create_security_middleware_stack(app, config: Settings) -> list:
    """
    Create complete security middleware stack.

    Args:
        app: FastAPI application
        config: Settings configuration

    Returns:
        List of security middleware instances
    """
    return [
        SecurityAuditMiddleware(app, config),
        InputValidationMiddleware(app, config),
        RateLimitingMiddleware(app, config),
        SecurityHeadersMiddleware(app, config),
    ]
