"""Behavioral analytics models — events, insights, feedback, profiles."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BehavioralEvent(Base):
    __tablename__ = "behavioral_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    event_category: Mapped[str] = mapped_column(String(30), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    secondary_entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    secondary_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    caused_by_event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("behavioral_events.id"), nullable=True)
    event_data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    actor_type: Mapped[str] = mapped_column(String(20), server_default="agent")
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    outcome_measured: Mapped[bool] = mapped_column(Boolean, server_default="false")
    outcome_measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BehavioralInsight(Base):
    __tablename__ = "behavioral_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    insight_type: Mapped[str] = mapped_column(String(60), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), server_default="tenant")
    scope_entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scope_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    action_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    first_surfaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    suppressed_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    generated_by_job: Mapped[str | None] = mapped_column(String(60), nullable=True)
    data_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class InsightFeedback(Base):
    __tablename__ = "insight_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    insight_id: Mapped[str] = mapped_column(String(36), ForeignKey("behavioral_insights.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_positive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EntityBehavioralProfile(Base):
    __tablename__ = "entity_behavioral_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", "entity_id", name="uq_entity_profile"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # Customer
    avg_days_to_pay: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    payment_consistency_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    discount_uptake_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    collections_response_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    preferred_contact_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finance_charge_forgiveness_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    relationship_health_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    relationship_health_trend: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_frequency_days: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    # Vendor
    on_time_delivery_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    invoice_accuracy_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    avg_price_variance_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    price_trend: Mapped[str | None] = mapped_column(String(10), nullable=True)
    discrepancy_resolution_days: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    # Flexible profile data from historical imports / behavioral analysis
    profile_data: Mapped[dict] = mapped_column(_JSONB, server_default="{}")
    last_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
