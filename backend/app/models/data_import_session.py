"""DataImportSession — tracks data import sessions for historical data migration."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DataImportSession(Base):
    __tablename__ = "import_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    matched_records: Mapped[int] = mapped_column(Integer, default=0)
    unmatched_records: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, default=0)
    imported_records: Mapped[int] = mapped_column(Integer, default=0)
    skipped_records: Mapped[int] = mapped_column(Integer, default=0)
    date_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    column_mapping: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    product_matches: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    customer_matches: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_log: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
