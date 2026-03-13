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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    po_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=Decimal("0.000")
    )
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships ---
    purchase_order = relationship("PurchaseOrder", back_populates="lines")
    product = relationship("Product")
