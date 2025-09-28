"""Expand user engagement and security entities.

Revision ID: 202502140001
Revises: 202502130001
Create Date: 2025-02-14 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202502140001"
down_revision: Union[str, None] = "202502130001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "engagement_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reputation_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "privacy_settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "active_tokens",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )

    op.create_table(
        "user_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "score_delta",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_user_activities_user_created",
        "user_activities",
        ["user_id", "created_at"],
    )

    op.create_table(
        "user_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "method",
            name="uq_user_verification_method",
        ),
    )
    op.create_index(
        "ix_user_verifications_expires",
        "user_verifications",
        ["expires_at"],
    )

    op.create_table(
        "user_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("connection_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "target_user_id",
            "connection_type",
            name="uq_user_connection_target",
        ),
    )
    op.create_index(
        "ix_user_connections_updated",
        "user_connections",
        ["updated_at"],
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_token", sa.String(length=255), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_token", name="uq_user_session_token"),
    )
    op.create_index(
        "ix_user_sessions_expires",
        "user_sessions",
        ["expires_at"],
    )
    op.create_index(
        "ix_user_sessions_created",
        "user_sessions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_sessions_created", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index("ix_user_connections_updated", table_name="user_connections")
    op.drop_table("user_connections")

    op.drop_index("ix_user_verifications_expires", table_name="user_verifications")
    op.drop_table("user_verifications")

    op.drop_index(
        "ix_user_activities_user_created",
        table_name="user_activities",
    )
    op.drop_table("user_activities")

    op.drop_column("users", "active_tokens")
    op.drop_column("users", "privacy_settings")
    op.drop_column("users", "reputation_score")
    op.drop_column("users", "engagement_score")
