"""UrnEngravingJob model — engraving specs and proof workflow for drop-ship orders."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UrnEngravingJob(Base):
    __tablename__ = "urn_engraving_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    urn_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("urn_orders.id"), nullable=False, index=True
    )

    # Piece identification
    piece_label: Mapped[str] = mapped_column(
        String(50), nullable=False, default="main"
    )  # main | companion_1 | companion_2 | companion_3

    # Engraving specs
    engraving_line_1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    engraving_line_2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    engraving_line_3: Mapped[str | None] = mapped_column(String(500), nullable=True)
    engraving_line_4: Mapped[str | None] = mapped_column(String(500), nullable=True)
    font_selection: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color_selection: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Photo etch
    photo_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Wilbert form
    generated_form_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Proof workflow
    proof_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_submitted"
    )
    # not_submitted | awaiting_proof | proof_received | awaiting_fh_approval |
    # fh_approved | fh_changes_requested | approved | rejected

    proof_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    proof_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FH approval (token-based, no login required)
    fh_approval_token: Mapped[str | None] = mapped_column(
        String(200), nullable=True, unique=True
    )
    fh_approval_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fh_approved_by_name: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )
    fh_approved_by_email: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    fh_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fh_change_request_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Staff final approval
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resubmission_count: Mapped[int] = mapped_column(Integer, default=0)

    # Verbal approval (call intelligence)
    verbal_approval_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    verbal_approval_transcript_excerpt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tenant = relationship("Company", foreign_keys=[tenant_id])
    urn_order = relationship(
        "UrnOrder", back_populates="engraving_jobs", foreign_keys=[urn_order_id]
    )
    approved_by_user = relationship("User", foreign_keys=[approved_by])
