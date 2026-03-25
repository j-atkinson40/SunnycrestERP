"""Delivery intelligence models — driver profiles, capacity blocks, forecasts, conflicts."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    funeral_certified: Mapped[bool] = mapped_column(Boolean, server_default="true")
    funeral_daily_rough_capacity: Mapped[int] = mapped_column(Integer, server_default="2")
    can_deliver_wastewater: Mapped[bool] = mapped_column(Boolean, server_default="false")
    can_deliver_redi_rock: Mapped[bool] = mapped_column(Boolean, server_default="false")
    can_deliver_rosetta: Mapped[bool] = mapped_column(Boolean, server_default="false")
    can_deliver_vault: Mapped[bool] = mapped_column(Boolean, server_default="true")
    default_working_days: Mapped[list] = mapped_column(ARRAY(Integer), server_default="{1,2,3,4,5}")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    employee = relationship("User", foreign_keys=[employee_id])


class DeliveryCapacityBlock(Base):
    __tablename__ = "delivery_capacity_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    block_type: Mapped[str] = mapped_column(String(20), nullable=False)
    blocked_product_types: Mapped[list] = mapped_column(ARRAY(String(20)), nullable=False)
    driver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("driver_profiles.id"), nullable=True)
    block_start: Mapped[date] = mapped_column(Date, nullable=False)
    block_end: Mapped[date] = mapped_column(Date, nullable=False)
    applies_to_days: Mapped[list | None] = mapped_column(ARRAY(Integer), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text)
    suggested_by_agent: Mapped[bool] = mapped_column(Boolean, server_default="false")
    suggestion_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    confirmed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overridden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    overridden_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DeliveryDemandForecast(Base):
    __tablename__ = "delivery_demand_forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    funeral_demand_low: Mapped[int] = mapped_column(Integer, nullable=False)
    funeral_demand_high: Mapped[int] = mapped_column(Integer, nullable=False)
    funeral_demand_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    confirmed_funerals: Mapped[int] = mapped_column(Integer, server_default="0")
    portal_activity_signal: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    historical_pattern_low: Mapped[int | None] = mapped_column(Integer)
    historical_pattern_high: Mapped[int | None] = mapped_column(Integer)
    total_funeral_drivers: Mapped[int | None] = mapped_column(Integer)
    predicted_available_after_funerals_low: Mapped[int | None] = mapped_column(Integer)
    predicted_available_after_funerals_high: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    recommend_block: Mapped[bool] = mapped_column(Boolean, server_default="false")
    recommend_block_reason: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DeliveryConflictLog(Base):
    __tablename__ = "delivery_conflict_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(200))
    conflict_type: Mapped[str] = mapped_column(String(30), nullable=False)
    days_until_delivery: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    confirmed_funerals_that_day: Mapped[int | None] = mapped_column(Integer)
    predicted_funeral_range: Mapped[str | None] = mapped_column(String(20))
    available_driver_estimate: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alert_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
