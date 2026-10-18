from httpx import AsyncClient


async def test_create_and_get_product(client: AsyncClient) -> None:
    response = await client.post("/products/", json={"name": "Stylo", "price": 500, "stock": 10})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Stylo"
    assert body["price"] == 500
    assert body["stock"] == 10
    product_id = body["id"]

    response = await client.get(f"/products/{product_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Stylo"


async def test_list_products_sorted(client: AsyncClient) -> None:
    await client.post("/products/", json={"name": "Cahier", "price": 1200, "stock": 5})
    await client.post("/products/", json={"name": "Stylo", "price": 500, "stock": 10})
    response = await client.get("/products/")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Cahier", "Stylo"]


async def test_update_product(client: AsyncClient) -> None:
    created = (await client.post("/products/", json={"name": "Stylo", "price": 500})).json()
    response = await client.put(f"/products/{created['id']}", json={"price": 700})
    assert response.status_code == 200
    assert response.json()["price"] == 700
    assert response.json()["name"] == "Stylo"


async def test_delete_product(client: AsyncClient) -> None:
    created = (await client.post("/products/", json={"name": "Stylo", "price": 500})).json()
    response = await client.delete(f"/products/{created['id']}")
    assert response.status_code == 204
    assert (await client.get(f"/products/{created['id']}")).status_code == 404


async def test_get_missing_product(client: AsyncClient) -> None:
    response = await client.get("/products/999")
    assert response.status_code == 404


async def test_create_product_validation(client: AsyncClient) -> None:
    response = await client.post("/products/", json={"name": "", "price": -1})
    assert response.status_code == 422
