from httpx import AsyncClient

from app.models.user import UserRole
from tests.conftest import make_user


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _id(client: AsyncClient, email: str) -> int:
    return next(u["id"] for u in (await client.get("/users/")).json() if u["email"] == email)


async def test_blocked_account_cannot_log_in_or_use_its_session(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    token = await make_user("bob@exemple.cm", "motdepasse")
    bob = await _id(client, "bob@exemple.cm")
    admin_auth = client.headers.pop("Authorization")

    assert (await anon_client.get("/auth/me", headers=bearer(token))).status_code == 200
    blocked = await anon_client.patch(
        f"/users/{bob}/active", json={"active": False}, headers={"Authorization": admin_auth}
    )
    assert blocked.status_code == 200
    assert blocked.json()["is_active"] is False
    assert (await anon_client.get("/auth/me", headers=bearer(token))).status_code == 401
    login = {"email": "bob@exemple.cm", "password": "motdepasse"}
    refused = await anon_client.post("/auth/login", json=login)
    assert refused.status_code == 403
    # A wrong password still gets the generic answer.
    wrong = await anon_client.post("/auth/login", json={**login, "password": "mauvais"})
    assert wrong.status_code == 401

    await anon_client.patch(
        f"/users/{bob}/active", json={"active": True}, headers={"Authorization": admin_auth}
    )
    assert (await anon_client.post("/auth/login", json=login)).status_code == 200


async def test_admin_cannot_block_or_delete_self(client: AsyncClient) -> None:
    me = (await client.get("/auth/me")).json()["id"]
    assert (await client.patch(f"/users/{me}/active", json={"active": False})).status_code == 409
    assert (await client.delete(f"/users/{me}")).status_code == 409


async def test_last_active_admin_is_protected(client: AsyncClient) -> None:
    await make_user("other@exemple.cm", "motdepasse", UserRole.ADMIN)
    other = await _id(client, "other@exemple.cm")
    me = (await client.get("/auth/me")).json()["id"]
    # Two admins: blocking one is fine, then the remaining one cannot be demoted.
    assert (await client.patch(f"/users/{other}/active", json={"active": False})).status_code == 200
    assert (await client.patch(f"/users/{me}/role", json={"role": "user"})).status_code == 409


async def test_delete_account_unless_it_has_hours(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    await make_user("client@exemple.cm", "motdepasse")
    emp_token = await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE)
    await anon_client.post("/time/me/clock-in", headers=bearer(emp_token))

    customer = await _id(client, "client@exemple.cm")
    assert (await client.delete(f"/users/{customer}")).status_code == 204
    assert (await client.delete(f"/users/{customer}")).status_code == 404

    emp = await _id(client, "emp@exemple.cm")
    kept = await client.delete(f"/users/{emp}")
    assert kept.status_code == 409
    assert "block it instead" in kept.json()["detail"]


async def test_account_management_requires_admin(anon_client: AsyncClient) -> None:
    boss = bearer(await make_user("resp@exemple.cm", "motdepasse", UserRole.MANAGER))
    assert (
        await anon_client.patch("/users/1/active", json={"active": False}, headers=boss)
    ).status_code == 403
    assert (await anon_client.delete("/users/1", headers=boss)).status_code == 403


async def test_admin_gives_a_temporary_password(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    token = await make_user("awa@exemple.cm", "ancienmotdepasse")
    awa = await _id(client, "awa@exemple.cm")

    reset = await client.post(f"/users/{awa}/password")
    assert reset.status_code == 200
    password = reset.json()["password"]
    assert len(password) == 10
    # The old password and the open session stop working; the new password works.
    assert (await anon_client.get("/auth/me", headers=bearer(token))).status_code == 401
    old = {"email": "awa@exemple.cm", "password": "ancienmotdepasse"}
    assert (await anon_client.post("/auth/login", json=old)).status_code == 401
    new = {"email": "awa@exemple.cm", "password": password}
    assert (await anon_client.post("/auth/login", json=new)).status_code == 200


async def test_temporary_password_is_admin_only_and_not_for_oneself(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    token = await make_user("bob@exemple.cm", "motdepasse")
    bob = await _id(client, "bob@exemple.cm")
    me = (await client.get("/auth/me")).json()["id"]

    assert (await client.post(f"/users/{me}/password")).status_code == 409
    assert (await client.post("/users/99999/password")).status_code == 404
    refused = await anon_client.post(f"/users/{bob}/password", headers=bearer(token))
    assert refused.status_code == 403
