#!/usr/bin/env python3
# ABOUTME: Helper script to guide Reddit research setup
# ABOUTME: Provides instructions and verification for Reddit API configuration

from pathlib import Path


def check_env_file():
    """Check if .env file exists and has required Reddit settings."""
    env_file = Path(".env")

    if not env_file.exists():
        print("❌ .env file not found")
        return False

    required_vars = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]

    env_content = env_file.read_text()
    missing_vars = []

    for var in required_vars:
        if f"{var}=" not in env_content or f"{var}=your_" in env_content:
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing/incomplete Reddit API settings: {', '.join(missing_vars)}")
        return False

    print("✅ Reddit API configuration found")
    return True


def print_setup_instructions():
    """Print instructions for setting up Reddit API credentials."""
    print("""
🔧 Reddit Research Setup Instructions
==================================================

1. **Get Reddit API Credentials:**
   - Go to https://www.reddit.com/prefs/apps
   - Click "Create App" or "Create Another App"
   - Choose "script" as app type
   - Note your Client ID and Client Secret

2. **Create .env file:**
   - Copy .env.example to .env
   - Update these values:
     REDDIT_CLIENT_ID=your_actual_client_id
     REDDIT_CLIENT_SECRET=your_actual_client_secret
     REDDIT_USER_AGENT=Reddit Technical Watcher v1.0.0 by u/YourUsername

3. **Optional: Add Gemini API for summaries:**
   - Get API key from https://ai.google.dev/
   - Set: GEMINI_API_KEY=your_gemini_api_key

4. **Configure Research Topics:**
   - Edit MONITORING_TOPICS in .env
   - Examples: "Python,FastAPI,AI", "cryptocurrency,bitcoin", etc.

==================================================
""")


def main():
    print("🚀 Reddit Research Setup Checker")
    print("=" * 50)

    if check_env_file():
        print("✅ Configuration looks good!")
        print("\n💡 Next steps:")
        print("   1. Start all agent servers")
        print("   2. Run: uv run python tests/integration/test_real_workflow.py")
        print("   3. Configure your research topics in .env")
    else:
        print_setup_instructions()
        print("💡 Run this script again after setting up your .env file")


if __name__ == "__main__":
    main()
