"""PortalUser — Workflow Arc Phase 8e.2.

Separate identity store for portal-authed users (drivers, future
family/supplier/customer portals). Per SPACES_ARCHITECTURE.md §10:

  - Identity-level separation from tenant `User` — prevents
    cross-realm privilege bleed at the query layer.
  - Tenant-scoped via `company_id`; no cross-tenant identity.
  - Assigned to exactly one Space (by `assigned_space_id`,
    matching a `SpaceConfig.space_id` in the tenant admin's
    preferences). Session scope enforced at JWT layer.
  - Auth flow: invite (admin-driven, token-based) → first-password
    set → login → 12h access + 7d refresh JWT (realm="portal").
    Lockout after 10 failed logins for 30 minutes.

Business-logic invariant (NOT a DB constraint): exactly one of
`drivers.employee_id` OR `drivers.portal_user_id` is populated per
Driver row. CHECK constraint omitted deliberately to permit
migration windows where a Driver transitions between tenant-user
and portal-user identities. Tests verify the invariant.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PortalUser(Base):
    __tablename__ = "portal_users"
    __table_args__ = (
        UniqueConstraint(
            "email", "company_id", name="uq_portal_users_email_company"
        ),
        Index("ix_portal_users_company", "company_id"),
        Index(
            "uq_portal_users_invite_token",
            "invite_token",
            unique=True,
            postgresql_where=text("invite_token IS NOT NULL"),
        ),
        Index(
            "uq_portal_users_recovery_token",
            "recovery_token",
            unique=True,
            postgresql_where=text("recovery_token IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable: invited-but-not-yet-password-set portal users have no hash.
    hashed_password: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Matches SpaceConfig.space_id ("sp_<12 hex>"). No FK — spaces
    # live in JSONB on the tenant admin's User.preferences row.
    # Session middleware verifies that (a) portal_user.is_active,
    # (b) portal_user.assigned_space_id == token.space_id.
    assigned_space_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invited_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    invite_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invite_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Password recovery flow — distinct from invite so they don't collide.
    recovery_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    recovery_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    company = relationship("Company")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])

    def __repr__(self) -> str:
        return (
            f"<PortalUser {self.email} company={self.company_id[:8]} "
            f"space={self.assigned_space_id} active={self.is_active}>"
        )
