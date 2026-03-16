import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Delivery(Base):
    """A single delivery request — may be linked to a sales order."""

    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    delivery_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # funeral_vault, precast, redi_rock
    order_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    delivery_lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    required_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # pending, scheduled, in_transit, arrived, setup, completed, cancelled, failed
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal"
    )  # low, normal, high, urgent
    type_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_lbs: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Carrier fields (for third-party delivery)
    carrier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("carriers.id"), nullable=True
    )
    carrier_tracking_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company = relationship("Company")
    customer = relationship("Customer")
    carrier = relationship("Carrier")
    stops = relationship("DeliveryStop", back_populates="delivery")
    events = relationship("DeliveryEvent", back_populates="delivery", order_by="DeliveryEvent.created_at")
    media = relationship("DeliveryMedia", back_populates="delivery")
