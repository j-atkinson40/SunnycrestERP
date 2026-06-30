"""MoC task vocabulary — the constrained-but-editable value store (Task Editing 2a).

frequency/task_type on moc_task_catalog were free-form (the canon note). This
resolves that to CONSTRAINED-EDITABLE: a task's frequency/type must be a value
that exists HERE, but the store itself is editable (add a value = insert a row,
no code change — configuration-over-plugins).

Scope mirrors moc_task_catalog / moc_pages exactly: three-tier
`platform_default → vertical_default → tenant_override`. A value is either
platform-wide (vertical NULL, shared across every MoC) or vertical-specific. The
picker for vertical V reads platform values + V's values.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCTaskVocabulary(Base):
    __tablename__ = "moc_task_vocabulary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # 'frequency' | 'type'
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    # platform_default | vertical_default | tenant_override
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="platform_default"
    )
    vertical: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("verticals.slug"), nullable=True, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True, index=True
    )
    display_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # Soft-delete: deactivating a value keeps tasks referencing it from orphaning.
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    # Realm-agnostic actor (tenant User OR platform PlatformUser) — FK-less, like
    # moc_task_catalog.
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('frequency', 'type')", name="ck_moc_task_vocabulary_kind"
        ),
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_moc_task_vocabulary_scope",
        ),
    )
