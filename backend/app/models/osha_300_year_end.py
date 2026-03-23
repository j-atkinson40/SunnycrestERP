import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OSHA300YearEndRecord(Base):
    __tablename__ = "osha_300_year_end_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "year", name="uq_osha_300_year_end_tenant_year"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="not_started"
    )
    review_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_completed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_count_at_review: Mapped[int | None] = mapped_column(Integer, nullable=True)
    form_300a_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    form_300a_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    form_300a_certified_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    form_300a_certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    form_300a_certified_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    form_300a_certified_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    posting_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posting_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posting_period_end_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reviewer = relationship("User", foreign_keys=[review_completed_by])
    certifier = relationship("User", foreign_keys=[form_300a_certified_by])
