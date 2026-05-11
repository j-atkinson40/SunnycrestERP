"""Phase R-6.2a — File intake adapter configuration.

Three-scope inheritance at READ time. ``allowed_content_types`` is a
JSONB list of MIME types; server-side validation rejects uploads
outside the list. ``max_file_size_bytes`` + ``max_file_count`` cap
the upload payload.

``r2_key_prefix_template`` is a string template applied at upload
time with placeholders ``{tenant_id}``, ``{adapter_slug}``,
``{upload_id}``. The resulting key lives under the canonical R2
``tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}`` namespace.

``metadata_schema`` shape matches form_schema (version + fields[] +
captcha_required) and renders ABOVE the file selector on the upload
page.

Migration: r94_intake_adapter_configurations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
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


class IntakeFileConfiguration(Base):
    """Per-adapter file upload point configuration."""

    __tablename__ = "intake_file_configurations"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_intake_file_configurations_scope",
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
    allowed_content_types: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    max_file_size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=10 * 1024 * 1024
    )
    max_file_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    r2_key_prefix_template: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}",
    )
    metadata_schema: Mapped[dict] = mapped_column(
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
