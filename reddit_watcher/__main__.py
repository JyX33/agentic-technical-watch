# ABOUTME: Main entry point for the Reddit Technical Watcher application
# ABOUTME: Handles command-line execution and agent startup coordination

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Main entry point for the Reddit Technical Watcher."""
    print("Reddit Technical Watcher - A2A Agent System")
    print("Starting coordinator agent...")

    # TODO: This will be implemented in Step 11 (CoordinatorAgent)
    # For now, just show that the application can start
    print("Application structure ready. Agent implementations pending.")


if __name__ == "__main__":
    main()
