import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OSHA300Entry(Base):
    __tablename__ = "osha_300_entries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    incident_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("safety_incidents.id"), nullable=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_name: Mapped[str] = mapped_column(String(200), nullable=False)
    employee_job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_injury: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="other_recordable"
    )  # days_away, restricted_work, transfer, other_recordable, death
    days_away: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_restricted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    injury_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="injury"
    )  # injury, skin_disorder, respiratory, poisoning, hearing_loss, other
    privacy_case: Mapped[bool] = mapped_column(Boolean, default=False)
    is_auto_populated: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, server_default="false")
    correction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    corrected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    incident = relationship("SafetyIncident", foreign_keys=[incident_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
