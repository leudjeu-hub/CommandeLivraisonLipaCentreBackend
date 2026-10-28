from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.db import async_session_maker
from app.core.exceptions import EmailAlreadyUsedError
from app.core.rate_limit import MAX_FAILURES, MAX_REGISTRATIONS
from app.core.security import hash_password, verify_password
from app.models.user import AuthToken, User, UserRole
from app.scripts.create_admin import create_admin
from app.scripts.migrate import detect_unversioned_revision
from app.services.auth_service import AuthService
from tests.conftest import ADMIN_EMAIL, make_user, sqlite_only

PRODUCT = {"category": "Scolaire", "name": "Stylo", "price": 500, "stock": 10}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_password_hash_roundtrip() -> None:
    stored = hash_password("secret-123")
    assert stored.startswith("scrypt$")
    assert "secret-123" not in stored
    assert verify_password("secret-123", stored)
    assert not verify_password("secret-124", stored)
    assert not verify_password("secret-123", "not-a-hash")


async def test_register_login_me_logout(anon_client: AsyncClient) -> None:
    response = await anon_client.post(
        "/auth/register", json={"email": " Client@Exemple.CM ", "password": "motdepasse"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "client@exemple.cm"
    assert body["user"]["role"] == "user"
    assert "password_hash" not in body["user"]

    login = await anon_client.post(
        "/auth/login", json={"email": "CLIENT@exemple.cm", "password": "motdepasse"}
    )
    assert login.status_code == 200
    token = login.json()["token"]

    me = await anon_client.get("/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["email"] == "client@exemple.cm"

    assert (await anon_client.post("/auth/logout", headers=bearer(token))).status_code == 204
    assert (await anon_client.get("/auth/me", headers=bearer(token))).status_code == 401


async def test_register_rejects_duplicate_and_weak_input(anon_client: AsyncClient) -> None:
    ok = {"email": "a@exemple.cm", "password": "motdepasse"}
    assert (await anon_client.post("/auth/register", json=ok)).status_code == 201
    duplicate = await anon_client.post(
        "/auth/register", json={"email": "A@exemple.cm", "password": "autre-mdp"}
    )
    assert duplicate.status_code == 409
    short = await anon_client.post(
        "/auth/register", json={"email": "b@exemple.cm", "password": "court"}
    )
    assert short.status_code == 422
    bad_email = await anon_client.post(
        "/auth/register", json={"email": "pas-un-email", "password": "motdepasse"}
    )
    assert bad_email.status_code == 422


async def test_login_failures_look_the_same(anon_client: AsyncClient) -> None:
    await make_user("c@exemple.cm", "motdepasse")
    wrong = await anon_client.post(
        "/auth/login", json={"email": "c@exemple.cm", "password": "mauvais"}
    )
    unknown = await anon_client.post(
        "/auth/login", json={"email": "inconnu@exemple.cm", "password": "motdepasse"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_missing_invalid_and_expired_tokens(anon_client: AsyncClient) -> None:
    missing = await anon_client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert (await anon_client.get("/auth/me", headers=bearer("faux"))).status_code == 401

    token = await make_user("d@exemple.cm", "motdepasse")
    async with async_session_maker() as session:
        await session.execute(
            update(AuthToken).values(expires_at=datetime.now() - timedelta(minutes=1))
        )
        await session.commit()
    assert (await anon_client.get("/auth/me", headers=bearer(token))).status_code == 401


async def test_tokens_are_stored_hashed(anon_client: AsyncClient) -> None:
    token = await make_user("e@exemple.cm", "motdepasse")
    async with async_session_maker() as session:
        stored = (await session.execute(select(AuthToken.token_hash))).scalars().all()
    assert stored and token not in stored


async def test_product_writes_require_admin(anon_client: AsyncClient) -> None:
    assert (await anon_client.post("/products/", json=PRODUCT)).status_code == 401
    user_token = await make_user("f@exemple.cm", "motdepasse")
    as_user = await anon_client.post("/products/", json=PRODUCT, headers=bearer(user_token))
    assert as_user.status_code == 403
    assert (await anon_client.put("/products/1", json={"name": "X"})).status_code == 401
    assert (await anon_client.delete("/products/1")).status_code == 401
    # Reading the catalogue stays public.
    assert (await anon_client.get("/products/")).status_code == 200


async def test_orders_are_admin_only(client: AsyncClient, anon_client: AsyncClient) -> None:
    product = (await client.post("/products/", json=PRODUCT)).json()
    admin_auth = client.headers.pop("Authorization")  # same underlying client: go anonymous

    order = await anon_client.post(
        "/orders/",
        json={
            "customer_name": "Awa",
            "phone": "+237600000000",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    # Creating an order takes stock: anonymous visitors must not be able to empty it.
    assert order.status_code == 401
    anon_client.headers["Authorization"] = admin_auth
    order = await anon_client.post(
        "/orders/",
        json={
            "customer_name": "Awa",
            "phone": "+237600000000",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    assert order.status_code == 201
    order_id = order.json()["id"]
    anon_client.headers.pop("Authorization")
    assert (await anon_client.get("/orders/")).status_code == 401
    assert (await anon_client.get(f"/orders/{order_id}")).status_code == 401
    status = await anon_client.patch(f"/orders/{order_id}/status", json={"status": "confirmed"})
    assert status.status_code == 401

    anon_client.headers["Authorization"] = admin_auth
    assert (await anon_client.get("/orders/")).status_code == 200


async def test_admin_promotes_and_demotes(client: AsyncClient) -> None:
    await make_user("g@exemple.cm", "motdepasse")
    users = (await client.get("/users/")).json()
    assert [u["email"] for u in users] == [ADMIN_EMAIL, "g@exemple.cm"]
    user_id = users[1]["id"]

    promoted = await client.patch(f"/users/{user_id}/role", json={"role": "admin"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"
    demoted = await client.patch(f"/users/{user_id}/role", json={"role": "user"})
    assert demoted.json()["role"] == "user"

    assert (await client.patch("/users/999/role", json={"role": "admin"})).status_code == 404
    bad = await client.patch(f"/users/{user_id}/role", json={"role": "chef"})
    assert bad.status_code == 422


async def test_last_admin_cannot_be_demoted(client: AsyncClient) -> None:
    admin_id = (await client.get("/auth/me")).json()["id"]
    response = await client.patch(f"/users/{admin_id}/role", json={"role": "user"})
    assert response.status_code == 409


async def test_user_management_requires_admin(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/users/")).status_code == 401
    token = await make_user("h@exemple.cm", "motdepasse")
    assert (await anon_client.get("/users/", headers=bearer(token))).status_code == 403
    response = await anon_client.patch(
        "/users/1/role", json={"role": "admin"}, headers=bearer(token)
    )
    assert response.status_code == 403


async def test_create_admin_script() -> None:
    message = await create_admin("Boss@Exemple.cm", "motdepasse")
    assert message == "Administrator boss@exemple.cm created."
    await make_user("i@exemple.cm", "motdepasse")
    message = await create_admin("i@exemple.cm", None)
    assert "now an administrator" in message
    async with async_session_maker() as session:
        service = AuthService(session)
        user = await service.get_by_email("i@exemple.cm")
        assert user is not None and user.role == UserRole.ADMIN
        # Existing password unchanged
        assert await service.authenticate("i@exemple.cm", "motdepasse")


@sqlite_only
async def test_migrate_stamps_unversioned_database_with_users_table() -> None:
    async with async_session_maker() as session:
        conn = await session.connection()
        # Tables come from create_all (conftest): products has `category` and users exists.
        assert await conn.run_sync(detect_unversioned_revision) == "head"
        assert (await session.execute(select(User))).first() is None


async def test_register_race_on_same_email_gives_409() -> None:
    # The pre-check misses a concurrent sign-up; the unique index must still give a clean 409.
    async with async_session_maker() as session:
        service = AuthService(session)
        await service.register("j@exemple.cm", "motdepasse")
        service.get_by_email = lambda email: _none()  # type: ignore[method-assign]
        try:
            await service.register("j@exemple.cm", "motdepasse")
        except EmailAlreadyUsedError:
            pass
        else:
            raise AssertionError("expected EmailAlreadyUsedError")


async def _none() -> None:
    return None


async def test_login_is_throttled_after_repeated_failures(anon_client: AsyncClient) -> None:
    await anon_client.post(
        "/auth/register", json={"email": "c@exemple.cm", "password": "motdepasse"}
    )
    wrong = {"email": "C@exemple.cm", "password": "mauvais"}
    for _ in range(MAX_FAILURES):
        assert (await anon_client.post("/auth/login", json=wrong)).status_code == 401
    # Even the right password is refused while the e-mail is throttled
    right = {"email": "c@exemple.cm", "password": "motdepasse"}
    assert (await anon_client.post("/auth/login", json=right)).status_code == 429
    # Other accounts are not affected
    other = {"email": "autre@exemple.cm", "password": "x"}
    assert (await anon_client.post("/auth/login", json=other)).status_code == 401


async def test_success_resets_failed_login_count(anon_client: AsyncClient) -> None:
    await anon_client.post(
        "/auth/register", json={"email": "c@exemple.cm", "password": "motdepasse"}
    )
    wrong = {"email": "c@exemple.cm", "password": "mauvais"}
    right = {"email": "c@exemple.cm", "password": "motdepasse"}
    for _ in range(MAX_FAILURES - 1):
        await anon_client.post("/auth/login", json=wrong)
    assert (await anon_client.post("/auth/login", json=right)).status_code == 200
    for _ in range(MAX_FAILURES - 1):
        await anon_client.post("/auth/login", json=wrong)
    assert (await anon_client.post("/auth/login", json=right)).status_code == 200


async def test_catalogue_is_gzipped(anon_client: AsyncClient, client: AsyncClient) -> None:
    for i in range(30):
        await client.post("/products/", json={**PRODUCT, "name": f"Cahier {i}"})
    response = await anon_client.get("/products/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert len(response.json()) == 30


async def test_registrations_are_limited_site_wide(anon_client: AsyncClient) -> None:
    for i in range(MAX_REGISTRATIONS):
        new = {"email": f"client{i}@exemple.cm", "password": "motdepasse"}
        assert (await anon_client.post("/auth/register", json=new)).status_code == 201
    # Once the limit is reached, every new sign-up waits (the limit is site-wide)
    extra = {"email": "encore@exemple.cm", "password": "motdepasse"}
    assert (await anon_client.post("/auth/register", json=extra)).status_code == 429
    # Logging in is not affected
    login = {"email": "client0@exemple.cm", "password": "motdepasse"}
    assert (await anon_client.post("/auth/login", json=login)).status_code == 200


async def test_admin_sees_last_login(client: AsyncClient, anon_client: AsyncClient) -> None:
    async with async_session_maker() as session:
        await AuthService(session).register("k@exemple.cm", "motdepasse")
    users = {u["email"]: u for u in (await client.get("/users/")).json()}
    assert users["k@exemple.cm"]["last_login_at"] is None

    admin_auth = client.headers.pop("Authorization")
    before = datetime.now(UTC)
    wrong = await anon_client.post(
        "/auth/login", json={"email": "k@exemple.cm", "password": "mauvais-mdp"}
    )
    assert wrong.status_code == 401
    login = await anon_client.post(
        "/auth/login", json={"email": "k@exemple.cm", "password": "motdepasse"}
    )
    assert "last_login_at" not in login.json()["user"]  # only administrators see it
    anon_client.headers["Authorization"] = admin_auth

    users = {u["email"]: u for u in (await client.get("/users/")).json()}
    seen = datetime.fromisoformat(users["k@exemple.cm"]["last_login_at"])
    assert seen.tzinfo is not None
    assert before - timedelta(seconds=1) <= seen <= datetime.now(UTC) + timedelta(seconds=1)
    assert users[ADMIN_EMAIL]["last_login_at"] is not None


async def test_admin_notes_on_accounts(client: AsyncClient, anon_client: AsyncClient) -> None:
    from tests.conftest import make_user

    token = await make_user("n@exemple.cm", "motdepasse")
    users = {u["email"]: u for u in (await client.get("/users/")).json()}
    user_id = users["n@exemple.cm"]["id"]
    assert users["n@exemple.cm"]["admin_notes"] is None

    response = await client.patch(
        f"/users/{user_id}/admin-notes", json={"admin_notes": "  Client de l'école Bastos  "}
    )
    assert response.status_code == 200
    assert response.json()["admin_notes"] == "Client de l'école Bastos"
    users = {u["email"]: u for u in (await client.get("/users/")).json()}
    assert users["n@exemple.cm"]["admin_notes"] == "Client de l'école Bastos"

    # The account's owner never sees them, and cannot write them
    admin_auth = client.headers.pop("Authorization")
    me = await anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert "admin_notes" not in me.json()
    denied = await anon_client.patch(
        f"/users/{user_id}/admin-notes",
        json={"admin_notes": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403
    anon_client.headers["Authorization"] = admin_auth

    # Empty clears them; too long is refused; unknown account is 404
    cleared = await client.patch(f"/users/{user_id}/admin-notes", json={"admin_notes": " "})
    assert cleared.json()["admin_notes"] is None
    too_long = await client.patch(f"/users/{user_id}/admin-notes", json={"admin_notes": "x" * 2001})
    assert too_long.status_code == 422
    assert (
        await client.patch("/users/9999/admin-notes", json={"admin_notes": "x"})
    ).status_code == 404
