"""link orders to the customer's account (GET /orders/mine)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_orders_user_id_users", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_orders_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_user_id")
        batch.drop_constraint("fk_orders_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
