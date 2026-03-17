from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SafetyChemical(Base):
    __tablename__ = "safety_chemicals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    chemical_name: Mapped[str] = mapped_column(String(200))
    manufacturer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cas_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity_on_hand: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hazard_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    ppe_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    sds_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sds_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    sds_review_due_at: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
