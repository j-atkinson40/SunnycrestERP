"""Generalized cross-tenant relationship for billing and supplier connections."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlatformTenantRelationship(Base):
    __tablename__ = "platform_tenant_relationships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "supplier_tenant_id", "relationship_type",
            name="uq_platform_tenant_rel",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    supplier_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)

    billing_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    billing_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_enabled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    connected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")

    legacy_fh_relationship_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Phase W-4b Calendar Step 3 — bilateral cross-tenant freebusy
    # consent state per §3.26.16.14 + Q1 Path A.
    # Canonical values: 'free_busy_only' (default, privacy-preserving;
    # returns busy/free + status only) | 'full_details' (bilateral
    # upgrade; additionally returns subject + location +
    # attendee_count_bucket per §3.26.16.6 anonymization granularity).
    calendar_freebusy_consent: Mapped[str] = mapped_column(
        String(16), server_default="free_busy_only", default="free_busy_only"
    )

    # Step 4.1 (Q3 confirmed pre-build): consent state metadata for
    # settings-page rendering ergonomics. NULL when consent has never
    # been changed (default-state rows). Stamped on first state flip
    # by ptr_consent_service request_upgrade / accept_upgrade /
    # revoke_upgrade.
    calendar_freebusy_consent_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    calendar_freebusy_consent_updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Personalization Studio implementation arc Step 1 — Step 0 Migration
    # r75 — column-per-capability discipline per Q4 canonical resolution.
    # Canonical 4-state machine stored DIRECTLY at column substrate per
    # Q4 canonical direction: default | pending_outbound | pending_inbound
    # | active. Each PTR row's column reflects the bilateral state from
    # THAT tenant's canonical perspective; state transitions update BOTH
    # PTR rows synchronously per dual-row canonical pattern. Enables
    # canonical cross-tenant DocumentShare grant of personalization
    # Generation Focus Document substrate per §2.5 portal-extension
    # foundation + §3.26.11.10 cross-tenant Focus consent canonical when
    # both sides at ``active`` (bilateral consent active state).
    #
    # **Canonical-substrate-shape distinction from Calendar Step 4.1**:
    # Calendar stores per-side intent (free_busy_only | full_details)
    # and resolves the bilateral 4-state machine at service-layer
    # resolver. Q4 canonical direction for personalization_studio
    # capability stores the canonical 4-state machine DIRECTLY at
    # column substrate. Per-capability state-machine storage shape may
    # differ canonically per capability — column-per-capability
    # discipline holds at substrate boundary while per-capability
    # state-machine semantics are canonical service-layer concerns.
    personalization_studio_cross_tenant_sharing_consent: Mapped[str] = mapped_column(
        String(32),
        server_default="default",
        default="default",
    )

    # Q3 canonical metadata columns parallel to Calendar Step 4.1
    # precedent — settings-page rendering ergonomics ("Last updated 3
    # days ago by Jane"). NULL when consent has never been changed
    # (default-state rows). Stamped on first state flip by
    # ptr_consent_service request_personalization_studio_consent /
    # accept_personalization_studio_consent /
    # revoke_personalization_studio_consent.
    personalization_studio_cross_tenant_sharing_consent_updated_at: Mapped[
        datetime | None
    ] = mapped_column(DateTime(timezone=True), nullable=True)
    personalization_studio_cross_tenant_sharing_consent_updated_by: Mapped[
        str | None
    ] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer_tenant = relationship("Company", foreign_keys=[tenant_id])
    supplier_tenant = relationship("Company", foreign_keys=[supplier_tenant_id])
