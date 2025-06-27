#!/usr/bin/env python3
"""
Migration Safety Toolkit for Reddit Technical Watcher

ABOUTME: Database migration safety tools including backup, rollback, and validation procedures
ABOUTME: Provides automated safety checks and recovery procedures for Alembic migrations

Usage:
    python migration_safety_toolkit.py backup
    python migration_safety_toolkit.py validate
    python migration_safety_toolkit.py rollback <revision>
    python migration_safety_toolkit.py emergency-restore <backup_file>
"""

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from reddit_watcher.config import Settings


class MigrationSafetyToolkit:
    """Database migration safety and recovery toolkit."""

    def __init__(self):
        self.settings = Settings()
        self.engine = create_engine(self.settings.database_url)
        self.backup_dir = Path("database_backups")
        self.backup_dir.mkdir(exist_ok=True)

    def get_current_migration(self) -> str | None:
        """Get current Alembic migration revision."""
        try:
            result = subprocess.run(
                ["uv", "run", "alembic", "current", "--verbose"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Parse revision from output
            for line in result.stdout.split("\n"):
                if line.startswith("Rev:"):
                    return line.split()[1]
            return None
        except subprocess.CalledProcessError as e:
            print(f"Error getting current migration: {e}")
            return None

    def create_backup(self) -> Path | None:
        """Create full database backup using pg_dump."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        current_rev = self.get_current_migration() or "unknown"
        backup_file = self.backup_dir / f"backup_{timestamp}_rev_{current_rev}.sql"

        # Parse database URL for pg_dump
        from urllib.parse import urlparse

        parsed = urlparse(self.settings.database_url)

        pg_dump_cmd = [
            "pg_dump",
            "-h",
            parsed.hostname or "localhost",
            "-p",
            str(parsed.port or 5432),
            "-U",
            parsed.username or "postgres",
            "-d",
            parsed.path.lstrip("/") if parsed.path else "reddit_watcher",
            "-f",
            str(backup_file),
        ]

        try:
            print(f"Creating database backup: {backup_file}")
            subprocess.run(pg_dump_cmd, check=True)
            print(f"✅ Backup created successfully: {backup_file}")

            # Also save migration state
            state_file = backup_file.with_suffix(".migration_state")
            with open(state_file, "w") as f:
                result = subprocess.run(
                    ["uv", "run", "alembic", "history", "--verbose"],
                    capture_output=True,
                    text=True,
                )
                f.write(result.stdout)

            return backup_file

        except subprocess.CalledProcessError as e:
            print(f"❌ Backup failed: {e}")
            return None

    def validate_schema(self) -> bool:
        """Validate database schema after migration."""
        expected_tables = [
            "a2a_tasks",
            "a2a_workflows",
            "alert_batches",
            "alert_deliveries",
            "subreddits",
            "reddit_posts",
            "reddit_comments",
            "content_filters",
            "content_summaries",
            "agent_tasks",
            "workflow_executions",
            "agent_states",
            "task_recoveries",
            "content_deduplication",
            "alembic_version",
        ]

        try:
            with self.engine.connect() as conn:
                # Check tables exist
                result = conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
                existing_tables = {row[0] for row in result}

                missing_tables = set(expected_tables) - existing_tables
                extra_tables = existing_tables - set(expected_tables)

                print("📊 Schema Validation Results:")
                print(f"   Expected tables: {len(expected_tables)}")
                print(f"   Found tables: {len(existing_tables)}")

                if missing_tables:
                    print(f"   ❌ Missing tables: {missing_tables}")
                    return False

                if extra_tables:
                    print(f"   ⚠️  Extra tables: {extra_tables}")

                # Check foreign key constraints
                fk_result = conn.execute(
                    text("""
                    SELECT COUNT(*) FROM information_schema.table_constraints
                    WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public'
                """)
                )
                fk_count = fk_result.scalar()
                print(f"   🔗 Foreign key constraints: {fk_count}")

                # Check indexes
                idx_result = conn.execute(
                    text("""
                    SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public'
                """)
                )
                idx_count = idx_result.scalar()
                print(f"   📈 Indexes: {idx_count}")

                print("✅ Schema validation passed")
                return True

        except Exception as e:
            print(f"❌ Schema validation failed: {e}")
            return False

    def rollback_migration(self, target_revision: str) -> bool:
        """Rollback to specific migration revision."""
        try:
            print(f"🔄 Rolling back to revision: {target_revision}")

            # Create backup before rollback
            backup_file = self.create_backup()
            if not backup_file:
                print("❌ Cannot rollback without backup")
                return False

            # Perform rollback
            subprocess.run(
                ["uv", "run", "alembic", "downgrade", target_revision], check=True
            )

            print(f"✅ Rollback completed to revision: {target_revision}")

            # Validate after rollback
            if self.validate_schema():
                print("✅ Post-rollback validation passed")
                return True
            else:
                print("⚠️  Post-rollback validation issues detected")
                return False

        except subprocess.CalledProcessError as e:
            print(f"❌ Rollback failed: {e}")
            return False

    def emergency_restore(self, backup_file: Path) -> bool:
        """Emergency restore from backup file."""
        if not backup_file.exists():
            print(f"❌ Backup file not found: {backup_file}")
            return False

        # Parse database URL
        from urllib.parse import urlparse

        parsed = urlparse(self.settings.database_url)
        db_name = parsed.path.lstrip("/") if parsed.path else "reddit_watcher"

        try:
            print(f"🚨 EMERGENCY RESTORE from {backup_file}")
            print("⚠️  This will DROP and RECREATE the database!")

            confirmation = input("Type 'CONFIRM' to proceed: ")
            if confirmation != "CONFIRM":
                print("❌ Restore cancelled")
                return False

            # Drop and recreate database
            drop_cmd = [
                "dropdb",
                "-h",
                parsed.hostname or "localhost",
                "-p",
                str(parsed.port or 5432),
                "-U",
                parsed.username or "postgres",
                db_name,
            ]
            subprocess.run(drop_cmd, check=True)

            create_cmd = [
                "createdb",
                "-h",
                parsed.hostname or "localhost",
                "-p",
                str(parsed.port or 5432),
                "-U",
                parsed.username or "postgres",
                db_name,
            ]
            subprocess.run(create_cmd, check=True)

            # Restore from backup
            restore_cmd = [
                "psql",
                "-h",
                parsed.hostname or "localhost",
                "-p",
                str(parsed.port or 5432),
                "-U",
                parsed.username or "postgres",
                "-d",
                db_name,
                "-f",
                str(backup_file),
            ]
            subprocess.run(restore_cmd, check=True)

            print("✅ Emergency restore completed")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Emergency restore failed: {e}")
            return False

    def list_backups(self) -> list[Path]:
        """List available backup files."""
        backups = list(self.backup_dir.glob("backup_*.sql"))
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return backups

    def migration_safety_check(self) -> bool:
        """Comprehensive migration safety check."""
        print("🔍 Migration Safety Check")
        print("=" * 50)

        # Check 1: Database connectivity
        try:
            with self.engine.connect():
                print("✅ Database connection: OK")
        except Exception as e:
            print(f"❌ Database connection: FAILED ({e})")
            return False

        # Check 2: Current migration state
        current_rev = self.get_current_migration()
        if current_rev:
            print(f"✅ Current migration: {current_rev}")
        else:
            print("⚠️  Cannot determine migration state")

        # Check 3: Backup availability
        backups = self.list_backups()
        if backups:
            latest_backup = backups[0]
            backup_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                latest_backup.stat().st_mtime
            )
            print(
                f"✅ Latest backup: {latest_backup.name} ({backup_age.total_seconds() / 3600:.1f}h old)"
            )
        else:
            print("⚠️  No backups available")

        # Check 4: Disk space
        import shutil

        free_space = shutil.disk_usage(".").free / (1024**3)  # GB
        print(f"✅ Available disk space: {free_space:.1f} GB")

        print("=" * 50)
        print("✅ Safety check completed")
        return True


def main():
    """Command-line interface for migration safety toolkit."""
    parser = argparse.ArgumentParser(description="Migration Safety Toolkit")
    parser.add_argument(
        "command",
        choices=[
            "backup",
            "validate",
            "rollback",
            "emergency-restore",
            "list-backups",
            "safety-check",
        ],
    )
    parser.add_argument("target", nargs="?", help="Target revision or backup file")

    args = parser.parse_args()
    toolkit = MigrationSafetyToolkit()

    try:
        if args.command == "backup":
            backup_file = toolkit.create_backup()
            sys.exit(0 if backup_file else 1)

        elif args.command == "validate":
            success = toolkit.validate_schema()
            sys.exit(0 if success else 1)

        elif args.command == "rollback":
            if not args.target:
                print("❌ Rollback target revision required")
                sys.exit(1)
            success = toolkit.rollback_migration(args.target)
            sys.exit(0 if success else 1)

        elif args.command == "emergency-restore":
            if not args.target:
                print("❌ Backup file path required")
                sys.exit(1)
            backup_path = Path(args.target)
            success = toolkit.emergency_restore(backup_path)
            sys.exit(0 if success else 1)

        elif args.command == "list-backups":
            backups = toolkit.list_backups()
            if backups:
                print("Available backups:")
                for backup in backups:
                    mtime = datetime.datetime.fromtimestamp(backup.stat().st_mtime)
                    size_kb = backup.stat().st_size / 1024
                    print(f"  {backup.name} ({mtime:%Y-%m-%d %H:%M}, {size_kb:.1f} KB)")
            else:
                print("No backups found")
            sys.exit(0)

        elif args.command == "safety-check":
            success = toolkit.migration_safety_check()
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
