"""Cross-system intelligence models — health scores, insights, seasonal readiness."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FinancialHealthScore(Base):
    __tablename__ = "financial_health_scores"
    __table_args__ = (UniqueConstraint("tenant_id", "score_date", name="uq_health_score_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    score_date: Mapped[date] = mapped_column(Date, nullable=False)
    overall_grade: Mapped[str] = mapped_column(String(2), nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    # Dimensions
    ar_health_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    ar_health_grade: Mapped[str | None] = mapped_column(String(2))
    ap_discipline_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    ap_discipline_grade: Mapped[str | None] = mapped_column(String(2))
    cash_position_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    cash_position_grade: Mapped[str | None] = mapped_column(String(2))
    operational_integrity_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    operational_integrity_grade: Mapped[str | None] = mapped_column(String(2))
    growth_trajectory_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    growth_trajectory_grade: Mapped[str | None] = mapped_column(String(2))
    weights: Mapped[dict] = mapped_column(JSONB, server_default='{"ar_health":0.25,"ap_discipline":0.20,"cash_position":0.20,"operational_integrity":0.20,"growth_trajectory":0.15}')
    top_positive_factors: Mapped[list] = mapped_column(JSONB, server_default="[]")
    top_negative_factors: Mapped[list] = mapped_column(JSONB, server_default="[]")
    prior_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    score_change: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    trend_7_day: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    calculation_inputs: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CrossSystemInsight(Base):
    __tablename__ = "cross_system_insights"
    __table_args__ = (UniqueConstraint("tenant_id", "insight_key", "primary_entity_id", name="uq_cross_insight"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    insight_key: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_entity_type: Mapped[str | None] = mapped_column(String(30))
    primary_entity_id: Mapped[str | None] = mapped_column(String(36))
    connected_systems: Mapped[list] = mapped_column(JSONB, server_default="[]")
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    primary_action_label: Mapped[str | None] = mapped_column(Text)
    primary_action_url: Mapped[str | None] = mapped_column(Text)
    secondary_action_label: Mapped[str | None] = mapped_column(Text)
    secondary_action_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    auto_resolved: Mapped[bool] = mapped_column(Boolean, server_default="false")
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SeasonalReadinessReport(Base):
    __tablename__ = "seasonal_readiness_reports"
    __table_args__ = (UniqueConstraint("tenant_id", "season", "season_year", name="uq_seasonal_report"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    readiness_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    readiness_grade: Mapped[str | None] = mapped_column(String(2))
    financial_readiness: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    operational_readiness: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    customer_readiness: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    inventory_readiness: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    ready_items: Mapped[list] = mapped_column(JSONB, server_default="[]")
    action_items: Mapped[list] = mapped_column(JSONB, server_default="[]")
    executive_summary: Mapped[str | None] = mapped_column(Text)
