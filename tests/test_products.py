from httpx import AsyncClient

from app.core.db import async_session_maker
from app.services.catalogue_seed import seed_products_if_empty
from tests.conftest import make_user


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


async def test_update_product_to_price_on_request(client: AsyncClient) -> None:
    created = (
        await client.post("/products/", json={"category": "Livres", "name": "Livre", "price": 900})
    ).json()
    response = await client.put(
        f"/products/{created['id']}", json={"price": None, "available": False}
    )
    assert response.status_code == 200
    assert response.json()["price"] is None
    assert response.json()["available"] is False


async def test_delete_product_used_in_order(client: AsyncClient) -> None:
    pen = (
        await client.post(
            "/products/", json={"category": "Scolaire", "name": "Stylo", "price": 500, "stock": 5}
        )
    ).json()["id"]
    await client.post(
        "/orders/",
        json={
            "customer_name": "Jean",
            "phone": "237600000000",
            "items": [{"product_id": pen, "quantity": 1}],
        },
    )
    response = await client.delete(f"/products/{pen}")
    assert response.status_code == 409
    assert (await client.get(f"/products/{pen}")).status_code == 200


async def test_admin_page(client: AsyncClient) -> None:
    response = await client.get("/admin")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Gestion des produits" in response.text


async def test_list_products_is_cacheable(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/products/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=60, stale-while-revalidate=600"


async def test_preflight_is_cached_for_a_day(anon_client: AsyncClient) -> None:
    response = await anon_client.options(
        "/products/",
        headers={
            "Origin": "https://leudjeu-hub.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-max-age"] == "86400"


async def test_managers_edit_products(anon_client: AsyncClient) -> None:
    manager = {"Authorization": f"Bearer {await make_user('m@test.cm', 'password-123', 'manager')}"}
    created = await anon_client.post(
        "/products/", json={"category": "Scolaire", "name": "Stylo", "price": 500}, headers=manager
    )
    assert created.status_code == 201
    product_id = created.json()["id"]
    response = await anon_client.put(
        f"/products/{product_id}", json={"price": 600}, headers=manager
    )
    assert response.status_code == 200
    assert response.json()["price"] == 600

    employee = {
        "Authorization": f"Bearer {await make_user('e@test.cm', 'password-123', 'employee')}"
    }
    for request in (
        anon_client.post(
            "/products/", json={"category": "Scolaire", "name": "X"}, headers=employee
        ),
        anon_client.put(f"/products/{product_id}", json={"price": 1}, headers=employee),
        anon_client.delete(f"/products/{product_id}", headers=employee),
    ):
        assert (await request).status_code == 403

    response = await anon_client.delete(f"/products/{product_id}", headers=manager)
    assert response.status_code == 204
