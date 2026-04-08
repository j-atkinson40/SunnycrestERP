"""DisintermentChargeType — per-tenant configurable line item template for disinterment quotes.

Configured once in settings, pre-loaded on every new disinterment quote.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DisintermentChargeType(Base):
    __tablename__ = "disinterment_charge_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    calculation_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # flat, per_mile, per_unit, hourly
    default_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )
    requires_input: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    input_label: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )  # e.g. 'Miles between cemeteries'
    is_hazard_pay: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    company = relationship("Company")
