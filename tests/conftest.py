import asyncio
import os

# TEST_DATABASE_URL (CI: a PostgreSQL service) runs the suite against a schema built by the Alembic
# migrations, like Neon's, instead of SQLite + create_all: a model the migrations disagree with
# (e.g. an enum stored by name against a CHECK on values) then fails here, not in production.
# The database is wiped first.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or "sqlite+aiosqlite:///./test.db"
os.environ["CREATE_TABLES"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.db import Base, async_session_maker, engine, get_async_session
from app.core.rate_limit import (
    login_throttle,
    order_throttle,
    register_throttle,
    reset_email_throttle,
    reset_throttle,
)
from app.main import app
from app.models.user import UserRole
from app.services.auth_service import AuthService


async def override_get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


app.dependency_overrides[get_async_session] = override_get_async_session

ON_POSTGRES = bool(os.environ.get("TEST_DATABASE_URL"))
sqlite_only = pytest.mark.skipif(ON_POSTGRES, reason="recreates the schema with create_all")


async def _reset_postgres_schema() -> None:
    setup_engine = create_async_engine(get_settings().async_database_url)
    async with setup_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await setup_engine.dispose()


if ON_POSTGRES:
    from app.scripts import migrate

    asyncio.run(_reset_postgres_schema())
    # The same entry point as Render's start command
    migrate.main()


@pytest_asyncio.fixture(autouse=True)
async def create_tables():
    if not ON_POSTGRES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    login_throttle.reset()
    register_throttle.reset()
    order_throttle.reset()
    reset_email_throttle.reset()
    reset_throttle.reset()
    yield
    if ON_POSTGRES:
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        # Each test runs in its own event loop: asyncpg connections cannot be reused across loops.
        await engine.dispose()
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


ADMIN_EMAIL = "admin@test.cm"
ADMIN_PASSWORD = "admin-password"


async def make_user(email: str, password: str, role: UserRole = UserRole.USER) -> str:
    """Create an account and return a bearer token for it."""
    async with async_session_maker() as session:
        service = AuthService(session)
        user = await service.register(email, password, role)
        return await service.create_token(user)


@pytest_asyncio.fixture
async def anon_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client(anon_client: AsyncClient):
    """Client logged in as an administrator (product and order management need it)."""
    token = await make_user(ADMIN_EMAIL, ADMIN_PASSWORD, UserRole.ADMIN)
    anon_client.headers["Authorization"] = f"Bearer {token}"
    yield anon_client
