"""add indexes to support repository queries

Revision ID: 202502150001
Revises: 202502140001
Create Date: 2025-02-15 00:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202502150001"
down_revision: Union[str, None] = "202502140001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_users_updated_at", "users", ["updated_at"])
    op.create_index("ix_users_last_login", "users", ["last_login"])
    op.create_index("ix_users_last_active_at", "users", ["last_active_at"])
    op.create_index("ix_users_experience_years", "users", ["experience_years"])


def downgrade() -> None:
    op.drop_index("ix_users_experience_years", table_name="users")
    op.drop_index("ix_users_last_active_at", table_name="users")
    op.drop_index("ix_users_last_login", table_name="users")
    op.drop_index("ix_users_updated_at", table_name="users")

