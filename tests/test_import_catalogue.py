from pathlib import Path

from app.models.product import ProductCategory
from app.scripts.import_catalogue import read_catalogue

CSV = (
    "﻿id;categorie;prix;nom;description;vignette;nom_en;description_en;vignette_en;"
    "couleur;statut;image\n"
    "1;Scolaire;1 500;Cahier A4 · 200 pages;Quadrillé.;CAHIER / 200 PAGES;A4 notebook;"
    "Squared paper.;NOTEBOOK / 200 PAGES;#31574b;;img/produits/cahier-a4-200.webp\n"
    "8;Livres;;Livre scolaire sur demande;Précisez le titre.;APPRENDRE;;;;#486473;disponible;\n"
)


def test_read_catalogue(tmp_path: Path) -> None:
    path = tmp_path / "catalogue.csv"
    path.write_text(CSV, encoding="utf-8")
    products = dict(read_catalogue(path))
    assert set(products) == {1, 8}
    notebook = products[1]
    assert notebook.category is ProductCategory.SCOLAIRE
    assert notebook.price == 1500
    assert notebook.label_en == "NOTEBOOK / 200 PAGES"
    book = products[8]
    assert book.price is None
    assert book.name_en is None
    assert book.status == "disponible"
    assert book.image is None
    assert book.available is True
