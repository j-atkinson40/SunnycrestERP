"""Two-step sign-in: a user's TOTP secret and their recovery codes.

Spec: docs/investigations/2026-11-03-payroll-2-invites-and-two-step.md
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserTwoStep(Base):
    """One second factor per user.

    ⚠️ `enrolled_at IS NULL` IS A STATE, NOT A GAP. `begin_enrolment` creates the
    row with a secret and no stamp; `confirm_enrolment` stamps it once the user
    has proved they can read a code from it. Only a stamped row satisfies the
    requirement, so an abandoned enrolment grants nothing — and a user who got
    halfway cannot be mistaken for one who finished.
    """

    __tablename__ = "user_two_step"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_two_step_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    #: Fernet, reversible. TOTP verifies against the secret itself, so this
    #: cannot be a hash — it is the one secret in this module that must be
    #: recoverable.
    totp_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    enrolled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    @property
    def is_enrolled(self) -> bool:
        return self.enrolled_at is not None


class UserRecoveryCode(Base):
    """A single-use recovery code, stored hashed.

    ⚠️ `used_at` IS STAMPED, NOT DELETED. Single-use is enforced by the stamp, so
    "which codes has she spent, and when" stays answerable — a deleted row
    answers neither.
    """

    __tablename__ = "user_recovery_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    #: bcrypt. These are compared and never shown again, so hashing is right
    #: here where the TOTP secret needed encryption.
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
