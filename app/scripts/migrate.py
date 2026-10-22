"""Bring the database schema to the latest Alembic revision.

Databases created by `create_all` (CREATE_TABLES=true) have no `alembic_version` table, so
`alembic upgrade head` would try to create the existing tables again. Such databases are
stamped with the revision matching their schema first.

Usage: uv run python -m app.scripts.migrate
"""

import asyncio

from alembic.config import Config
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings


def detect_unversioned_revision(conn: Connection) -> str | None:
    """Return the revision to stamp an unversioned database with, or None."""
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables or "products" not in tables:
        return None
    if "time_entries" in tables:
        return "head"
    if "users" in tables:
        return "0003"
    columns = {column["name"] for column in inspector.get_columns("products")}
    return "0002" if "category" in columns else "0001"


async def _detect() -> str | None:
    engine = create_async_engine(get_settings().async_database_url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(detect_unversioned_revision)
    finally:
        await engine.dispose()


def main() -> None:
    config = Config("alembic.ini")
    revision = asyncio.run(_detect())
    if revision is not None:
        print(f"Unversioned database, stamping {revision}")
        command.stamp(config, revision)
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
