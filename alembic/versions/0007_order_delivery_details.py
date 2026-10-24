"""order delivery details (orders sent by the site's form)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("kind", "area", "address", "slot", "payment", "notes", "delivery_fee")


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(
            sa.Column("kind", sa.String(length=10), nullable=False, server_default="order")
        )
        batch.add_column(sa.Column("area", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("address", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("slot", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("payment", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("delivery_fee", sa.Float(), nullable=True))
        batch.create_check_constraint("ck_orders_kind", "kind IN ('order', 'quote')")


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("ck_orders_kind", type_="check")
        for column in COLUMNS:
            batch.drop_column(column)
