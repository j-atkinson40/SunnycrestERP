"""SafetyProgramGeneration model — tracks monthly written safety program generation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SafetyProgramGeneration(Base):
    __tablename__ = "safety_program_generations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("safety_training_topics.id"), nullable=False
    )
    schedule_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenant_training_schedules.id"), nullable=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # OSHA scraper results
    osha_standard_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    osha_scraped_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    osha_scrape_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    osha_scrape_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, success, failed, skipped
    osha_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Generation
    generated_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, generating, complete, failed
    generation_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # PDF
    pdf_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=True
    )
    pdf_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Approval workflow
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft, pending_review, approved, rejected
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Posting to safety_programs
    safety_program_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("safety_programs.id"), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # Relationships
    topic = relationship("SafetyTrainingTopic")
    schedule = relationship("TenantTrainingSchedule", foreign_keys=[schedule_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    pdf_document = relationship("Document", foreign_keys=[pdf_document_id])
