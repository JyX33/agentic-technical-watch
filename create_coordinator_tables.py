#!/usr/bin/env python3
# ABOUTME: Create coordinator tables manually for testing
# ABOUTME: Simple script to create the missing tables without complex migration

import asyncio

from reddit_watcher.config import get_settings
from reddit_watcher.models import (
    create_database_engine,
    create_tables,
)


async def create_coordinator_tables():
    """Create the coordinator tables manually."""
    print("🔧 Creating coordinator tables...")

    try:
        settings = get_settings()
        engine = create_database_engine(settings.database_url)

        # This will create only missing tables
        create_tables(engine)

        print("✅ Coordinator tables created successfully!")
        print("   - agent_tasks")
        print("   - workflow_executions")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_coordinator_tables())
