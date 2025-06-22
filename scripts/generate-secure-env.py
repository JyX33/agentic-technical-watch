#!/usr/bin/env python3
"""
ABOUTME: Generate secure environment variables for Reddit Technical Watcher
ABOUTME: Creates strong passwords and API keys for production deployment
"""

import secrets
import string
from pathlib import Path


def generate_password(length: int = 32) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_api_key(length: int = 64) -> str:
    """Generate a secure API key using URL-safe characters."""
    return secrets.token_urlsafe(length)


def main():
    """Generate secure environment variables and update .env file."""
    print("🔐 Generating secure environment variables for Reddit Technical Watcher")
    print("=" * 70)

    # Generate secure credentials
    db_password = generate_password(32)
    redis_password = generate_password(32)
    a2a_api_key = generate_api_key(48)

    # Read the .env.example file
    env_example_path = Path(__file__).parent.parent / ".env.example"
    env_path = Path(__file__).parent.parent / ".env"

    if not env_example_path.exists():
        print(f"❌ .env.example not found at {env_example_path}")
        return

    with open(env_example_path) as f:
        content = f.read()

    # Replace placeholder values with secure ones
    replacements = {
        "CHANGE_ME_STRONG_DB_PASSWORD_HERE": db_password,
        "CHANGE_ME_STRONG_REDIS_PASSWORD_HERE": redis_password,
        "CHANGE_ME_STRONG_A2A_API_KEY_HERE": a2a_api_key,
    }

    for placeholder, secure_value in replacements.items():
        content = content.replace(placeholder, secure_value)

    # Write to .env file
    with open(env_path, "w") as f:
        f.write(content)

    print(f"✅ Secure .env file created at {env_path}")
    print("\n🔑 Generated secure credentials:")
    print(f"   Database Password: {db_password[:8]}... (32 characters)")
    print(f"   Redis Password: {redis_password[:8]}... (32 characters)")
    print(f"   A2A API Key: {a2a_api_key[:12]}... (64 characters)")

    print("\n⚠️  IMPORTANT SECURITY REMINDERS:")
    print("   • Never commit the .env file to version control")
    print("   • Store these credentials securely (password manager)")
    print("   • Rotate credentials regularly in production")
    print("   • Use separate credentials for each environment")
    print(
        "   • Update REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and GEMINI_API_KEY manually"
    )

    print("\n📁 Next steps:")
    print(f"   1. Edit {env_path} and add your API keys")
    print("   2. Run: docker-compose up --build")
    print(
        "   3. For development: docker-compose -f docker-compose.yml -f docker-compose.dev.yml up"
    )


if __name__ == "__main__":
    main()
