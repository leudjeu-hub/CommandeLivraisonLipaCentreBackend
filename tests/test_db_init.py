from sqlalchemy import inspect

from app.core.db import Base, engine, initialize_database_if_empty


async def table_names() -> list[str]:
    async with engine.begin() as conn:
        return await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())


async def test_creates_schema_when_database_is_empty() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    assert await initialize_database_if_empty() is True
    names = await table_names()
    assert {"products", "orders", "order_items", "users", "auth_tokens"} <= set(names)


async def test_keeps_existing_schema() -> None:
    assert await initialize_database_if_empty() is False
    assert "products" in await table_names()
