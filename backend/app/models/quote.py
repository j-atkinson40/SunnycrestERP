import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Quote(Base):
    """Sales quote — can be converted to a sales order."""

    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # QTE-YYYY-####
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True, index=True
    )
    customer_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # For walk-in / quick quotes without a customer record
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft, sent, accepted, rejected, expired, converted

    quote_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expiry_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.00")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_to_order_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )

    # Order station fields
    product_line: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # wastewater, redi_rock, rosetta, funeral_vaults
    template_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )

    # Cemetery reference (for funeral vault orders)
    cemetery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cemeteries.id"), nullable=True, index=True
    )
    cemetery_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    permit_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    permit_jurisdiction: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    installation_address: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    installation_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    installation_state: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_charge: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Audit
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer")
    cemetery = relationship("Cemetery", foreign_keys=[cemetery_id])
    lines = relationship(
        "QuoteLine", back_populates="quote", order_by="QuoteLine.sort_order"
    )
    creator = relationship("User", foreign_keys=[created_by])


class QuoteLine(Base):
    __tablename__ = "quote_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotes.id"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("1")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Auto-add tracking (mirrors sales_order_lines)
    is_auto_added: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    auto_add_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    quote = relationship("Quote", back_populates="lines")
    product = relationship("Product")
