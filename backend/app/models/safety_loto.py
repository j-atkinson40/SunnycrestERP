from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SafetyLotoProcedure(Base):
    __tablename__ = "safety_loto_procedures"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    machine_name: Mapped[str] = mapped_column(String(200))
    machine_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    machine_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    procedure_number: Mapped[str] = mapped_column(String(50))
    energy_sources: Mapped[str] = mapped_column(Text)
    ppe_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[str] = mapped_column(Text)
    estimated_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    authorized_employees: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_employees: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
