#!/usr/bin/env python3
"""
Automated Database Migration & Rollback Runner CLI for CV Analyzer backend.
Supports PostgreSQL dialect, SHA-256 checksum verification,
schema migration tracking, step-down rollbacks (*_down.sql), and dry-run previews.
"""

import argparse
import hashlib
import sys
from datetime import timezone, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

# Add backend directory to sys.path if invoked from root
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings


def compute_checksum(content: str) -> str:
    """Computes normalized SHA-256 checksum of SQL script content."""
    normalized_content = content.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()


def get_db_url() -> str:
    """
    Detects target database URL for PostgreSQL.
    """
    if not settings.POSTGRES_APP_URL:
        raise ValueError("POSTGRES_APP_URL is not configured in settings.")
    return settings.POSTGRES_APP_URL


def ensure_migrations_table(conn, dialect: str = "postgres"):
    """Ensures cvai.schema_migrations tracking table exists in the target database."""
    if dialect.lower() == "mssql":
        raise ValueError("MSSQL dialect is permanently disabled.")
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS cvai;"))
    conn.execute(
        text("""
        CREATE TABLE IF NOT EXISTS cvai.schema_migrations (
            version VARCHAR(50) PRIMARY KEY,
            migration_name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            checksum VARCHAR(64)
        );
    """)
    )


def get_applied_migrations(conn) -> dict[str, dict[str, Any]]:
    """Fetches dictionary of applied migrations keyed by version."""
    query = text("SELECT version, migration_name, applied_at, checksum FROM cvai.schema_migrations ORDER BY version")
    rows = conn.execute(query).fetchall()
    applied = {}
    for r in rows:
        applied[r[0]] = {
            "version": r[0],
            "migration_name": r[1],
            "applied_at": str(r[2]),
            "checksum": r[3],
        }
    return applied


def get_migration_files(mode: str = "up", dialect: str = "postgres") -> list[Path]:
    """
    Returns sorted list of .sql migration files for postgres.
    mode='up' returns forward migrations (excluding *_down.sql).
    mode='down' returns rollback migrations (only *_down.sql).
    """
    if dialect.lower() == "mssql":
        raise ValueError("MSSQL dialect is permanently disabled.")
    migrations_dir = script_dir / "migrations" / "postgres"
    if not migrations_dir.exists():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")

    if mode == "down":
        files = sorted(migrations_dir.glob("*_down.sql"))
    else:
        files = sorted([f for f in migrations_dir.glob("*.sql") if not f.name.endswith("_down.sql")])
    return files


def run_status(db_url: str, dialect: str = "postgres"):
    """Displays migration status table in terminal."""
    if dialect.lower() == "mssql":
        raise ValueError("MSSQL dialect is permanently disabled.")
    engine = create_engine(db_url)
    up_files = get_migration_files(mode="up")
    down_files = get_migration_files(mode="down")
    down_names = {f.name for f in down_files}

    with engine.begin() as conn:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)

    print("\n" + "=" * 85)
    print(f"DATABASE MIGRATION STATUS (POSTGRESQL)")
    print("=" * 85)
    print(f"{'VERSION':<10} | {'MIGRATION NAME':<38} | {'STATUS':<10} | {'REVERSAL SCRIPT'}")
    print("-" * 85)

    for file_path in up_files:
        version = file_path.name.split("_")[0]
        content = file_path.read_text(encoding="utf-8")
        current_checksum = compute_checksum(content)

        down_name = file_path.name.replace(".sql", "_down.sql")
        has_down = "AVAILABLE" if down_name in down_names else "MISSING"

        if version in applied:
            recorded_checksum = applied[version]["checksum"]
            status = "APPLIED" if recorded_checksum == current_checksum else "MODIFIED!"
        else:
            status = "PENDING"

        print(f"{version:<10} | {file_path.name:<38} | {status:<10} | {has_down}")

    print("=" * 85 + "\n")


def run_migrations(db_url: str, dry_run: bool = False, dialect: str = "postgres"):
    """Executes pending database migrations."""
    if dialect.lower() == "mssql":
        raise ValueError("MSSQL dialect is permanently disabled.")
    engine = create_engine(db_url)
    files = get_migration_files(mode="up")

    print(f"\n[MIGRATION RUNNER] Dialect: POSTGRESQL")
    print(f"[MIGRATION RUNNER] Dry Run: {dry_run}")
    print(f"[MIGRATION RUNNER] Target Directory: {script_dir / 'migrations' / 'postgres'}\n")

    with engine.begin() as conn:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)

    pending_count = 0
    for file_path in files:
        version = file_path.name.split("_")[0]
        migration_name = file_path.name
        content = file_path.read_text(encoding="utf-8")
        checksum = compute_checksum(content)

        if version in applied:
            recorded_checksum = applied[version]["checksum"]
            if recorded_checksum and recorded_checksum != checksum:
                print(f"⚠️  WARNING: Checksum mismatch for already applied migration {version} ({file_path.name})")
            continue

        pending_count += 1
        print(f"🚀 Processing [{version}] {file_path.name}...")

        if dry_run:
            print(f"   [DRY-RUN] Would execute {len(content)} bytes (Checksum: {checksum[:12]}...)")
            continue

        # Execute migration inside transaction
        try:
            with engine.begin() as conn:
                conn.execute(text(content))
                now = datetime.now(timezone.utc)
                conn.execute(
                    text("""
                    INSERT INTO cvai.schema_migrations (version, migration_name, applied_at, checksum)
                    VALUES (:version, :name, :applied_at, :checksum)
                    ON CONFLICT (version) DO UPDATE 
                    SET applied_at = EXCLUDED.applied_at, checksum = EXCLUDED.checksum;
                """),
                    {
                        "version": version,
                        "name": migration_name,
                        "applied_at": now,
                        "checksum": checksum,
                    },
                )

            print(f"✅ Applied [{version}] {file_path.name} successfully.")
        except Exception as err:
            print(f"❌ ERROR executing [{version}] {file_path.name}: {err}")
            sys.exit(1)

    if pending_count == 0:
        print("✨ Database schema is up-to-date. No pending migrations.")
    elif dry_run:
        print(f"\n🔍 [DRY-RUN COMPLETE] {pending_count} pending migration(s) ready to execute.")
    else:
        print(f"\n🎉 [MIGRATIONS COMPLETE] Successfully applied {pending_count} migration(s).")


def run_rollback(db_url: str, steps: str = "1", dry_run: bool = False, dialect: str = "postgres"):
    """Rolls back applied migrations in reverse order using *_down.sql scripts."""
    if dialect.lower() == "mssql":
        raise ValueError("MSSQL dialect is permanently disabled.")
    engine = create_engine(db_url)
    down_files = get_migration_files(mode="down")
    down_map = {f.name.replace("_down.sql", ".sql"): f for f in down_files}

    print(f"\n[MIGRATION ROLLBACK] Dialect: POSTGRESQL")
    print(f"[MIGRATION ROLLBACK] Dry Run: {dry_run}")
    print(f"[MIGRATION ROLLBACK] Requested Rollback Steps: {steps}\n")

    with engine.begin() as conn:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)

    if not applied:
        print("✨ No applied migrations found to roll back.")
        return

    applied_versions = sorted(applied.keys(), reverse=True)
    if steps.lower() != "all":
        try:
            limit = int(steps)
            applied_versions = applied_versions[:limit]
        except ValueError:
            print(f"❌ Invalid --rollback steps count: '{steps}'. Expected an integer or 'all'.")
            sys.exit(1)

    rolled_back_count = 0
    for version in applied_versions:
        migration_info = applied[version]
        forward_name = migration_info["migration_name"]
        down_file = down_map.get(forward_name)

        if not down_file or not down_file.exists():
            print(f"⚠️  WARNING: Down migration file missing for [{version}] {forward_name}. Skipping rollback.")
            continue

        rolled_back_count += 1
        content = down_file.read_text(encoding="utf-8")
        print(f"🔄 Rolling back [{version}] {forward_name} using {down_file.name}...")

        if dry_run:
            print(f"   [DRY-RUN] Would execute rollback {len(content)} bytes.")
            continue

        try:
            with engine.begin() as conn:
                conn.execute(text(content))

                conn.execute(
                    text("DELETE FROM cvai.schema_migrations WHERE version = :version"),
                    {"version": version},
                )
            print(f"✅ Rolled back [{version}] {forward_name} successfully.")
        except Exception as err:
            print(f"❌ ERROR rolling back [{version}] {forward_name}: {err}")
            sys.exit(1)

    if dry_run:
        print(f"\n🔍 [ROLLBACK DRY-RUN COMPLETE] {rolled_back_count} migration(s) ready to roll back.")
    else:
        print(f"\n🎉 [ROLLBACK COMPLETE] Successfully rolled back {rolled_back_count} migration(s).")


def main():
    parser = argparse.ArgumentParser(description="CV Analyzer Database Migration & Rollback Runner")
    parser.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Display migration status table and exit",
    )
    parser.add_argument(
        "--audit",
        "-a",
        action="store_true",
        help="Audit database schema for drift, missing elements, and checksum tampering",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migrations or rollback without executing",
    )
    parser.add_argument(
        "--rollback",
        "-r",
        nargs="?",
        const="1",
        help="Roll back applied migrations. Specify step count (e.g. 1, 2) or 'all' (default: 1)",
    )

    args = parser.parse_args()

    try:
        db_url = get_db_url()
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if args.audit:
        from scripts.verify_schema_drift import audit_schema_drift
        healthy = audit_schema_drift()
        sys.exit(0 if healthy else 1)
    elif args.status:
        run_status(db_url)
    elif args.rollback is not None:
        run_rollback(db_url, steps=args.rollback, dry_run=args.dry_run)
    else:
        run_migrations(db_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
