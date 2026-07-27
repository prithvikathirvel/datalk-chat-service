"""One-off helper to apply SQL migrations in app/sql/migrations against the
configured Postgres database (see app/core/config.py).

Usage:
    python -m scripts.apply_migrations

This is intentionally simple (no migration-tracking table) — the migration
files use `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` so they
are safe to re-run. For anything more advanced (rollback, multi-env tracking)
consider adopting Alembic.
"""

from __future__ import annotations

import asyncio
import glob
import os

import asyncpg

from app.core.config import config


async def apply_migrations() -> None:
    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "app", "sql", "migrations")
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

    if not migration_files:
        print("No migration files found.")
        return

    conn = await asyncpg.connect(
        host=config.DATABASE_HOST,
        port=config.DATABASE_PORT,
        user=config.DATABASE_USER,
        password=config.DATABASE_PASSWORD,
        database=config.DATABASE_NAME,
        ssl="require",
    )
    try:
        for path in migration_files:
            print(f"Applying migration: {os.path.basename(path)}")
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            await conn.execute(sql)
        print("All migrations applied successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply_migrations())
