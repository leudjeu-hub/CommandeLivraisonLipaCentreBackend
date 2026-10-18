# ruff: noqa: RUF001  (typographic apostrophes are copied verbatim from catalogue.csv)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductCategory

# Initial rows of CommandeLivraisonLipaCentre/catalogue/catalogue.csv. Later catalogue changes
# go through `python -m app.scripts.import_catalogue`.
CATALOGUE: list[dict[str, object]] = [
    {
        "id": 1,
        "category": ProductCategory.SCOLAIRE,
        "price": 1500,
        "name": "Cahier A4 · 200 pages",
        "description": "Quadrillé, pour les cours et les exercices.",
        "label": "CAHIER / 200 PAGES",
        "name_en": "A4 notebook · 200 pages",
        "description_en": "Squared paper, for lessons and exercises.",
        "label_en": "NOTEBOOK / 200 PAGES",
        "color": "#31574b",
        "status": None,
        "image": "img/produits/cahier-a4-200.webp",
    },
    {
        "id": 2,
        "category": ProductCategory.SCOLAIRE,
        "price": 1000,
        "name": "Lot de 10 stylos bleus",
        "description": "L’essentiel pour écrire au quotidien.",
        "label": "STYLOS / BLEUS",
        "name_en": "Pack of 10 blue pens",
        "description_en": "The essentials for everyday writing.",
        "label_en": "BLUE / PENS",
        "color": "#627e9c",
        "status": None,
        "image": "img/produits/lot-de-10.webp",
    },
    {
        "id": 3,
        "category": ProductCategory.SCOLAIRE,
        "price": 2500,
        "name": "Kit de géométrie",
        "description": "Règle, équerre, rapporteur et compas.",
        "label": "GÉOMÉTRIE",
        "name_en": "Geometry set",
        "description_en": "Ruler, set square, protractor and compass.",
        "label_en": "GEOMETRY",
        "color": "#a76b4c",
        "status": None,
        "image": "img/produits/kit-de-geometrie.webp",
    },
    {
        "id": 4,
        "category": ProductCategory.BUREAU,
        "price": 4000,
        "name": "Ramette de papier A4",
        "description": "500 feuilles · grammage à confirmer.",
        "label": "PAPIER A4 / 500 FEUILLES",
        "name_en": "Ream of A4 paper",
        "description_en": "500 sheets · paper weight to be confirmed.",
        "label_en": "A4 PAPER / 500 SHEETS",
        "color": "#c6a157",
        "status": None,
        "image": "img/produits/ramette-de-papier.webp",
    },
    {
        "id": 5,
        "category": ProductCategory.BUREAU,
        "price": 2500,
        "name": "Classeur à levier",
        "description": "Pour organiser et conserver vos documents.",
        "label": "ARCHIVES",
        "name_en": "Lever arch file",
        "description_en": "To organise and store your documents.",
        "label_en": "ARCHIVES",
        "color": "#53634e",
        "status": None,
        "image": "img/produits/classeur-a-levier.webp",
    },
    {
        "id": 6,
        "category": ProductCategory.BUREAU,
        "price": 750,
        "name": "Notes adhésives",
        "description": "Un bloc pour vos rappels et vos idées.",
        "label": "MES NOTES",
        "name_en": "Sticky notes",
        "description_en": "A pad for your reminders and ideas.",
        "label_en": "MY NOTES",
        "color": "#d3ae5d",
        "status": None,
        "image": "img/produits/notes-adhesives.webp",
    },
    {
        "id": 7,
        "category": ProductCategory.LIVRES,
        "price": 8500,
        "name": "Dictionnaire de français",
        "description": "Référence illustrative · édition à confirmer.",
        "label": "DICTIONNAIRE / FRANÇAIS",
        "name_en": "French dictionary",
        "description_en": "Illustrative reference · edition to be confirmed.",
        "label_en": "FRENCH / DICTIONARY",
        "color": "#a95540",
        "status": None,
        "image": "img/produits/dictionnaire-de-francais.webp",
    },
    {
        "id": 8,
        "category": ProductCategory.LIVRES,
        "price": None,
        "name": "Livre scolaire sur demande",
        "description": "Précisez le titre, la classe et l’édition.",
        "label": "APPRENDRE",
        "name_en": "School book on request",
        "description_en": "Specify the title, class and edition.",
        "label_en": "LEARN",
        "color": "#486473",
        "status": "disponible",
        "image": "img/produits/livre-scolaire-sur.webp",
    },
]


async def seed_products_if_empty(session: AsyncSession) -> int:
    """Insert the catalogue products when the products table is empty; return the count."""
    if (await session.execute(select(func.count()).select_from(Product))).scalar_one():
        return 0
    session.add_all(Product(**row) for row in CATALOGUE)
    await session.commit()
    if session.get_bind().dialect.name == "postgresql":
        # Explicit ids bypass the serial sequence; move it past them.
        await session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('products', 'id'), "
                "(SELECT MAX(id) FROM products))"
            )
        )
        await session.commit()
    return len(CATALOGUE)
