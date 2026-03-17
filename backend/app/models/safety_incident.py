from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SafetyIncident(Base):
    __tablename__ = "safety_incidents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    incident_type: Mapped[str] = mapped_column(String(30))
    incident_date: Mapped[datetime] = mapped_column(Date)
    incident_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    location: Mapped[str] = mapped_column(String(200))
    involved_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    witnesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    immediate_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_part_affected: Mapped[str | None] = mapped_column(String(100), nullable=True)
    injury_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    medical_treatment: Mapped[str] = mapped_column(String(30), default="none")
    days_away_from_work: Mapped[int] = mapped_column(Integer, default=0)
    days_on_restricted_duty: Mapped[int] = mapped_column(Integer, default=0)
    osha_recordable: Mapped[bool] = mapped_column(Boolean, default=False)
    osha_300_case_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reported_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    investigated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    corrective_actions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="reported")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
