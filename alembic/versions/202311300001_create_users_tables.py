"""create users tables"""

from alembic import op
import sqlalchemy as sa


revision = "202311300001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255)),
        sa.Column("photo_url", sa.String(length=512)),
        sa.Column("title", sa.String(length=255)),
        sa.Column("company", sa.String(length=255)),
        sa.Column("location", sa.String(length=255)),
        sa.Column("provider", sa.String(length=50)),
        sa.Column("provider_user_id", sa.String(length=255)),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bio", sa.Text()),
        sa.Column("timezone", sa.String(length=64)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_provider_user_id", "users", ["provider_user_id"])

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_pref"),
    )

    op.create_table(
        "user_social_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255)),
        sa.Column("display_name", sa.String(length=255)),
        sa.Column("profile_url", sa.String(length=512)),
        sa.Column("last_connected_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_social"),
    )


def downgrade() -> None:
    op.drop_table("user_social_accounts")
    op.drop_table("user_preferences")
    op.drop_index("ix_users_provider_user_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
