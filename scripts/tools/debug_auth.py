# ABOUTME: Debug script to check authentication configuration and API key setup
# ABOUTME: Helps troubleshoot why authentication tests are failing

import os

from reddit_watcher.auth_middleware import AuthMiddleware
from reddit_watcher.config import Settings


def debug_auth():
    """Debug authentication configuration."""

    # Test with environment variable
    os.environ["A2A_API_KEY"] = "test-security-simple-key-xyz789"

    config = Settings()
    print(f"Config a2a_api_key: '{config.a2a_api_key}'")
    print(f"Config jwt_secret: '{config.jwt_secret}'")
    print(f"Environment A2A_API_KEY: '{os.getenv('A2A_API_KEY')}'")

    # Manually set the API key
    config.a2a_api_key = "test-security-simple-key-xyz789"
    print(f"After manual set - Config a2a_api_key: '{config.a2a_api_key}'")

    AuthMiddleware(config)

    # Test token matching
    test_token = "test-security-simple-key-xyz789"
    print(f"Test token: '{test_token}'")
    print(f"Token matches: {config.a2a_api_key == test_token}")
    print(f"Config has api key: {bool(config.a2a_api_key)}")
    print(f"Config has jwt secret: {bool(config.jwt_secret)}")

    # Test direct comparison
    if config.a2a_api_key and test_token == config.a2a_api_key:
        print("✓ Direct comparison would succeed")
    else:
        print("✗ Direct comparison would fail")


if __name__ == "__main__":
    debug_auth()
