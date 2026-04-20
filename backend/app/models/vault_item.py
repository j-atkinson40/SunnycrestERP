import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VaultItem(Base):
    """A single item within a vault — document, event, communication, etc."""

    __tablename__ = "vault_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    vault_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vaults.id"), nullable=False, index=True
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Type discriminator
    item_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # document | event | communication | reminder | order | quote | case | contact | asset | compliance_item | production_record

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Document fields
    r2_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # delivery_confirmation | mold_config | batch_record | qc_photo | training_completion | training_material | inspection_cert | repair_record | asset_photo | asset_purchase | po | po_confirmation | coi | vendor_contract | payment_confirmation

    # Calendar/event fields
    event_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    event_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    event_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )  # delivery | route | driver_assignment | production_pour | production_strip | work_order | safety_training | compliance_expiry | maintenance
    event_type_sub: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # Sub-type for compliance: cdl | dot | hut | osha_300a | equipment_inspection | forklift_cert | npca
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # RRULE standard

    # Notification settings
    notify_recipients: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # list of user IDs
    notify_before_minutes: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # e.g. [1440, 60]

    # Visibility and sharing
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, default="internal"
    )  # private | internal | shared | public
    shared_with_company_ids: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # Cross-tenant sharing

    # Hierarchy
    parent_item_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("vault_items.id"), nullable=True
    )
    related_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )  # case | order | employee | asset | production_record
    related_entity_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active"
    )  # active | completed | cancelled | expired
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="system_generated"
    )  # system_generated | user_upload | agent_created | migrated | calendar_sync
    source_entity_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )  # ID of the source record (e.g. delivery.id) for back-reference.
    # Widened from 36 → 128 in r32 to fit semantic seed keys like
    # `saved_view_seed:{role_slug}:{template_id}` — UUID-shaped
    # values still fit.

    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Flexible metadata — domain-specific fields per item_type
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

    # Location
    location_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("locations.id"), nullable=True
    )

    # Relationships
    vault = relationship("Vault", back_populates="items")
    company = relationship("Company")
    parent_item = relationship("VaultItem", remote_side="VaultItem.id")
    creator = relationship("User", foreign_keys=[created_by])
    location = relationship("Location")
