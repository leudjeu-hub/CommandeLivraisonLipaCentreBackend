from httpx import AsyncClient


async def _create_product(client: AsyncClient, name: str, price: float, stock: int) -> int:
    response = await client.post(
        "/products/", json={"category": "Scolaire", "name": name, "price": price, "stock": stock}
    )
    return response.json()["id"]


async def test_create_order_decrements_stock(client: AsyncClient) -> None:
    pen = await _create_product(client, "Stylo", 500, 10)
    notebook = await _create_product(client, "Cahier", 1200, 5)
    response = await client.post(
        "/orders/",
        json={
            "customer_name": "Jean",
            "phone": "237600000000",
            "items": [
                {"product_id": pen, "quantity": 2},
                {"product_id": notebook, "quantity": 1},
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["total"] == 2200
    assert body["status"] == "new"
    assert "whatsapp_url" in body
    assert len(body["items"]) == 2

    products = (await client.get("/products/")).json()
    stock = {p["name"]: p["stock"] for p in products}
    assert stock["Stylo"] == 8
    assert stock["Cahier"] == 4


async def test_order_insufficient_stock(client: AsyncClient) -> None:
    pen = await _create_product(client, "Stylo", 500, 1)
    response = await client.post(
        "/orders/",
        json={
            "customer_name": "Jean",
            "phone": "237600000000",
            "items": [{"product_id": pen, "quantity": 5}],
        },
    )
    assert response.status_code == 400
    assert "stock" in response.json()["detail"].lower()


async def test_order_missing_product(client: AsyncClient) -> None:
    response = await client.post(
        "/orders/",
        json={
            "customer_name": "Jean",
            "phone": "237600000000",
            "items": [{"product_id": 999, "quantity": 1}],
        },
    )
    assert response.status_code == 404


async def test_update_order_status(client: AsyncClient) -> None:
    pen = await _create_product(client, "Stylo", 500, 10)
    order_id = (
        await client.post(
            "/orders/",
            json={
                "customer_name": "Jean",
                "phone": "237600000000",
                "items": [{"product_id": pen, "quantity": 1}],
            },
        )
    ).json()["id"]
    response = await client.patch(f"/orders/{order_id}/status", json={"status": "confirmed"})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


async def test_invalid_order_status(client: AsyncClient) -> None:
    pen = await _create_product(client, "Stylo", 500, 10)
    order_id = (
        await client.post(
            "/orders/",
            json={
                "customer_name": "Jean",
                "phone": "237600000000",
                "items": [{"product_id": pen, "quantity": 1}],
            },
        )
    ).json()["id"]
    response = await client.patch(f"/orders/{order_id}/status", json={"status": "shipped"})
    assert response.status_code == 422


async def test_list_orders(client: AsyncClient) -> None:
    pen = await _create_product(client, "Stylo", 500, 10)
    await client.post(
        "/orders/",
        json={
            "customer_name": "Jean",
            "phone": "237600000000",
            "items": [{"product_id": pen, "quantity": 1}],
        },
    )
    response = await client.get("/orders/")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_order_price_on_request_product(client: AsyncClient) -> None:
    book = (
        await client.post(
            "/products/", json={"category": "Livres", "name": "Livre sur demande", "stock": 5}
        )
    ).json()["id"]
    response = await client.post(
        "/orders/",
        json={
            "customer_name": "Jean",
            "phone": "237600000000",
            "items": [{"product_id": book, "quantity": 1}],
        },
    )
    assert response.status_code == 400
    assert "on request" in response.json()["detail"]


SUBMIT = {
    "customer_name": "Awa",
    "phone": "+237 690 00 00 00",
    "area": "Bastos",
    "address": "Près de l'ambassade",
    "slot": "Matin",
    "payment": "Orange Money",
    "notes": "Sonner deux fois",
    "delivery_fee": 1000,
}


async def test_submit_order_is_public_and_keeps_stock(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    pen = await _create_product(client, "Stylo", 500, 10)
    token = client.headers.pop("Authorization")
    response = await anon_client.post(
        "/orders/submit",
        # A price sent by the client is ignored: the catalogue's price is used
        json={**SUBMIT, "items": [{"product_id": pen, "quantity": 3, "unit_price": 1}]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "new"
    assert body["kind"] == "order"
    assert body["total"] == 1500
    assert body["delivery_fee"] == 1000
    assert body["area"] == "Bastos"
    assert body["notes"] == "Sonner deux fois"
    assert body["created_at"].endswith(("Z", "+00:00"))

    client.headers["Authorization"] = token
    stock = {p["name"]: p["stock"] for p in (await client.get("/products/")).json()}
    assert stock["Stylo"] == 10
    orders = (await client.get("/orders/")).json()
    assert [o["id"] for o in orders] == [body["id"]]


async def test_submit_quote_without_items(anon_client: AsyncClient) -> None:
    response = await anon_client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})
    assert response.status_code == 201
    assert response.json()["kind"] == "quote"
    assert response.json()["items"] == []


async def test_submit_order_needs_items(anon_client: AsyncClient) -> None:
    response = await anon_client.post("/orders/submit", json=SUBMIT)
    assert response.status_code == 422


async def test_submit_price_on_request_counts_zero(client: AsyncClient) -> None:
    book = (
        await client.post("/products/", json={"category": "Livres", "name": "Livre", "stock": 0})
    ).json()["id"]
    response = await client.post(
        "/orders/submit", json={**SUBMIT, "items": [{"product_id": book, "quantity": 1}]}
    )
    assert response.status_code == 201
    assert response.json()["total"] == 0


async def test_submit_order_is_throttled(anon_client: AsyncClient) -> None:
    from app.core.rate_limit import ALL, MAX_ORDERS, order_throttle

    for _ in range(MAX_ORDERS):
        order_throttle.record_failure(ALL)
    response = await anon_client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})
    assert response.status_code == 429


async def test_list_orders_by_status(client: AsyncClient) -> None:
    first = (await client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})).json()["id"]
    await client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})
    await client.patch(f"/orders/{first}/status", json={"status": "delivered"})
    delivered = (await client.get("/orders/", params={"status": "delivered"})).json()
    assert [o["id"] for o in delivered] == [first]
    assert len((await client.get("/orders/", params={"status": "new"})).json()) == 1


async def test_orders_list_is_admin_only(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/orders/")).status_code == 401


async def test_order_enums_stored_as_values(anon_client: AsyncClient) -> None:
    """The migrations' CHECK constraints accept 'new', 'order'…: enum names ('NEW') would fail."""
    from sqlalchemy import text

    from app.core.db import async_session_maker

    await anon_client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})
    async with async_session_maker() as session:
        row = (await session.execute(text("SELECT status, kind FROM orders"))).one()
    assert tuple(row) == ("new", "quote")


async def test_cancelled_orders_deleted_after_30_days(client: AsyncClient) -> None:
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.db import async_session_maker
    from app.models.order import Order
    from app.services.order_service import utcnow

    pen = await _create_product(client, "Stylo", 500, 10)
    item = {"items": [{"product_id": pen, "quantity": 1}]}
    old, recent, delivered = [
        (await client.post("/orders/submit", json={**SUBMIT, **item})).json()["id"]
        for _ in range(3)
    ]
    for order_id, status in ((old, "cancelled"), (recent, "cancelled"), (delivered, "delivered")):
        body = (await client.patch(f"/orders/{order_id}/status", json={"status": status})).json()
        assert body["status_changed_at"] is not None
    long_ago = utcnow() - timedelta(days=31)
    async with async_session_maker() as session:
        await session.execute(
            update(Order)
            .where(Order.id.in_([old, delivered]))
            .values(status_changed_at=long_ago, created_at=long_ago)
        )
        await session.commit()

    ids = [o["id"] for o in (await client.get("/orders/")).json()]
    assert sorted(ids) == sorted([recent, delivered])
    assert (await client.get(f"/orders/{old}")).status_code == 404
    # The product stays: only the order and its lines are deleted
    assert any(p["id"] == pen for p in (await client.get("/products/")).json())


async def test_delivered_orders_deleted_after_12_months(client: AsyncClient) -> None:
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.db import async_session_maker
    from app.models.order import Order
    from app.services.order_service import utcnow

    pen = await _create_product(client, "Stylo", 500, 10)
    item = {"items": [{"product_id": pen, "quantity": 1}]}
    old, recent, pending = [
        (await client.post("/orders/submit", json={**SUBMIT, **item})).json()["id"]
        for _ in range(3)
    ]
    for order_id in (old, recent):
        await client.patch(f"/orders/{order_id}/status", json={"status": "delivered"})
    async with async_session_maker() as session:
        # Delivered 366 days ago: deleted; delivered 364 days ago: kept
        for order_id, days in ((old, 366), (recent, 364)):
            when = utcnow() - timedelta(days=days)
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status_changed_at=when, created_at=when)
            )
        # Still "new" after more than a year: only cancelled and delivered orders expire
        await session.execute(
            update(Order)
            .where(Order.id == pending)
            .values(created_at=utcnow() - timedelta(days=400))
        )
        await session.commit()

    ids = [o["id"] for o in (await client.get("/orders/")).json()]
    assert sorted(ids) == sorted([recent, pending])
    assert (await client.get(f"/orders/{old}")).status_code == 404


async def test_managers_manage_orders_but_others_do_not(anon_client: AsyncClient) -> None:
    from app.models.user import UserRole
    from tests.conftest import make_user

    order_id = (await anon_client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})).json()[
        "id"
    ]
    manager = await make_user("resp@exemple.cm", "motdepasse", UserRole.MANAGER)
    headers = {"Authorization": f"Bearer {manager}"}
    assert (await anon_client.get("/orders/", headers=headers)).status_code == 200
    assert (await anon_client.get(f"/orders/{order_id}", headers=headers)).status_code == 200
    response = await anon_client.patch(
        f"/orders/{order_id}/status", json={"status": "confirmed"}, headers=headers
    )
    assert response.json()["status"] == "confirmed"
    # Entering an order by hand takes stock: administrators only
    created = await anon_client.post(
        "/orders/",
        json={"customer_name": "A", "phone": "1", "items": [{"product_id": 1, "quantity": 1}]},
        headers=headers,
    )
    assert created.status_code == 403
    for role in (UserRole.EMPLOYEE, UserRole.USER):
        token = await make_user(f"{role.value}@exemple.cm", "motdepasse", role)
        response = await anon_client.get("/orders/", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


async def test_customer_sees_only_own_orders(anon_client: AsyncClient) -> None:
    from tests.conftest import make_user

    alice = {"Authorization": f"Bearer {await make_user('alice@exemple.cm', 'motdepasse')}"}
    bob = {"Authorization": f"Bearer {await make_user('bob@exemple.cm', 'motdepasse')}"}
    quote = {**SUBMIT, "kind": "quote"}
    first = (await anon_client.post("/orders/submit", json=quote, headers=alice)).json()["id"]
    second = (await anon_client.post("/orders/submit", json=quote, headers=alice)).json()["id"]
    bobs = (await anon_client.post("/orders/submit", json=quote, headers=bob)).json()["id"]
    # A guest's order (same name and phone as Alice's) is linked to no one
    await anon_client.post("/orders/submit", json=quote)

    response = await anon_client.get("/orders/mine", headers=alice)
    assert response.status_code == 200
    assert [o["id"] for o in response.json()] == [second, first]
    assert [o["id"] for o in (await anon_client.get("/orders/mine", headers=bob)).json()] == [bobs]
    # A customer still cannot read the shop's list or someone else's order
    assert (await anon_client.get("/orders/", headers=alice)).status_code == 403
    assert (await anon_client.get(f"/orders/{bobs}", headers=alice)).status_code == 403


async def test_my_orders_needs_login(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/orders/mine")).status_code == 401


async def test_submit_with_invalid_token_still_records(anon_client: AsyncClient) -> None:
    response = await anon_client.post(
        "/orders/submit",
        json={**SUBMIT, "kind": "quote"},
        headers={"Authorization": "Bearer jeton-expire"},
    )
    assert response.status_code == 201


async def test_deleting_account_keeps_its_orders(client: AsyncClient) -> None:
    from tests.conftest import make_user

    token = await make_user("client@exemple.cm", "motdepasse")
    order_id = (
        await client.post(
            "/orders/submit",
            json={**SUBMIT, "kind": "quote"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()["id"]
    users = (await client.get("/users/")).json()
    user_id = next(u["id"] for u in users if u["email"] == "client@exemple.cm")
    assert (await client.delete(f"/users/{user_id}")).status_code == 204
    assert (await client.get(f"/orders/{order_id}")).status_code == 200


async def test_guest_order_claimed_after_login(anon_client: AsyncClient) -> None:
    from tests.conftest import make_user

    quote = {**SUBMIT, "kind": "quote"}
    guest = (await anon_client.post("/orders/submit", json=quote)).json()
    assert guest["claim_code"]
    other = (await anon_client.post("/orders/submit", json=quote)).json()
    awa = {"Authorization": f"Bearer {await make_user('awa@exemple.cm', 'motdepasse')}"}
    # Sent while logged in: already linked, no code
    linked = (await anon_client.post("/orders/submit", json=quote, headers=awa)).json()
    assert linked["claim_code"] is None

    claim = await anon_client.post(
        "/orders/claim", json={"codes": [guest["claim_code"], "code-invente"]}, headers=awa
    )
    assert claim.json() == {"claimed": 1}
    mine = [o["id"] for o in (await anon_client.get("/orders/mine", headers=awa)).json()]
    assert mine == [linked["id"], guest["id"]]
    assert other["id"] not in mine
    # A code works once: another account cannot take the order afterwards
    bob = {"Authorization": f"Bearer {await make_user('bob@exemple.cm', 'motdepasse')}"}
    claim = await anon_client.post(
        "/orders/claim", json={"codes": [guest["claim_code"]]}, headers=bob
    )
    assert claim.json() == {"claimed": 0}


async def test_claim_needs_login_and_code_never_listed(client: AsyncClient) -> None:
    client_token = client.headers.pop("Authorization")
    code = (await client.post("/orders/submit", json={**SUBMIT, "kind": "quote"})).json()[
        "claim_code"
    ]
    assert (await client.post("/orders/claim", json={"codes": [code]})).status_code == 401
    client.headers["Authorization"] = client_token
    for order in (await client.get("/orders/")).json():
        assert order["claim_code"] is None
