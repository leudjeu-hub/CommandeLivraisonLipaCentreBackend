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
