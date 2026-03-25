"""Network intelligence models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NetworkAnalyticsSnapshot(Base):
    __tablename__ = "network_analytics_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_type", "snapshot_date", name="uq_network_snapshot"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    tenant_count_included: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NetworkCoverageGap(Base):
    __tablename__ = "network_coverage_gaps"
    __table_args__ = (UniqueConstraint("state", "county", "gap_type", name="uq_network_gap"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    county: Mapped[str] = mapped_column(String(100), nullable=False)
    gap_type: Mapped[str] = mapped_column(String(30), nullable=False)
    transfer_request_count: Mapped[int] = mapped_column(Integer, server_default="0")
    funeral_home_count: Mapped[int] = mapped_column(Integer, server_default="0")
    platform_licensee_count: Mapped[int] = mapped_column(Integer, server_default="0")
    nearest_licensee_miles: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    opportunity_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved: Mapped[bool] = mapped_column(Boolean, server_default="false")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class OnboardingPatternData(Base):
    __tablename__ = "onboarding_pattern_data"
    __table_args__ = (UniqueConstraint("tenant_type", "checklist_item_key", "snapshot_month", name="uq_onboarding_pattern"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_type: Mapped[str] = mapped_column(String(30), nullable=False)
    checklist_item_key: Mapped[str] = mapped_column(String(100), nullable=False)
    avg_days_to_complete: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    median_days_to_complete: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    completion_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    abandonment_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    common_abandonment_point: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avg_days_from_signup: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    tenant_count_sample: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False)


class NetworkConnectionSuggestion(Base):
    __tablename__ = "network_connection_suggestions"
    __table_args__ = (UniqueConstraint("tenant_id", "suggested_tenant_id", "connection_type", name="uq_connection_suggestion"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    suggested_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    connection_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
