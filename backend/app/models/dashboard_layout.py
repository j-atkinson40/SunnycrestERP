"""DashboardLayout model — Phase R-0 of the Runtime-Aware Editor.

3-tier scope-inheritance table for dashboard widget arrangements.
Closes the pre-existing gap where `user_widget_layouts` was per-user
only with no platform/vertical/tenant default layer.

Resolution chain (computed at READ time in widget_service):
    user_override (UserWidgetLayout, existing)
        ←  tenant_default (this table, scope='tenant_default')
            ←  vertical_default (this table, scope='vertical_default')
                ←  platform_default (this table, scope='platform_default')
                    ←  in-code WIDGET_DEFINITIONS.default_position fallback

Versioned via service-layer write-side pattern: each save deactivates
the prior active row + inserts a new active row with version + 1.
The partial unique on `is_active=true` enforces "at most one active
row per (scope, vertical, tenant_id, page_context)"; inactive rows
accumulate for audit.

Layout config shape mirrors what UserWidgetLayout already stores:
    [
        {
            "widget_id": str,
            "enabled": bool,
            "position": int,
            "size": str,        # e.g. "2x1", "1x1"
            "config": dict,
        },
        ...
    ]

See migration `r87_dashboard_layouts` for full schema doc.
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"
SCOPE_TENANT_DEFAULT = "tenant_default"


class DashboardLayout(Base):
    """3-tier scope-inheritance row for a dashboard page_context."""

    __tablename__ = "dashboard_layouts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
    )
    page_context: Mapped[str] = mapped_column(String(96), nullable=False)

    layout_config: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_default')",
            name="ck_dashboard_layouts_scope",
        ),
        CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_default'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_dashboard_layouts_scope_keys",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DashboardLayout(id={self.id}, page_context={self.page_context}, "
            f"scope={self.scope}, version={self.version}, "
            f"is_active={self.is_active})>"
        )
