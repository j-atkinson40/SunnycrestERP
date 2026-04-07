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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceListItem(Base):
    """A single product row within a price list version."""

    __tablename__ = "price_list_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("price_list_versions.id"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    contractor_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    homeowner_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    previous_standard_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    previous_contractor_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    previous_homeowner_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), default="each")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    version = relationship("PriceListVersion", back_populates="items")
