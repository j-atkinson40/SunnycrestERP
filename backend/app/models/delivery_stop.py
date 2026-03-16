import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliveryStop(Base):
    """A single stop on a delivery route."""

    __tablename__ = "delivery_stops"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    route_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("delivery_routes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    delivery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deliveries.id"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_departure: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_departure: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # pending, en_route, arrived, completed, skipped
    driver_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    route = relationship("DeliveryRoute", back_populates="stops")
    delivery = relationship("Delivery", back_populates="stops")
