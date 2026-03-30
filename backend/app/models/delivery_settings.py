import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliverySettings(Base):
    """Per-tenant delivery workflow configuration."""

    __tablename__ = "delivery_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, unique=True
    )
    preset: Mapped[str] = mapped_column(
        String(30), nullable=False, default="standard"
    )

    # Workflow toggles
    require_photo_on_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_signature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_weight_ticket: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_setup_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_departure_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_mileage_entry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_partial_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_driver_resequence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    track_gps: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Notification toggles
    notify_customer_on_dispatch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_customer_on_arrival: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_customer_on_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_connected_tenant_on_arrival: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_connected_tenant_on_setup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Feature toggles
    enable_driver_messaging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enable_delivery_portal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_create_delivery_from_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_invoice_on_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invoice_generation_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="end_of_day"
    )
    # 'manual' | 'end_of_day' | 'immediate'

    # Carrier toggles
    sms_carrier_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carrier_portal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Limits
    max_stops_per_route: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_delivery_window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company = relationship("Company")
