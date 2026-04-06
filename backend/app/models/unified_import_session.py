"""UnifiedImportSession — tracks multi-source onboarding import wizard state."""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UnifiedImportSession(Base):
    __tablename__ = "unified_import_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, unique=True, index=True
    )

    # Phase tracking
    phase: Mapped[str] = mapped_column(
        String(30), server_default="uploading"
    )  # uploading | processing | review | applying | complete | error

    # Source status
    accounting_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # qbo | sage | csv | skip
    accounting_status: Mapped[str] = mapped_column(
        String(20), server_default="pending"
    )  # pending | uploaded | processed | skipped

    order_history_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    cemetery_csv_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    funeral_home_csv_status: Mapped[str] = mapped_column(String(20), server_default="pending")

    # File references (store raw content for reprocessing)
    cemetery_csv_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    cemetery_csv_mapping: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    funeral_home_csv_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    funeral_home_csv_mapping: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Processing results
    processing_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Review state
    review_decisions: Mapped[dict] = mapped_column(JSONB, server_default=sa.text("'{}'::jsonb"))

    # Staging counts
    staging_customers_count: Mapped[int] = mapped_column(Integer, server_default="0")
    staging_cemeteries_count: Mapped[int] = mapped_column(Integer, server_default="0")
    staging_funeral_homes_count: Mapped[int] = mapped_column(Integer, server_default="0")
    staging_orders_count: Mapped[int] = mapped_column(Integer, server_default="0")

    # Apply results
    apply_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    staging_companies = relationship("ImportStagingCompany", back_populates="session", cascade="all, delete-orphan")
