"""manager role and blocked accounts

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.drop_constraint("ck_users_role", type_="check")
        batch.create_check_constraint(
            "ck_users_role", "role IN ('user', 'employee', 'manager', 'admin')"
        )


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'employee' WHERE role = 'manager'")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_role", type_="check")
        batch.create_check_constraint("ck_users_role", "role IN ('user', 'employee', 'admin')")
        batch.drop_column("is_active")
