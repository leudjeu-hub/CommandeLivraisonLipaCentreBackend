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
