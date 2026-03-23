"""AP settings per tenant."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class APSettings(Base):
    __tablename__ = "ap_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)
    default_payment_terms: Mapped[str] = mapped_column(String(50), server_default="Net 30")
    default_expense_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bill_approval_required: Mapped[bool] = mapped_column(Boolean, server_default="false")
    bill_approval_threshold: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    quickbooks_ap_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quickbooks_default_expense_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
