"""Report and audit package models."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), server_default="running")
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_package_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AuditPackage(Base):
    __tablename__ = "audit_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    package_name: Mapped[str] = mapped_column(String(200), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="generating")
    reports_included: Mapped[list] = mapped_column(JSONB, server_default="[]")
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    natural_language_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditHealthCheck(Base):
    __tablename__ = "audit_health_checks"
    __table_args__ = (UniqueConstraint("tenant_id", "check_date", name="uq_health_check_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    overall_score: Mapped[str | None] = mapped_column(String(10), nullable=True)
    green_count: Mapped[int] = mapped_column(Integer, server_default="0")
    amber_count: Mapped[int] = mapped_column(Integer, server_default="0")
    red_count: Mapped[int] = mapped_column(Integer, server_default="0")
    findings: Mapped[list] = mapped_column(JSONB, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recipient_user_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
