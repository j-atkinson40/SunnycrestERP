import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BalanceAdjustment(Base):
    __tablename__ = "balance_adjustments"
    __table_args__ = (
        Index("ix_balance_adj_customer", "customer_id"),
        Index("ix_balance_adj_company", "company_id"),
        Index("ix_balance_adj_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    adjustment_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "charge" or "payment"
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer")
    author = relationship("User", foreign_keys=[created_by])
