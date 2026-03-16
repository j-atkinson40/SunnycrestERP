import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliveryMedia(Base):
    """Photo, signature, or weight ticket attached to a delivery."""

    __tablename__ = "delivery_media"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    delivery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deliveries.id"), nullable=False, index=True
    )
    event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("delivery_events.id"), nullable=True
    )
    media_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # photo, signature, weight_ticket
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    delivery = relationship("Delivery", back_populates="media")
    event = relationship("DeliveryEvent")
