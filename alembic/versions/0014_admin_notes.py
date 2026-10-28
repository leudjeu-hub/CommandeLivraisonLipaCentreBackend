"""internal remarks on orders and accounts (Gestion), never shown to customers

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("admin_notes", sa.Text(), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("admin_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("admin_notes")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("admin_notes")
