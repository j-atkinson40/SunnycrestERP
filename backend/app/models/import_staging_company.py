"""ImportStagingCompany — staging table for companies during unified import."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportStagingCompany(Base):
    __tablename__ = "import_staging_companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("unified_import_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Source tracking
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # accounting | order_history | cemetery_csv | fh_csv
    source_row_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Normalized fields
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification signals
    suggested_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # funeral_home | cemetery | contractor | etc
    suggested_contractor_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    classification_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Cross-reference results
    matched_sources: Mapped[list] = mapped_column(JSONB, server_default="'[]'")
    cross_ref_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Cluster assignment
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    is_cluster_primary: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Review state
    review_status: Mapped[str] = mapped_column(
        String(20), server_default="pending"
    )  # pending | auto_applied | approved | rejected | modified
    reviewed_classification: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Sage/accounting identifiers for dedup
    sage_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Order history stats (populated during cross-ref)
    order_count: Mapped[int] = mapped_column(Integer, server_default="0")
    vault_order_count: Mapped[int] = mapped_column(Integer, server_default="0")
    appears_as_cemetery_count: Mapped[int] = mapped_column(Integer, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    session = relationship("UnifiedImportSession", back_populates="staging_companies")
