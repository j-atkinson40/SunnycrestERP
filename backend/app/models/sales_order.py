import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SalesOrder(Base):
    """Sales order — can be invoiced. Optionally originates from a quote."""

    __tablename__ = "sales_orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # SO-YYYY-####
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    quote_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("quotes.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft, confirmed, processing, shipped, completed, canceled

    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    required_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shipped_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Shipping address (defaults from customer)
    ship_to_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ship_to_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

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

    # Cemetery reference — hard FK for funeral orders
    cemetery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cemeteries.id"), nullable=True
    )

    # Order classification
    order_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'funeral' | 'retail' | 'wholesale' — used by end-of-day invoice batch
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The service/delivery date for this order (distinct from required_date timestamp)

    # Driver exception tracking (populated when delivery is completed with issues)
    driver_exceptions: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    has_driver_exception: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Delivery confirmation tracking
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_auto_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True = system marked delivered at 6 PM batch; False = driver explicitly confirmed
    delivered_by_driver_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Driver explicitly confirmed delivery (vs auto-confirmed by batch)
    driver_confirmed: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Order completion
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft inventory warning at order entry
    has_inventory_warning: Mapped[bool] = mapped_column(Boolean, server_default="false")
    inventory_warning_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Funeral home confirmation method (defaults from customer preference, can be overridden)
    confirmation_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Service details — set during order entry, shown on scheduling board
    service_location: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 'church', 'funeral_home', 'graveside', 'other'
    service_location_other: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    eta: Mapped[time | None] = mapped_column(Time, nullable=True)
    # Estimated cemetery arrival (procession ETA); null for graveside

    # Deceased name — shown on invoice/PDF when invoice settings enable it
    deceased_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Spring burial
    is_spring_burial: Mapped[bool] = mapped_column(Boolean, default=False)
    spring_burial_added_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    spring_burial_added_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    spring_burial_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    spring_burial_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    spring_burial_scheduled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

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
    quote = relationship("Quote")
    cemetery = relationship("Cemetery")
    lines = relationship(
        "SalesOrderLine",
        back_populates="sales_order",
        order_by="SalesOrderLine.sort_order",
    )
    invoices = relationship("Invoice", back_populates="sales_order")
    creator = relationship("User", foreign_keys=[created_by])


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sales_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("1")
    )
    quantity_shipped: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Auto-add tracking (for placer preference lines)
    is_auto_added: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    auto_add_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    sales_order = relationship("SalesOrder", back_populates="lines")
    product = relationship("Product")
