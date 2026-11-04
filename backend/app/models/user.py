import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "company_id", name="uq_users_email_company"),
        Index(
            "uq_users_username_company",
            "company_id",
            "username",
            unique=True,
            postgresql_where="username IS NOT NULL",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # ⚠️ NULLABLE SINCE r226, AND NULL IS A STATE WITH A NAME: invited, not yet
    # accepted. An invited user exists before any password does. The DB CHECK
    # `ck_users_password_or_invite` is what stops this from being a licence to
    # create a passwordless account by forgetting one — see r226's docstring.
    # Every read must handle None; there are two, both in auth_service.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Tenant user invites (r226, Payroll 2 ruling 4) ──────────────────
    # A HASH, never the token: a read of this table must not yield working
    # invite links. sha256 rather than bcrypt because the token is 256 bits of
    # CSPRNG — guess-resistance is free and indexability is not.
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invite_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invited_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Phase 3b — gates editing of platform-global prompts. Set manually
    # (no UI yet). See backend/app/api/deps.py::require_super_admin.
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Two-track employee model
    track: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="office_management"
    )
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pin_encrypted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    console_access = mapped_column(JSONB, nullable=True)
    idle_timeout_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="30"
    )
    last_console_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Calendar sync
    calendar_token: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Saved Views Phase 2 (r32): generic per-user JSONB flag bag.
    # Today holds `saved_views_seeded_for_roles: list[str]` (see
    # `app.services.saved_views.seed`). Future phases extend with
    # additional per-user flags. `server_default='{}'` keeps reads
    # null-safe without extra checks.
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        default=dict,
    )

    # Phase W-4a — operator profile fields per BRIDGEABLE_MASTER §3.26.3.
    # `work_areas` is multi-select per §3.26.3.1 (Production Scheduling,
    # Delivery Scheduling, Inventory Management, etc.) and drives Tier
    # 1 rule-based Pulse composition. `responsibilities_description` is
    # free text per §3.26.3.2 used by Tier 2+ intelligence post-W-4a.
    # Both NULL during onboarding window — Pulse falls back to
    # vertical-default composition (D4 resolution) until populated.
    work_areas: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    responsibilities_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    role_obj = relationship("Role", back_populates="users", foreign_keys=[role_id])
    permission_overrides = relationship(
        "UserPermissionOverride", back_populates="user", cascade="all, delete-orphan",
        foreign_keys="[UserPermissionOverride.user_id]",
    )
    profile = relationship(
        "EmployeeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan",
        foreign_keys="[EmployeeProfile.user_id]",
    )
