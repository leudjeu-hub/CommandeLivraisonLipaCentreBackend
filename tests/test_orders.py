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
