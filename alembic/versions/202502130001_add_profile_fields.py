"""add extended profile fields"""

from alembic import op
import sqlalchemy as sa


revision = "202502130001"
down_revision = "202311300001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("industry", sa.String(length=255)))
    op.add_column("users", sa.Column("linkedin_url", sa.String(length=512)))
    op.add_column("users", sa.Column("experience_years", sa.Integer()))
    op.add_column("users", sa.Column("skills", sa.Text()))
    op.add_column("users", sa.Column("interests", sa.Text()))
    op.create_index(
        "ix_users_industry_location",
        "users",
        ["industry", "location"],
    )
    op.create_index("ix_users_created_at", "users", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_industry_location", table_name="users")
    op.drop_column("users", "interests")
    op.drop_column("users", "skills")
    op.drop_column("users", "experience_years")
    op.drop_column("users", "linkedin_url")
    op.drop_column("users", "industry")
