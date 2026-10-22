import enum

from sqlalchemy import Boolean, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductCategory(enum.StrEnum):
    SCOLAIRE = "Scolaire"
    BUREAU = "Bureau"
    LIVRES = "Livres"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[ProductCategory] = mapped_column(
        Enum(
            ProductCategory,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    # None means "price on request" (sur devis).
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Free-text sub-category shown on the site ("Sacs et cartables"); None = not grouped.
    family: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    label_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
