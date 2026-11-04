"""Admin impersonation session — full audit trail of super admin acting as tenant user."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminImpersonationSession(Base):
    __tablename__ = "admin_impersonation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("platform_users.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    impersonated_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="production")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # ⚠️ RECORDS A DELIBERATE BYPASS (r225). Impersonation mints a tenant token
    # directly, and per James's 2026-11-03 ruling that token is marked
    # MFA-satisfied so support can still reach a payroll user. Writing it down
    # here is what makes the bypass auditable instead of implied: a reader can
    # ask "did a payroll-reaching token ever exist without a second step" and
    # get an answer. NULL on rows predating r225 — nobody measured it for them.
    mfa_satisfied_by_admin: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
