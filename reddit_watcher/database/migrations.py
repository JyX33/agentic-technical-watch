# ABOUTME: Database migration utilities for Alembic integration
# ABOUTME: Provides programmatic database initialization and migration management

import asyncio
import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config
from reddit_watcher.config import get_settings
from reddit_watcher.models import Base

logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration with proper paths."""
    project_root = Path(__file__).parent.parent.parent
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini_path}")

    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(project_root / "alembic"))

    # Set database URL from settings
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.database_url)

    return config


def run_migrations(target_revision: str = "head") -> None:
    """Run Alembic migrations to target revision."""
    try:
        config = get_alembic_config()
        logger.info(f"Running migrations to revision: {target_revision}")
        command.upgrade(config, target_revision)
        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def create_migration(message: str, autogenerate: bool = True) -> str:
    """Create a new Alembic migration."""
    try:
        config = get_alembic_config()
        logger.info(f"Creating migration: {message}")

        # Create the revision
        command.revision(
            config,
            message=message,
            autogenerate=autogenerate,
        )

        logger.info(f"Migration created: {message}")
        return message
    except Exception as e:
        logger.error(f"Failed to create migration: {e}")
        raise


def get_current_revision() -> str | None:
    """Get current database revision."""
    try:
        get_alembic_config()

        # Create a temporary engine to check revision
        settings = get_settings()
        engine = create_engine(settings.database_url)

        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'alembic_version')"
                )
            )
            table_exists = result.scalar()

            if not table_exists:
                return None

            # Get current revision
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            revision = result.scalar()
            return revision

    except Exception as e:
        logger.warning(f"Could not get current revision: {e}")
        return None


def check_migration_status() -> dict[str, any]:
    """Check migration status and return information."""
    try:
        config = get_alembic_config()
        current = get_current_revision()

        return {
            "current_revision": current,
            "migrations_needed": current is None,
            "alembic_config_path": config.config_file_name,
            "database_url": config.get_main_option("sqlalchemy.url"),
        }
    except Exception as e:
        logger.error(f"Failed to check migration status: {e}")
        return {
            "current_revision": None,
            "migrations_needed": True,
            "error": str(e),
        }


def create_all_tables() -> None:
    """Create all tables using SQLAlchemy metadata (for testing)."""
    try:
        settings = get_settings()

        # Use sync engine for table creation
        sync_url = settings.database_url.replace("+asyncpg", "").replace(
            "+psycopg2", ""
        )
        engine = create_engine(sync_url)

        logger.info("Creating all tables using SQLAlchemy metadata")
        Base.metadata.create_all(engine)
        logger.info("All tables created successfully")

    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise


async def create_all_tables_async() -> None:
    """Create all tables using async SQLAlchemy metadata."""
    try:
        settings = get_settings()

        # Ensure async URL
        async_url = settings.database_url
        if not async_url.startswith("postgresql+asyncpg"):
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

        engine = create_async_engine(async_url)

        logger.info("Creating all tables using async SQLAlchemy metadata")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await engine.dispose()
        logger.info("All tables created successfully (async)")

    except Exception as e:
        logger.error(f"Failed to create tables (async): {e}")
        raise


def initialize_database() -> None:
    """Initialize database with migrations or table creation."""
    try:
        status = check_migration_status()

        if status.get("migrations_needed"):
            logger.info("Database not initialized, running initial migration")

            # First, try to create initial migration if none exist
            try:
                create_migration("Initial database schema", autogenerate=True)
            except Exception as e:
                logger.warning(f"Could not create initial migration: {e}")
                # Fallback to direct table creation for development
                logger.info("Falling back to direct table creation")
                create_all_tables()
                return

            # Run migrations
            run_migrations()
        else:
            logger.info(
                f"Database is up to date (revision: {status['current_revision']})"
            )

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def initialize_database_async() -> None:
    """Initialize database asynchronously."""
    try:
        # Run the sync initialization in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, initialize_database)
    except Exception as e:
        logger.error(f"Async database initialization failed: {e}")
        raise


if __name__ == "__main__":
    # CLI interface for migration management
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m reddit_watcher.database.migrations <command>")
        print("Commands: init, migrate, create, status")
        sys.exit(1)

    command_name = sys.argv[1]

    if command_name == "init":
        initialize_database()
    elif command_name == "migrate":
        run_migrations()
    elif command_name == "create":
        if len(sys.argv) < 3:
            print(
                "Usage: python -m reddit_watcher.database.migrations create <message>"
            )
            sys.exit(1)
        message = " ".join(sys.argv[2:])
        create_migration(message)
    elif command_name == "status":
        status = check_migration_status()
        print("Migration Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
    else:
        print(f"Unknown command: {command_name}")
        sys.exit(1)
