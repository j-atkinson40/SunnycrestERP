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

    # Invoice / confirmation workflow
    require_driver_status_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # False = system auto-confirms delivery at 6 PM batch; True = require driver to mark delivered

    # Driver portal visibility
    show_en_route_button: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_exception_button: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_delivered_button: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_equipment_checklist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_funeral_home_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_cemetery_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_get_directions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_call_office_button: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Personalization scheduling gate
    require_personalization_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Carrier toggles
    sms_carrier_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carrier_portal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Limits
    max_stops_per_route: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_delivery_window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Phase 4.3.3 (r57) — tenant default driver start time.
    #
    # Default start time for weekday deliveries. Weekend deliveries
    # (Saturday especially) typically specify explicit start times
    # per delivery due to overtime rules. NULL
    # `delivery.driver_start_time` = use this default. The
    # QuickEditDialog's "Use default" toggle clears the per-delivery
    # value back to NULL so this default takes over.
    #
    # Format: 'HH:MM' (24-hour, tenant-local). Stored as TEXT (not
    # TIME) because the value is interpreted as tenant-local wall
    # clock at dispatch time, not as a UTC instant.
    default_driver_start_time: Mapped[str] = mapped_column(
        String(5), nullable=False, default="07:00", server_default="07:00"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company = relationship("Company")
