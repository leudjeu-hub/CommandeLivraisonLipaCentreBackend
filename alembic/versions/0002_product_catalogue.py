"""product columns from catalogue.csv

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column("category", sa.String(length=20), nullable=False, server_default="Scolaire")
        )
        batch.add_column(
            sa.Column("description", sa.String(length=500), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("label", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("name_en", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("description_en", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("label_en", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("color", sa.String(length=7), nullable=True))
        batch.add_column(
            sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(sa.Column("status", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("image", sa.String(length=255), nullable=True))
        batch.alter_column("price", existing_type=sa.Float(), nullable=True)
        batch.create_check_constraint(
            "ck_products_category", "category IN ('Scolaire', 'Bureau', 'Livres')"
        )
        batch.create_index("ix_products_category", ["category"], unique=False)


def downgrade() -> None:
    op.execute("UPDATE products SET price = 0 WHERE price IS NULL")
    with op.batch_alter_table("products") as batch:
        batch.drop_index("ix_products_category")
        batch.drop_constraint("ck_products_category", type_="check")
        batch.alter_column("price", existing_type=sa.Float(), nullable=False)
        for column in (
            "image",
            "status",
            "available",
            "color",
            "label_en",
            "description_en",
            "name_en",
            "label",
            "description",
            "category",
        ):
            batch.drop_column(column)
