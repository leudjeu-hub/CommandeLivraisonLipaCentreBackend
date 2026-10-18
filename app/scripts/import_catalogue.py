"""Import (upsert by id) the products of the frontend's catalogue.csv.

Usage: uv run python -m app.scripts.import_catalogue path/to/catalogue.csv
"""

import asyncio
import csv
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text

from app.core.db import async_session_maker, engine
from app.models.product import Product
from app.schemas.product import ProductCreate


def _optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def parse_row(row: dict[str, str]) -> tuple[int, ProductCreate]:
    price = _optional(row.get("prix"))
    data: dict[str, Any] = {
        "category": row["categorie"].strip(),
        "price": float("".join(price.split())) if price else None,
        "name": row["nom"].strip(),
        "description": (row.get("description") or "").strip(),
        "label": _optional(row.get("vignette")),
        "name_en": _optional(row.get("nom_en")),
        "description_en": _optional(row.get("description_en")),
        "label_en": _optional(row.get("vignette_en")),
        "color": _optional(row.get("couleur")),
        "available": (row.get("disponible") or "").strip().lower() != "non",
        "status": _optional(row.get("statut")),
        "image": _optional(row.get("image")),
    }
    return int(row["id"]), ProductCreate.model_validate(data)


def read_catalogue(path: Path) -> list[tuple[int, ProductCreate]]:
    content = path.read_text(encoding="utf-8-sig")
    delimiter = (
        ";" if content.splitlines()[0].count(";") >= content.splitlines()[0].count(",") else ","
    )
    rows = csv.DictReader(content.splitlines(), delimiter=delimiter)
    return [parse_row(row) for row in rows if any((v or "").strip() for v in row.values())]


async def import_catalogue(path: Path) -> int:
    products = read_catalogue(path)
    async with async_session_maker() as session:
        for product_id, data in products:
            product = await session.get(Product, product_id)
            # stock is managed by the backend, not by the catalogue.
            values = data.model_dump(exclude={"stock"})
            if product is None:
                session.add(Product(id=product_id, **values))
            else:
                for field, value in values.items():
                    setattr(product, field, value)
        await session.commit()
        if engine.dialect.name == "postgresql":
            max_id = (await session.execute(select(func.max(Product.id)))).scalar_one()
            await session.execute(
                text("SELECT setval(pg_get_serial_sequence('products', 'id'), :max_id)"),
                {"max_id": max_id},
            )
            await session.commit()
    await engine.dispose()
    return len(products)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.scripts.import_catalogue path/to/catalogue.csv")
    count = asyncio.run(import_catalogue(Path(sys.argv[1])))
    print(f"Imported {count} products")


if __name__ == "__main__":
    main()
