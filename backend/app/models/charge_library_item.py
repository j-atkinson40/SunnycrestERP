"""Charge Library Item — fee/surcharge templates seeded per tenant."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChargeLibraryItem(Base):
    __tablename__ = "charge_library_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "charge_key", name="uq_charge_library_tenant_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    charge_key: Mapped[str] = mapped_column(String(100), nullable=False)
    charge_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    pricing_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="variable"
    )
    fixed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    per_mile_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    free_radius_miles: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    zone_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_min: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    guidance_max: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    variable_placeholder: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    auto_suggest: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_suggest_trigger: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    invoice_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tenant = relationship("Company", foreign_keys=[tenant_id])

    # ── Convenience JSON accessor ───────────────────────────────────────

    @property
    def zone_config_parsed(self) -> list[dict] | None:
        if not self.zone_config:
            return None
        return json.loads(self.zone_config)
