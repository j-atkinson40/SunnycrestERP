"""Phase R-6.2a — Form intake submission record.

Append-only by service contract. ``submitted_data`` JSONB carries the
family's field values keyed by field_id; ``submitter_metadata`` JSONB
captures IP + user_agent for spam triage.

Per-row denormalized classification outcome (tier + workflow_id +
workflow_run_id + reasoning JSONB) stored directly on the submission
row. R-6.1's email-bound ``workflow_email_classifications`` table is
deliberately NOT extended cross-source; the audit chain for form +
file lives on each adapter's record table. Future R-6.x hygiene MAY
unify the audit substrate when concrete signal warrants.

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


class IntakeFormSubmission(Base):
    """Append-only form submission record with denormalized classification
    outcome."""

    __tablename__ = "intake_form_submissions"
    __table_args__ = (
        CheckConstraint(
            "classification_tier IS NULL OR classification_tier IN (1, 2, 3)",
            name="ck_intake_form_submissions_tier",
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
        ForeignKey("intake_form_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submitted_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    submitter_metadata: Mapped[dict] = mapped_column(
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
