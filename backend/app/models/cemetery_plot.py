"""Cemetery plot + map config models (FH-1b)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CemeteryPlot(Base):
    __tablename__ = "cemetery_plots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    row: Mapped[str | None] = mapped_column(String(50), nullable=True)
    number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plot_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plot_type: Mapped[str] = mapped_column(String(50), default="single")
    status: Mapped[str] = mapped_column(String(50), default="available")
    map_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    opening_closing_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reserved_for_case_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reserved_by_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CemeteryMapConfig(Base):
    __tablename__ = "cemetery_map_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)
    map_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    map_width_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_height_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    sections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    legend: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
