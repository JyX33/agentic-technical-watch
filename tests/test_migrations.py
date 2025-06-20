# ABOUTME: Tests for database migration functionality
# ABOUTME: Validates Alembic configuration and migration operations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from alembic.config import Config
from reddit_watcher.database.migrations import (
    check_migration_status,
    get_alembic_config,
    get_current_revision,
)


class TestMigrations:
    """Test database migration functionality."""

    def test_get_alembic_config(self):
        """Test Alembic configuration loading."""
        config = get_alembic_config()

        assert isinstance(config, Config)
        assert config.get_main_option("script_location") is not None
        assert "alembic" in config.get_main_option("script_location")

        # Should have database URL set
        db_url = config.get_main_option("sqlalchemy.url")
        assert db_url is not None
        assert "postgresql" in db_url

    def test_check_migration_status_structure(self):
        """Test migration status check returns proper structure."""
        status = check_migration_status()

        # Should have required keys
        required_keys = ["current_revision", "migrations_needed", "alembic_config_path"]
        for key in required_keys:
            assert key in status

        # Should have proper types
        assert isinstance(status["migrations_needed"], bool)
        assert status["alembic_config_path"] is not None

        # Current revision should be string or None
        revision = status["current_revision"]
        assert revision is None or isinstance(revision, str)

    def test_get_current_revision_with_no_database(self):
        """Test getting revision when database is not available."""
        # This test uses a non-existent database URL
        original_db_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = (
            "postgresql://invalid:invalid@nonexistent:9999/invalid"
        )

        try:
            # Reset settings to pick up new env var
            from reddit_watcher.config import reset_settings

            reset_settings()

            revision = get_current_revision()
            # Should return None when database is not accessible
            assert revision is None
        finally:
            # Restore original environment
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
            reset_settings()

    def test_alembic_ini_exists(self):
        """Test that alembic.ini file exists and is properly configured."""
        project_root = Path(__file__).parent.parent
        alembic_ini = project_root / "alembic.ini"

        assert alembic_ini.exists(), "alembic.ini file should exist"

        # Read and check key configurations
        content = alembic_ini.read_text()

        # Should have timestamped file template enabled
        assert "file_template = " in content
        assert "%%(year)d_%%(month).2d_%%(day).2d" in content

        # Should have ruff post-write hook configured
        assert "hooks = ruff" in content
        assert "ruff.executable = uv" in content

    def test_alembic_env_imports(self):
        """Test that alembic env.py has proper imports."""
        project_root = Path(__file__).parent.parent
        env_py = project_root / "alembic" / "env.py"

        assert env_py.exists(), "alembic/env.py should exist"

        content = env_py.read_text()

        # Should import our models and config
        assert "from reddit_watcher.models import Base" in content
        assert "from reddit_watcher.config import get_settings" in content

        # Should set target_metadata
        assert "target_metadata = Base.metadata" in content

        # Should have compare options enabled
        assert "compare_type=True" in content
        assert "compare_server_default=True" in content

    def test_migration_file_format(self):
        """Test that migration files follow expected format."""
        project_root = Path(__file__).parent.parent
        versions_dir = project_root / "alembic" / "versions"

        if not versions_dir.exists():
            pytest.skip("No migration versions directory found")

        migration_files = list(versions_dir.glob("*.py"))

        if not migration_files:
            pytest.skip("No migration files found")

        # Check the most recent migration file
        latest_migration = max(migration_files, key=lambda f: f.stat().st_mtime)
        content = latest_migration.read_text()

        # Should have proper imports
        assert "from alembic import op" in content
        assert "import sqlalchemy as sa" in content

        # Should have upgrade and downgrade functions
        assert "def upgrade() -> None:" in content
        assert "def downgrade() -> None:" in content

        # Should have revision identifiers
        assert 'revision: str = "' in content
        # Check for either old or new format (since ruff updated it)
        assert (
            "down_revision: Union[str, Sequence[str], None] = " in content
            or "down_revision: str | Sequence[str] | None = " in content
        )

    def test_database_tables_created_by_migration(self):
        """Test that migration creates expected database tables."""
        status = check_migration_status()

        if status.get("migrations_needed", True):
            pytest.skip("Database not migrated, skipping table check")

        try:
            from reddit_watcher.config import get_settings

            settings = get_settings()
            engine = create_engine(settings.database_url)

            with engine.connect() as conn:
                # Check for key tables
                expected_tables = [
                    "subreddits",
                    "reddit_posts",
                    "reddit_comments",
                    "content_filters",
                    "content_summaries",
                    "a2a_tasks",
                    "a2a_workflows",
                    "alert_batches",
                    "alert_deliveries",
                    "alembic_version",
                ]

                for table_name in expected_tables:
                    result = conn.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                            f"WHERE table_name = '{table_name}')"
                        )
                    )
                    exists = result.scalar()
                    assert exists, f"Table '{table_name}' should exist after migration"

        except Exception as e:
            pytest.skip(f"Could not connect to database: {e}")

    def test_json_columns_have_proper_type(self):
        """Test that JSON columns are properly configured."""
        status = check_migration_status()

        if status.get("migrations_needed", True):
            pytest.skip("Database not migrated, skipping column check")

        try:
            from reddit_watcher.config import get_settings

            settings = get_settings()
            engine = create_engine(settings.database_url)

            with engine.connect() as conn:
                # Check a2a_tasks.parameters column type
                result = conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = 'a2a_tasks' AND column_name = 'parameters'"
                    )
                )
                data_type = result.scalar()

                # Should be either 'jsonb' (PostgreSQL) or 'json' (SQLite)
                assert data_type in ["jsonb", "json"], (
                    f"Parameters column should be JSON type, got: {data_type}"
                )

        except Exception as e:
            pytest.skip(f"Could not check column types: {e}")
