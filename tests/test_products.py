from httpx import AsyncClient

from app.core.db import async_session_maker
from app.services.catalogue_seed import seed_products_if_empty


async def test_create_and_get_product(client: AsyncClient) -> None:
    response = await client.post(
        "/products/", json={"category": "Scolaire", "name": "Stylo", "price": 500, "stock": 10}
    )
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
    await client.post(
        "/products/", json={"category": "Scolaire", "name": "Cahier", "price": 1200, "stock": 5}
    )
    await client.post(
        "/products/", json={"category": "Scolaire", "name": "Stylo", "price": 500, "stock": 10}
    )
    response = await client.get("/products/")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Cahier", "Stylo"]


async def test_update_product(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/products/", json={"category": "Scolaire", "name": "Stylo", "price": 500}
        )
    ).json()
    response = await client.put(f"/products/{created['id']}", json={"price": 700})
    assert response.status_code == 200
    assert response.json()["price"] == 700
    assert response.json()["name"] == "Stylo"


async def test_delete_product(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/products/", json={"category": "Scolaire", "name": "Stylo", "price": 500}
        )
    ).json()
    response = await client.delete(f"/products/{created['id']}")
    assert response.status_code == 204
    assert (await client.get(f"/products/{created['id']}")).status_code == 404


async def test_get_missing_product(client: AsyncClient) -> None:
    response = await client.get("/products/999")
    assert response.status_code == 404


async def test_create_product_validation(client: AsyncClient) -> None:
    response = await client.post(
        "/products/", json={"category": "Scolaire", "name": "", "price": -1}
    )
    assert response.status_code == 422


async def test_create_product_with_catalogue_fields(client: AsyncClient) -> None:
    payload = {
        "category": "Livres",
        "name": "Livre scolaire sur demande",
        "description": "Précisez le titre, la classe et l'édition.",
        "label": "APPRENDRE",
        "name_en": "School book on request",
        "color": "#486473",
        "status": "disponible",
        "image": "img/produits/livre-scolaire-sur.webp",
    }
    response = await client.post("/products/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["price"] is None
    assert body["available"] is True
    assert body["category"] == "Livres"
    assert body["color"] == "#486473"


async def test_create_product_invalid_category_and_color(client: AsyncClient) -> None:
    response = await client.post("/products/", json={"category": "Jouets", "name": "Balle"})
    assert response.status_code == 422
    response = await client.post(
        "/products/", json={"category": "Bureau", "name": "Agrafeuse", "color": "red"}
    )
    assert response.status_code == 422


async def test_seed_products_if_empty(client: AsyncClient) -> None:
    async with async_session_maker() as session:
        assert await seed_products_if_empty(session) == 8
        assert await seed_products_if_empty(session) == 0
    products = (await client.get("/products/")).json()
    assert sorted(p["id"] for p in products) == list(range(1, 9))
    book = next(p for p in products if p["id"] == 8)
    assert book["price"] is None
    assert book["category"] == "Livres"


async def test_seed_skips_non_empty_table(client: AsyncClient) -> None:
    await client.post("/products/", json={"category": "Bureau", "name": "Agrafeuse", "price": 900})
    async with async_session_maker() as session:
        assert await seed_products_if_empty(session) == 0
    assert len((await client.get("/products/")).json()) == 1
