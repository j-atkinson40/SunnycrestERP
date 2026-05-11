"""Phase R-6.2a — Form intake adapter configuration.

Three-scope inheritance at READ time: tenant_override → vertical_default
→ platform_default. First match wins. Same canon as R-6.1 + the
visual editor's platform_themes / component_configurations.

``form_schema`` JSONB carries the canonical field-definition shape
documented in the migration's seed (version + fields[] + captcha_required).
Field types v1: text, textarea, email, phone, date, select, checkbox.
Conditional logic + multiselect deferred to R-6.x.

Slug is URL-routable; uniqueness enforced per-scope via three partial
unique indexes in r94 (tenant-scope / vertical-scope / platform-scope).

Migration: r94_intake_adapter_configurations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IntakeFormConfiguration(Base):
    """Per-adapter form configuration with three-scope inheritance."""

    __tablename__ = "intake_form_configurations"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_intake_form_configurations_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    vertical: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_schema: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    success_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_email_template_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )
