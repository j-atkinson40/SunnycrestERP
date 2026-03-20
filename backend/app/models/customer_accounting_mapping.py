"""Customer-to-accounting-provider mapping model."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CustomerAccountingMapping(Base):
    __tablename__ = "customer_accounting_mappings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )

    # Provider-specific IDs
    qbo_customer_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    qbd_customer_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    sage_customer_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Match metadata
    match_method: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # auto_matched | manually_matched | created_by_sync
    match_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    matched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
