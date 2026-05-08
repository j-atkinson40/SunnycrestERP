"""WorkflowReviewItem — canonical workflow review-pause primitive.

Created by ``invoke_review_focus`` workflow step. Consumed by the
canonical ``workflow_review_triage`` queue. Decided by reviewer
action (approve / reject / edit_and_approve), at which point
``workflow_review_adapter.commit_decision`` advances the underlying
``WorkflowRun`` with the decision payload.

See ``r92_workflow_review_items`` migration for full schema + index
discipline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkflowReviewItem(Base):
    __tablename__ = "workflow_review_items"
    __table_args__ = (
        CheckConstraint(
            "decision IS NULL OR decision IN ('approve', 'reject', 'edit_and_approve')",
            name="ck_workflow_review_items_decision",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_step_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_run_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id"),
        nullable=False,
    )
    review_focus_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    edited_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
