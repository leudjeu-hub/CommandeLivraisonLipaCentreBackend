from httpx import AsyncClient

from tests.conftest import make_user

HEADER = "id;categorie;prix;nom;description;nom_en;description_en;disponible;stock\n"


async def add(client: AsyncClient, name: str, price: int | None = 500) -> int:
    response = await client.post(
        "/products/", json={"category": "Scolaire", "name": name, "price": price, "stock": 3}
    )
    return response.json()["id"]


async def upload(client: AsyncClient, content: str, dry_run: bool = False) -> dict:
    response = await client.post("/products/import", json={"content": content, "dry_run": dry_run})
    assert response.status_code == 200, response.text
    return response.json()


async def test_import_creates_and_updates(client: AsyncClient) -> None:
    pen = await add(client, "Stylo")
    await add(client, "Cahier")
    csv = (
        "\ufeff" + HEADER + f"{pen};Scolaire;1\u202f500;Stylo bleu;;;;oui;10\n"
        ";bureau;;Classeur;Sur devis.;Binder;On request.;non;\n"
        ";Scolaire;1200;cahier;;;;;5\n"
    )
    report = await upload(client, csv)
    assert report == {
        "applied": True,
        "created": 1,
        "updated": 2,
        "unchanged": 0,
        "errors": [],
    }
    products = {p["name"]: p for p in (await client.get("/products/")).json()}
    assert products["Stylo bleu"]["price"] == 1500
    assert products["Stylo bleu"]["stock"] == 10
    binder = products["Classeur"]
    assert binder["category"] == "Bureau"
    assert binder["price"] is None
    assert binder["available"] is False
    assert binder["name_en"] == "Binder"
    # Matched by name, ignoring case; the name is rewritten as in the file.
    assert products["cahier"]["stock"] == 5
    assert "Cahier" not in products


async def test_only_present_columns_are_updated(client: AsyncClient) -> None:
    pen = await add(client, "Stylo")
    report = await upload(client, f"id,prix\n{pen},700\n")
    assert report["updated"] == 1
    product = (await client.get(f"/products/{pen}")).json()
    assert product["price"] == 700
    assert product["name"] == "Stylo"
    assert product["stock"] == 3


async def test_dry_run_writes_nothing(client: AsyncClient) -> None:
    pen = await add(client, "Stylo")
    report = await upload(client, f"id;prix\n{pen};500\n;\n", dry_run=True)
    assert report["applied"] is False
    assert report["unchanged"] == 1
    report = await upload(client, "categorie;nom\nLivres;Roman\n", dry_run=True)
    assert report["created"] == 1
    assert len((await client.get("/products/")).json()) == 1


async def test_errors_are_reported_per_line_and_nothing_is_written(client: AsyncClient) -> None:
    pen = await add(client, "Stylo")
    csv = (
        HEADER + f"{pen};Scolaire;abc;Stylo;;;;;\n"  # line 2
        ";Jouets;100;Ballon;;;;;\n"  # line 3
        "99;Scolaire;100;Fantôme;;;;;\n"  # line 4
        ";Livres;;Roman;;Novel;;;\n"  # line 5: English name without description
        ";Livres;;;;;;;\n"  # line 6: no name
        ";Bureau;100;Agrafeuse;;;;peut-être;\n"  # line 7
        ";Bureau;100;Gomme;;;;;-2\n"  # line 8
        ";Bureau;100;Gomme;;;;;\n"  # line 9: same new article twice
        ";Bureau;100;Règle;;;;;\n"  # line 10: valid
    )
    report = await upload(client, csv)
    assert report["applied"] is False
    assert [(e["line"], e["code"], e["column"]) for e in report["errors"]] == [
        (2, "invalid_price", "prix"),
        (3, "invalid_category", "categorie"),
        (4, "unknown_id", "id"),
        (5, "english_pair", "nom_en"),
        (6, "required", "nom"),
        (7, "invalid_available", "disponible"),
        (8, "invalid_stock", "stock"),
    ]
    names = [p["name"] for p in (await client.get("/products/")).json()]
    assert names == ["Stylo"]
    report = await upload(client, "categorie;nom\nBureau;Gomme\nBureau;gomme\n")
    assert [(e["line"], e["code"], e["value"]) for e in report["errors"]] == [
        (3, "duplicate_row", "2")
    ]


async def test_header_problems(client: AsyncClient) -> None:
    report = await upload(client, "nom;pris\nStylo;100\n")
    assert [(e["code"], e["value"]) for e in report["errors"]] == [("unknown_column", "pris")]
    report = await upload(client, "prix;stock\n100;1\n")
    assert [e["code"] for e in report["errors"]] == ["missing_key_column"]
    report = await upload(client, "  \n")
    assert [e["code"] for e in report["errors"]] == ["empty"]


async def test_new_article_needs_a_category(client: AsyncClient) -> None:
    report = await upload(client, "nom;prix\nStylo;100\n")
    assert [(e["line"], e["code"], e["column"]) for e in report["errors"]] == [
        (2, "required", "categorie")
    ]


async def test_quoted_cells_and_line_numbers(client: AsyncClient) -> None:
    csv = 'categorie;nom;description\nLivres;Roman;"Ligne 1\nligne 2; avec point-virgule"\nX;Y;\n'
    report = await upload(client, csv)
    assert [(e["line"], e["code"]) for e in report["errors"]] == [(4, "invalid_category")]


async def test_import_is_admin_only(anon_client: AsyncClient) -> None:
    body = {"content": "categorie;nom\nLivres;Roman\n", "dry_run": False}
    assert (await anon_client.post("/products/import", json=body)).status_code == 401
    for role in ("user", "employee", "manager"):
        token = await make_user(f"{role}@test.cm", "password-123", role)
        response = await anon_client.post(
            "/products/import", json=body, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403


async def test_family_column(client: AsyncClient) -> None:
    pen = await add(client, "Stylo")
    report = await upload(client, f"id;famille\n{pen};Stylos et crayons\n")
    assert report["updated"] == 1
    assert (await client.get(f"/products/{pen}")).json()["family"] == "Stylos et crayons"
    await upload(client, f"id;famille\n{pen};\n")
    assert (await client.get(f"/products/{pen}")).json()["family"] is None
    report = await upload(client, "categorie;nom;famille\nLivres;Bled CE2;" + "x" * 61 + "\n")
    assert [(e["code"], e["column"]) for e in report["errors"]] == [("too_long", "famille")]
