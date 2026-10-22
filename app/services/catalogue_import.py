"""Catalogue import from a CSV file sent by an administrator (`POST /products/import`).

Columns use the French headers of the site's export (`id;categorie;prix;nom;…`). A row with an
`id` updates that product; a row without one updates the product with the same name (ignoring
case) or creates a new one. Only the columns present in the file are written on update, so a file
with just `id;prix` changes prices and nothing else. An empty cell means "no value" (no price =
price on request, empty stock = 0). Nothing is written while any row has an error.
"""

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductCategory
from app.schemas.product import ProductCreate

MAX_ROWS = 2000

# CSV header -> Product attribute
COLUMNS = {
    "id": "id",
    "categorie": "category",
    "prix": "price",
    "nom": "name",
    "description": "description",
    "vignette": "label",
    "nom_en": "name_en",
    "description_en": "description_en",
    "vignette_en": "label_en",
    "couleur": "color",
    "disponible": "available",
    "statut": "status",
    "image": "image",
    "stock": "stock",
}
TEXT_LIMITS = {
    "name": 255,
    "description": 500,
    "label": 255,
    "name_en": 255,
    "description_en": 500,
    "label_en": 255,
    "status": 50,
    "image": 255,
}
TRUE = {"oui", "o", "yes", "y", "vrai", "true", "1", "x"}
FALSE = {"non", "n", "no", "faux", "false", "0"}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
# Same rule as the site's form: a local image, allowed by the site's CSP.
IMAGE = re.compile(r"^img/[\w./-]+\.(webp|avif|png|jpe?g|svg)$", re.IGNORECASE)


@dataclass
class RowProblem:
    """One problem, with a code the site translates. `line` 1 is the header row."""

    line: int
    code: str
    column: str | None = None
    value: str | None = None


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[RowProblem] = field(default_factory=list)


class _RowError(Exception):
    def __init__(self, code: str, column: str, value: str | None = None) -> None:
        self.code, self.column, self.value = code, column, value


def _parse_cell(column: str, raw: str) -> Any:
    value = raw.strip()
    attr = COLUMNS[column]
    if attr == "category":
        for category in ProductCategory:
            if category.value.lower() == value.lower():
                return category
        raise _RowError("required" if not value else "invalid_category", column, value)
    if attr == "price":
        digits = re.sub(r"\s", "", value)  # "1 500", also with no-break spaces
        if not digits:
            return None
        if not digits.isdigit() or int(digits) == 0:
            raise _RowError("invalid_price", column, value)
        return float(digits)
    if attr == "stock":
        digits = re.sub(r"\s", "", value)  # "1 500", also with no-break spaces
        if not digits:
            return 0
        if not digits.isdigit():
            raise _RowError("invalid_stock", column, value)
        return int(digits)
    if attr == "available":
        if not value or value.lower() in TRUE:
            return True
        if value.lower() in FALSE:
            return False
        raise _RowError("invalid_available", column, value)
    if attr == "color":
        if value and not HEX_COLOR.match(value):
            raise _RowError("invalid_color", column, value)
        return value or None
    if attr == "image":
        if value and (not IMAGE.match(value) or ".." in value):
            raise _RowError("invalid_image", column, value)
        return value or None
    if len(value) > TEXT_LIMITS[attr]:
        raise _RowError("too_long", column, str(TEXT_LIMITS[attr]))
    if attr == "name":
        if not value:
            raise _RowError("required", column)
        return value
    if attr == "description":
        return value
    return value or None


def _read_rows(
    content: str, report: ImportReport
) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    content = content.lstrip("\ufeff")
    if not content.strip():
        report.errors.append(RowProblem(line=1, code="empty"))
        return [], []
    header_line = content.lstrip().splitlines()[0]
    delimiter = ";" if header_line.count(";") >= header_line.count(",") else ","
    reader = csv.reader(io.StringIO(content.lstrip(), newline=""), delimiter=delimiter)
    header = [h.strip().lower() for h in next(reader)]
    unknown = [h for h in header if h not in COLUMNS]
    for name in unknown:
        report.errors.append(RowProblem(line=1, code="unknown_column", value=name))
    for name in {h for h in header if header.count(h) > 1}:
        report.errors.append(RowProblem(line=1, code="duplicate_column", value=name))
    if "id" not in header and "nom" not in header:
        report.errors.append(RowProblem(line=1, code="missing_key_column"))
    if report.errors:
        return header, []
    rows: list[tuple[int, dict[str, str]]] = []
    for cells in reader:
        if not any(c.strip() for c in cells):
            continue
        line = reader.line_num
        if len(rows) == MAX_ROWS:
            report.errors.append(RowProblem(line=line, code="too_many_rows", value=str(MAX_ROWS)))
            break
        if len(cells) > len(header) and any(c.strip() for c in cells[len(header) :]):
            report.errors.append(RowProblem(line=line, code="extra_cells"))
            continue
        cells += [""] * (len(header) - len(cells))
        rows.append((line, dict(zip(header, cells, strict=False))))
    return header, rows


async def import_catalogue(session: AsyncSession, content: str, apply: bool) -> ImportReport:
    report = ImportReport()
    header, rows = _read_rows(content, report)
    if report.errors:
        return report

    products: Sequence[Product] = (await session.execute(select(Product))).scalars().all()
    by_id = {p.id: p for p in products}
    by_name: dict[str, list[Product]] = {}
    for p in products:
        by_name.setdefault(p.name.strip().lower(), []).append(p)

    seen: dict[object, int] = {}  # product id or new name -> first line using it
    changes: list[tuple[Product | None, dict[str, Any]]] = []
    for line, row in rows:
        values: dict[str, Any] = {}
        try:
            for column in header:
                if column == "id":
                    continue
                values[COLUMNS[column]] = _parse_cell(column, row[column])
        except _RowError as e:
            report.errors.append(RowProblem(line, e.code, e.column, e.value))
            continue

        raw_id = row.get("id", "").strip()
        target: Product | None
        if raw_id:
            if not raw_id.isdigit() or int(raw_id) not in by_id:
                report.errors.append(RowProblem(line, "unknown_id", "id", raw_id))
                continue
            target = by_id[int(raw_id)]
        else:
            if not values.get("name"):
                report.errors.append(RowProblem(line, "required", "nom"))
                continue
            matches = by_name.get(values["name"].lower(), [])
            if len(matches) > 1:
                report.errors.append(RowProblem(line, "ambiguous_name", "nom", values["name"]))
                continue
            target = matches[0] if matches else None

        key: object = target.id if target else values["name"].lower()
        if key in seen:
            report.errors.append(RowProblem(line, "duplicate_row", value=str(seen[key])))
            continue
        seen[key] = line

        if target is None:
            if "category" not in values:
                report.errors.append(RowProblem(line, "required", "categorie"))
                continue
            try:
                ProductCreate.model_validate(values)
            except ValidationError:
                report.errors.append(RowProblem(line, "invalid_row"))
                continue
        merged = {a: getattr(target, a) for a in TEXT_LIMITS} if target else {}
        merged.update(values)
        # Same rule as the site's form: an English name needs an English description.
        if bool(merged.get("name_en")) != bool(merged.get("description_en")):
            report.errors.append(RowProblem(line, "english_pair", "nom_en"))
            continue
        changes.append((target, values))

    if report.errors:
        return report
    for target, values in changes:
        if target is None:
            report.created += 1
            if apply:
                session.add(Product(**ProductCreate.model_validate(values).model_dump()))
        elif any(getattr(target, a) != v for a, v in values.items()):
            report.updated += 1
            if apply:
                for attr, value in values.items():
                    setattr(target, attr, value)
        else:
            report.unchanged += 1
    if apply:
        await session.commit()
    return report
