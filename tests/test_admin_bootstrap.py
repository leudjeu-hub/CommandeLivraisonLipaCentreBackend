import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.db import async_session_maker
from app.services.admin_bootstrap import ensure_admin
from tests.conftest import make_user


async def test_creates_first_admin(anon_client: AsyncClient) -> None:
    async with async_session_maker() as session:
        message = await ensure_admin(session, "Boss@Shop.cm", "secret-pass")
    assert message == "Administrator boss@shop.cm created"
    response = await anon_client.post(
        "/auth/login", json={"email": "boss@shop.cm", "password": "secret-pass"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


async def test_does_nothing_when_an_admin_exists(anon_client: AsyncClient) -> None:
    async with async_session_maker() as session:
        assert await ensure_admin(session, "boss@shop.cm", "secret-pass") is not None
        assert await ensure_admin(session, "boss@shop.cm", "other-pass") is None
        assert await ensure_admin(session, "second@shop.cm", "secret-pass") is None
    response = await anon_client.post(
        "/auth/login", json={"email": "boss@shop.cm", "password": "secret-pass"}
    )
    assert response.status_code == 200
    response = await anon_client.post(
        "/auth/login", json={"email": "second@shop.cm", "password": "secret-pass"}
    )
    assert response.status_code == 401


async def test_promotes_existing_account_keeping_password(anon_client: AsyncClient) -> None:
    await make_user("client@shop.cm", "client-pass")
    async with async_session_maker() as session:
        message = await ensure_admin(session, "client@shop.cm", "ignored-pass")
    assert message == "Existing account client@shop.cm promoted to administrator"
    response = await anon_client.post(
        "/auth/login", json={"email": "client@shop.cm", "password": "client-pass"}
    )
    assert response.json()["user"]["role"] == "admin"


async def test_rejects_short_password() -> None:
    async with async_session_maker() as session:
        with pytest.raises(ValidationError):
            await ensure_admin(session, "boss@shop.cm", "short")
