from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SafetyTrainingRequirement(Base):
    __tablename__ = "safety_training_requirements"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    training_topic: Mapped[str] = mapped_column(String(200))
    osha_standard_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    applicable_roles: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_training_required: Mapped[bool] = mapped_column(Boolean, default=True)
    refresher_frequency_months: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    new_hire_deadline_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )


class SafetyTrainingEvent(Base):
    __tablename__ = "safety_training_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    training_topic: Mapped[str] = mapped_column(String(200))
    osha_standard_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    training_type: Mapped[str] = mapped_column(String(30))
    trainer_name: Mapped[str] = mapped_column(String(200))
    trainer_type: Mapped[str] = mapped_column(String(30))
    training_date: Mapped[datetime] = mapped_column(Date)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_materials_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class EmployeeTrainingRecord(Base):
    __tablename__ = "employee_training_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    training_event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("safety_training_events.id"), nullable=False
    )
    completion_status: Mapped[str] = mapped_column(String(20))
    test_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    certificate_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
