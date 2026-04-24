import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Delivery(Base):
    """A single delivery request — may be linked to a sales order.

    Phase 4.3 (r56) ancillary three-state + helper model:
      - ``primary_assignee_id`` (FK users.id): the person assigned to
        deliver this. Domain-broadened from "driver" — any tenant
        user is eligible (office staff occasionally delivers when
        drivers are unavailable). Renamed from ``assigned_driver_id``
        in r56; the old column stored ``drivers.id`` values without
        a FK constraint; the new column stores ``users.id`` values
        with a real FK. Portal-only Drivers (Phase 8e.2 with
        ``portal_user_id`` set but ``employee_id=NULL``) currently
        cannot be assigned via this FK — post-September follow-up.
      - ``attached_to_delivery_id`` (self-ref FK): for ancillary
        deliveries, points at the primary kanban Delivery this is
        physically paired with. Three ancillary states:
          · pool: ``attached_to_delivery_id=NULL + primary_assignee_id=NULL + requested_date=NULL``
          · standalone: ``attached_to_delivery_id=NULL + primary_assignee_id + requested_date set``
          · attached: ``attached_to_delivery_id`` set; driver/date inherit from parent
      - ``helper_user_id`` (FK users.id): optional second person
        accompanying the primary assignee. Shown as icon+tooltip in
        the card status row.
      - ``driver_start_time`` (TIME): per-delivery start-of-day
        target for the primary assignee. Not the ETA; a scheduling
        hint for route planning.
    """

    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    delivery_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # configurable per tenant via delivery_type_definitions
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

    # Ancillary order fields
    scheduling_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )  # 'kanban' | 'ancillary' — NULL treated as kanban
    ancillary_fulfillment_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True, index=True
    )  # unassigned, awaiting_pickup, assigned_to_driver, completed
    # Phase 4.3 (r56): renamed from `assigned_driver_id`, now FK to
    # `users.id` (was bare String(36), no FK). Represents the primary
    # deliverer — typically a driver-role user, but any tenant user
    # is eligible. See class docstring for rationale + portal-driver
    # follow-up note.
    primary_assignee_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Phase 4.3 (r56): optional second person accompanying the
    # primary assignee. Icon+tooltip in card status row.
    helper_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Phase 4.3 (r56): self-referential FK. When set, this delivery
    # is physically paired with another kanban delivery (same stop).
    # When NULL + primary_assignee_id set = standalone; when
    # NULL + primary_assignee_id NULL = pool.
    attached_to_delivery_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("deliveries.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Phase 4.3 (r56): per-delivery start-of-day target. Route
    # planning hint for the primary assignee — not ETA.
    driver_start_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )
    pickup_expected_by: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pickup_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pickup_confirmed_by: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    ancillary_is_floating: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=False
    )  # True = floating order (no hard delivery date)
    ancillary_soft_target_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )  # Optional soft target for floating orders

    # Direct ship fields
    direct_ship_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True, index=True
    )  # pending, ordered_from_wilbert, shipped, done
    wilbert_order_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    direct_ship_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    marked_shipped_by: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )

    # Location
    origin_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id"), nullable=True
    )

    # Dispatch quick-edit field (Phase B Session 1 / 3.1).
    # Three states: 'unknown' | 'yes' | 'no'. NOT NULL default 'unknown'
    # per Phase 3.1 operational feedback — every delivery has a hole-dug
    # state; the question is whether the dispatcher has confirmed it.
    # Migration r50_dispatch_hole_dug_default backfilled NULLs → 'unknown'.
    hole_dug_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="unknown"
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
    origin_location = relationship("Location")
    stops = relationship("DeliveryStop", back_populates="delivery")
    events = relationship("DeliveryEvent", back_populates="delivery", order_by="DeliveryEvent.created_at")
    media = relationship("DeliveryMedia", back_populates="delivery")
    # Phase 4.3 (r56) user relationships + self-ref. Explicit
    # foreign_keys to disambiguate (primary_assignee + helper both
    # target users.id; attached_to_delivery is self-ref).
    primary_assignee = relationship(
        "User", foreign_keys=[primary_assignee_id]
    )
    helper = relationship("User", foreign_keys=[helper_user_id])
    attached_to_delivery = relationship(
        "Delivery", foreign_keys=[attached_to_delivery_id], remote_side=[id]
    )
