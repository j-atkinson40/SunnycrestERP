from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SafetyInspectionTemplate(Base):
    __tablename__ = "safety_inspection_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    template_name: Mapped[str] = mapped_column(String(200))
    inspection_type: Mapped[str] = mapped_column(String(20))
    equipment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frequency_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    items = relationship("SafetyInspectionItem", back_populates="template")


class SafetyInspectionItem(Base):
    __tablename__ = "safety_inspection_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("safety_inspection_templates.id"), nullable=False, index=True
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    item_order: Mapped[int] = mapped_column(Integer)
    item_text: Mapped[str] = mapped_column(Text)
    response_type: Mapped[str] = mapped_column(String(20))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    osha_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    template = relationship("SafetyInspectionTemplate", back_populates="items")


class SafetyInspection(Base):
    __tablename__ = "safety_inspections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("safety_inspection_templates.id"), nullable=False
    )
    equipment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    equipment_identifier: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    inspector_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    inspection_date: Mapped[datetime] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="in_progress")
    overall_result: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    template = relationship("SafetyInspectionTemplate")
    results = relationship("SafetyInspectionResult", back_populates="inspection")


class SafetyInspectionResult(Base):
    __tablename__ = "safety_inspection_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("safety_inspections.id"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("safety_inspection_items.id"), nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    finding_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrective_action_required: Mapped[bool] = mapped_column(Boolean, default=False)
    corrective_action_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    corrective_action_due_date: Mapped[datetime | None] = mapped_column(
        Date, nullable=True
    )
    corrective_action_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    corrective_action_completed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    photo_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    inspection = relationship("SafetyInspection", back_populates="results")
    item = relationship("SafetyInspectionItem")
