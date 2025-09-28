"""SQLAlchemy models for user data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class User(Base):
    """Primary user record."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_industry_location", "industry", "location"),
        Index("ix_users_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    title: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    experience_years: Mapped[int | None] = mapped_column(Integer())
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_user_id: Mapped[str | None] = mapped_column(
        String(255), index=True
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    bio: Mapped[str | None] = mapped_column(Text())
    skills: Mapped[str | None] = mapped_column(Text())
    interests: Mapped[str | None] = mapped_column(Text())
    timezone: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    preferences: Mapped[list["UserPreference"]] = relationship(
        "UserPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    social_accounts: Mapped[list["UserSocialAccount"]] = relationship(
        "UserSocialAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    activities: Mapped[list["UserActivity"]] = relationship(
        "UserActivity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    verifications: Mapped[list["UserVerification"]] = relationship(
        "UserVerification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    connections: Mapped[list["UserConnection"]] = relationship(
        "UserConnection",
        primaryjoin="User.id==UserConnection.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    engagement_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    reputation_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    privacy_settings: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    active_tokens: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )

    def touch_login(self, at: datetime) -> None:
        """Update login metadata."""

        self.last_login = at
        self.last_active_at = at
        self.login_count = (self.login_count or 0) + 1


class UserPreference(Base):
    """Key/value preferences associated with a user."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_pref"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="preferences")


class UserSocialAccount(Base):
    """Additional social connections for a user."""

    __tablename__ = "user_social_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_social"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str | None] = mapped_column(String(512))
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    user: Mapped[User] = relationship("User", back_populates="social_accounts")


class UserActivity(Base):
    """Chronological record of user actions."""

    __tablename__ = "user_activities"
    __table_args__ = (
        Index("ix_user_activities_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    score_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="activities")


class UserVerification(Base):
    """Verification requests (email, phone, etc.)."""

    __tablename__ = "user_verifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "method",
            name="uq_user_verification_method",
        ),
        Index("ix_user_verifications_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="verifications")


class UserConnection(Base):
    """Relationship to other users or external identities."""

    __tablename__ = "user_connections"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "target_user_id",
            "connection_type",
            name="uq_user_connection_target",
        ),
        Index("ix_user_connections_updated", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    external_reference: Mapped[str | None] = mapped_column(String(255))
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", server_default="pending"
    )
    attributes: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(
        "User",
        primaryjoin="User.id==UserConnection.user_id",
        back_populates="connections",
    )
    target_user: Mapped[User | None] = relationship(
        "User",
        primaryjoin="User.id==UserConnection.target_user_id",
        lazy="selectin",
    )


class UserSession(Base):
    """Encrypted session tokens issued to a user."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("session_token", name="uq_user_session_token"),
        Index("ix_user_sessions_expires", "expires_at"),
        Index("ix_user_sessions_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_token: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_payload: Mapped[str | None] = mapped_column(Text())
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")
