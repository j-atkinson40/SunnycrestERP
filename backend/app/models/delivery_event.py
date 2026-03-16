import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliveryEvent(Base):
    """Timeline event for a delivery — arrival, departure, photo, issue, etc."""

    __tablename__ = "delivery_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    delivery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deliveries.id"), nullable=False, index=True
    )
    route_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("delivery_routes.id"), nullable=True
    )
    driver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drivers.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # dispatched, en_route, arrived, setup_start, setup_complete, photo, signature, departed, completed, issue
    lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default="driver"
    )  # driver, dispatch_manual, carrier_sms, system

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    delivery = relationship("Delivery", back_populates="events")
    driver = relationship("Driver")
