"""Phase R-6.2a — File intake upload record.

Append-only by service contract. ``r2_key`` is the canonical R2
storage key (server-built from the config's r2_key_prefix_template);
``content_type`` + ``size_bytes`` are server-verified at completion
time.

Per-row denormalized classification outcome lives directly on the
upload row (same canon as IntakeFormSubmission).

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
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IntakeFileUpload(Base):
    """Append-only file upload record with denormalized classification
    outcome."""

    __tablename__ = "intake_file_uploads"
    __table_args__ = (
        CheckConstraint(
            "classification_tier IS NULL OR classification_tier IN (1, 2, 3)",
            name="ck_intake_file_uploads_tier",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intake_file_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploader_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Denormalized classification outcome (post-cascade).
    classification_tier: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    classification_workflow_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    classification_workflow_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    classification_is_suppressed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    classification_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
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
