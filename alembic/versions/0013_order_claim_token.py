"""code to attach a guest's order to an account later (POST /orders/claim)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("claim_token_hash", sa.String(length=64), nullable=True))
        batch.create_index("ix_orders_claim_token_hash", ["claim_token_hash"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_claim_token_hash")
        batch.drop_column("claim_token_hash")
