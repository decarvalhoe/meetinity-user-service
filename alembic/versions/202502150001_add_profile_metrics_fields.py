"""Add derived profile metrics fields."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202502150001"
down_revision: Union[str, None] = "202502140001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "profile_completeness",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "trust_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "privacy_level",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'standard'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("reactivation_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.alter_column("users", "profile_completeness", server_default=None)
    op.alter_column("users", "trust_score", server_default=None)
    op.alter_column("users", "privacy_level", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "reactivation_at")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "privacy_level")
    op.drop_column("users", "trust_score")
    op.drop_column("users", "profile_completeness")
