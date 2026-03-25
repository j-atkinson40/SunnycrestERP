"""Report intelligence models — snapshots, commentary, forecasts, preflight."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "report_type", "snapshot_date", name="uq_report_snapshot"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    key_metrics: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReportCommentary(Base):
    __tablename__ = "report_commentary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    report_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="generating")
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_findings: Mapped[list] = mapped_column(JSONB, server_default="[]")
    trend_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    forecast_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attention_items: Mapped[list] = mapped_column(JSONB, server_default="[]")
    comparison_periods_used: Mapped[int] = mapped_column(Integer, server_default="0")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReportForecast(Base):
    __tablename__ = "report_forecasts"
    __table_args__ = (UniqueConstraint("tenant_id", "forecast_type", "generated_date", name="uq_report_forecast"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    forecast_type: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_points: Mapped[int] = mapped_column(Integer, nullable=False)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    forecast_periods: Mapped[list] = mapped_column(JSONB, server_default="[]")
    trend_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    trend_rate_monthly: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    milestone_projections: Mapped[list] = mapped_column(JSONB, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditPreflightResult(Base):
    __tablename__ = "audit_preflight_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    audit_package_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="running")
    blocking_issues: Mapped[list] = mapped_column(JSONB, server_default="[]")
    warning_issues: Mapped[list] = mapped_column(JSONB, server_default="[]")
    passed_checks: Mapped[list] = mapped_column(JSONB, server_default="[]")
    override_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
