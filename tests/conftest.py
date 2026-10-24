import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["CREATE_TABLES"] = "false"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base, async_session_maker, engine, get_async_session
from app.core.rate_limit import login_throttle, order_throttle, register_throttle
from app.main import app
from app.models.user import UserRole
from app.services.auth_service import AuthService


async def override_get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


app.dependency_overrides[get_async_session] = override_get_async_session


@pytest_asyncio.fixture(autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    login_throttle.reset()
    register_throttle.reset()
    order_throttle.reset()
    yield
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
