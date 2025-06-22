# ABOUTME: Authentication middleware for A2A endpoints with API key and JWT token support
# ABOUTME: Provides secure access control for skill invocation endpoints in the Reddit monitoring system


import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from reddit_watcher.config import Settings

security = HTTPBearer()


class AuthMiddleware:
    """
    Authentication middleware for A2A agent endpoints.

    Supports both API key and JWT token authentication methods
    to provide secure access control for skill execution endpoints.
    """

    def __init__(self, config: Settings):
        self.config = config

    async def verify_token(
        self, credentials: HTTPAuthorizationCredentials | None = None
    ) -> str:
        """
        Verify bearer token or API key.

        Args:
            credentials: HTTP authorization credentials from request header

        Returns:
            Authentication subject identifier

        Raises:
            HTTPException: If authentication fails
        """
        if credentials is None:
            raise HTTPException(
                status_code=401, detail="Missing authorization credentials"
            )

        token = credentials.credentials

        # Check API key first
        if self.config.a2a_api_key and token == self.config.a2a_api_key:
            return "api_key"

        # Check JWT token
        if self.config.jwt_secret:
            try:
                payload = jwt.decode(
                    token, self.config.jwt_secret, algorithms=["HS256"]
                )
                return payload.get("sub", "unknown")
            except jwt.InvalidTokenError as e:
                raise HTTPException(
                    status_code=403, detail="Invalid authentication credentials"
                ) from e

        # If no authentication methods are configured or token is invalid
        raise HTTPException(
            status_code=403, detail="Invalid authentication credentials"
        )
