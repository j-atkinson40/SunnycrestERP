"""Historical order import models.

Two tables:
  historical_order_imports — one record per file upload / import session
  historical_orders        — one record per source row successfully parsed
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HistoricalOrderImport(Base):
    """Tracks a historical order import job and its results."""

    __tablename__ = "historical_order_imports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Status lifecycle: pending → mapping → preview → importing → complete / failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    source_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 'sunnycrest_green_sheet', 'generic_csv', 'excel', etc.
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Row counts
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)

    # Enrichment counts
    customers_created: Mapped[int] = mapped_column(Integer, default=0)
    customers_matched: Mapped[int] = mapped_column(Integer, default=0)
    cemeteries_created: Mapped[int] = mapped_column(Integer, default=0)
    cemeteries_matched: Mapped[int] = mapped_column(Integer, default=0)
    fh_cemetery_pairs_created: Mapped[int] = mapped_column(Integer, default=0)

    # Column mapping {"Firm": "funeral_home_name", ...}
    column_mapping: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    # Confidence per column {"Firm": 0.99, ...}
    mapping_confidence: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    # Structured results
    warnings: Mapped[list] = mapped_column(JSONB, server_default="[]")
    errors: Mapped[list] = mapped_column(JSONB, server_default="[]")
    # [{"product_name": ..., "equipment": ..., "order_count": ..., "pct_of_total": ..., "suggested_template_name": ...}]
    recommended_templates: Mapped[list] = mapped_column(JSONB, server_default="[]")

    # Cached file content for two-phase parse → run flow
    raw_csv_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    cutover_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initiated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    orders: Mapped[list["HistoricalOrder"]] = relationship(
        "HistoricalOrder", back_populates="import_record", lazy="dynamic"
    )


class HistoricalOrder(Base):
    """One row from a historical order CSV, resolved against platform records."""

    __tablename__ = "historical_orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("historical_order_imports.id"), nullable=False, index=True
    )

    # Resolved foreign keys (nullable if not matched)
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True, index=True
    )
    cemetery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cemeteries.id"), nullable=True, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )

    # Raw values preserved from source (never overwritten)
    raw_funeral_home: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_cemetery: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_product: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_equipment: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Parsed order fields
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    service_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    service_place_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    equipment_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Normalized equipment value from EQUIPMENT_MAPPING
    equipment_mapped: Mapped[str | None] = mapped_column(String(100), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    fulfillment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'cemetery' or 'funeral_home' (when vault is delivered to FH not grave)
    delivery_location_type: Mapped[str] = mapped_column(String(20), default="cemetery")

    is_spring_surcharge: Mapped[bool] = mapped_column(Boolean, default=False)
    order_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    csr_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_order_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Match quality scores
    funeral_home_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    cemetery_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    import_record: Mapped["HistoricalOrderImport"] = relationship(
        "HistoricalOrderImport", back_populates="orders"
    )
