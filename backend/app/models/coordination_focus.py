"""Job Coordination Focus models (JCF-1, migration r110).

The order-launched, job-scoped Focus instance + the FocusShare cross-tenant
grant (cloned from the DocumentShare shape per the settled decision) + the
append-only share audit + the in-platform Focus-scoped thread.

Decision-bounded access: a FocusShare's lifetime is the job's lifetime —
revoked explicitly or auto-revoked when the bound task completes (the
jcf_subscriber rides the same task-completion event family as
focus_subscriber; see DECISIONS.md 2026-06-10).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CoordinationFocusInstance(Base):
    __tablename__ = "coordination_focus_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    # One instance per landing order (the order-launched entry, idempotent).
    sales_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales_orders.id"), nullable=False, unique=True
    )
    source_fh_company_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    # Mirrors r108 focus_sessions.task_id — binds the instance to the job's
    # task so task-completion drives decision-bounded closure + auto-revoke.
    task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("vault_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FocusShare(Base):
    """Cross-tenant read grant on ONE coordination Focus instance.

    DocumentShare clone: owner/target company + optional person scope +
    permission + granted/revoked lifecycle + source_module provenance.
    """

    __tablename__ = "focus_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    instance_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coordination_focus_instances.id"),
        nullable=False,
        index=True,
    )
    owner_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    target_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    # Person-scoped when set; company-wide when NULL.
    target_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    permission: Mapped[str] = mapped_column(
        String(16), nullable=False, default="read"
    )
    granted_by_user_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    revoked_by_user_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_module: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FocusShareEvent(Base):
    """Append-only share audit (DocumentShareEvent clone):
    granted | revoked | accessed."""

    __tablename__ = "focus_share_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    share_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("focus_shares.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_company_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class JCFThreadMessage(Base):
    """The in-platform Focus-scoped thread (settled decision 2): both
    tenants post as authenticated users; authorization runs through the
    SAME read-guard as the Focus itself."""

    __tablename__ = "jcf_thread_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    instance_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coordination_focus_instances.id"),
        nullable=False,
        index=True,
    )
    author_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    author_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
