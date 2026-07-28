"""Focus persistence models — Phase A Session 4.

Two tables:

- `focus_sessions`: per-user session state for a specific Focus.
  `layout_state` JSONB mirrors the frontend LayoutState shape — a
  widgets dict keyed by WidgetId with position (anchor, offsetX,
  offsetY, width, height). Soft-delete via `is_active=False` so closed
  sessions remain queryable for the "recent closed" resume window.

- `focus_layout_defaults`: per-tenant admin baseline per focus_type.
  Unique on (company_id, focus_type). Admin-managed; no soft delete.

Used by `app.services.focus.focus_session_service.resolve_layout_state`
which implements the 3-tier cascade: active user session → recent
closed user session → tenant default → null. Frontend callers use the
API endpoint and don't see the tiers directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    focus_type: Mapped[str] = mapped_column(String(64), nullable=False)
    layout_state: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # S-3b (r146) — per-user, Focus-scoped editing draft (e.g. the quote
    # edit-canvas line items). DELIBERATELY SEPARATE from layout_state:
    # layout_state is widget geometry auto-seeded by the tenant-default
    # cascade; a draft must not be seeded from a team layout or clobbered
    # by the layout resolver. Nullable — most Focus types never set it.
    # THE HARD INVARIANT: this is Focus session state, NOT a quote. No
    # quotes-domain read path ever surfaces it; a quote materializes only
    # at explicit save (create_quote), never from this column.
    draft_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_interacted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # v1 task substrate B1 r108 — FK to vault_items.id (the canonical
    # task identifier; task_details.vault_item_id maps 1:1).
    # ON DELETE SET NULL: deleting a task VaultItem leaves the focus
    # session row intact with task_id cleared (preserves session history).
    task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("vault_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", foreign_keys=[user_id])
    company = relationship("Company", foreign_keys=[company_id])


class FocusLayoutDefault(Base):
    __tablename__ = "focus_layout_defaults"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    focus_type: Mapped[str] = mapped_column(String(64), nullable=False)
    layout_state: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    company = relationship("Company", foreign_keys=[company_id])


__all__ = ["FocusSession", "FocusLayoutDefault"]
