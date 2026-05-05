"""Calendar Primitive entity models — Phase W-4b Layer 1 Step 1.

All 9 entities for the Calendar Primitive (BRIDGEABLE_MASTER §3.26.16)
live in this single module. They share enough relationship topology
that splitting per-table would fragment the conceptual unit; future
phases may split if the file grows past comfort. Mirrors the
``email_primitive.py`` consolidation pattern verbatim.

**Architectural separation reminder:** these models implement the
*canonical Calendar primitive* (§3.26.16) — provider abstraction +
threaded calendar/account/sync infrastructure for inbound + outbound +
cross-tenant joint scheduling. The platform already has the **Vault
iCal feed** at ``GET /api/v1/vault/calendar.ics`` that serializes
VaultItems with event_type to one-way iCalendar text for external
calendar clients. The two surfaces coexist per CLAUDE.md
coexist-with-legacy discipline — different architectural concerns:

  - Existing (Vault): one-way iCal export (operator subscribes phone
    calendar to their token-protected feed URL); read-only from
    external clients' perspective; no provider abstraction; no
    threaded sync; no attendee modeling; no cross-tenant pairing.
  - This module (W-4b §3.26.16): bidirectional sync with provider
    accounts (Google Calendar, Microsoft 365, Bridgeable-native
    local); attendees + responses; recurrence engine; cross-tenant
    bilateral joint events; magic-link contextual surface for
    external participants.

**Cross-tenant masking inheritance hooks** are present on every
relationship that crosses a tenant boundary (the
``cross_tenant_event_pairing`` association in particular) — full
masking implementation defers to subsequent steps per §3.25.x
discipline. The hooks live as relationship+helper-method placeholders
that callers consult before reading sensitive fields.

**Canonical entity catalog per §3.26.16.2:**

Primary (3 entities):
  1. CalendarEvent              — event canonical entity
  2. CalendarEventAttendee      — attendee participation + response
  3. CalendarAccount            — per-tenant account configuration

Supporting (4 entities):
  4. CalendarAccountAccess      — per-user-per-account access grant
  5. CalendarEventInstanceOverride
                                — RFC 5545 modified/cancelled instance
                                  shadowing
  6. CalendarEventReminder      — per-attendee reminder configuration
                                  with deduplication discipline
  7. CalendarEventLinkage       — polymorphic linkage to Bridgeable
                                  entities (Quote in canonical catalog)

Cross-tenant + audit (2 entities):
  8. CrossTenantEventPairing    — paired-event junction across tenants
  9. CalendarAuditLog           — per-tenant calendar-action audit log
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Vocabulary tuples (mirror migration CHECK constraints) ───────────
ACCOUNT_TYPES = ("shared", "personal")

# Per Q3 architectural decision: CalDAV omitted entirely from Step 1
# package per canonical deferral (§3.26.16.4 + §3.26.7.5). When concrete
# operator signal warrants, add ``caldav.py`` provider as separate
# scoped session — easier to add a provider than maintain unused stub.
PROVIDER_TYPES = ("google_calendar", "msgraph", "local")

ACCESS_LEVELS = ("read", "read_write", "admin")
EVENT_STATUSES = ("tentative", "confirmed", "cancelled")
TRANSPARENCY_VALUES = ("opaque", "transparent")
ATTENDEE_ROLES = (
    "organizer",
    "required_attendee",
    "optional_attendee",
    "chair",
    "non_participant",
)
RESPONSE_STATUSES = (
    "needs_action",
    "accepted",
    "declined",
    "tentative",
    "delegated",
)
REMINDER_SURFACES = (
    "provider_default",
    "bridgeable_pulse",
    "bridgeable_email",
    "bridgeable_sms",
)
LINKAGE_SOURCES = (
    "manual_pre_link",
    "manual_post_link",
    "intelligence_inferred",
)
# Step 2 vocabulary tuples
SYNC_STATUSES = ("pending", "syncing", "synced", "error")
BACKFILL_STATUSES = ("not_started", "in_progress", "completed", "error")
CREDENTIAL_OPS = (
    "oauth_complete",
    "refresh",
    "refresh_failed",
    "revoke",
)


# ─────────────────────────────────────────────────────────────────────
# 1. CalendarAccount — per-tenant calendar account configuration
# ─────────────────────────────────────────────────────────────────────


class CalendarAccount(Base):
    __tablename__ = "calendar_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('shared', 'personal')",
            name="ck_calendar_accounts_account_type",
        ),
        CheckConstraint(
            "provider_type IN ('google_calendar', 'msgraph', 'local')",
            name="ck_calendar_accounts_provider_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="shared"
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # provider_config holds provider-specific config + (in Step 2)
    # cached subscription handles. Tokens stored encrypted under
    # ``encrypted_credentials`` per §3.26.16.2 — Step 2 wires the
    # encryption layer.
    provider_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Step 2 — encrypted credential storage. Fernet-encrypted JSON blob
    # containing access_token / refresh_token / token_expiry (OAuth).
    # NULL until first successful OAuth/credential capture. Local
    # provider never populates this (no transport).
    encrypted_credentials: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Step 2 — token expiry (denormalized for fast refresh scheduling
    # without decrypting the credential blob).
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Step 2 — credential lifecycle (denormalized for status indicator
    # on CalendarAccountsPage; full audit trail in calendar_audit_log).
    last_credential_op: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    last_credential_op_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Step 2 — asymmetric backfill window per canonical §3.26.16.4
    # ("last 90 days + next 365 days"). Diverges from Email r64's
    # symmetric backfill_days; tenant admin configurable per account.
    backfill_window_past_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90
    )
    backfill_window_future_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365
    )
    backfill_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_started"
    )
    backfill_progress_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    backfill_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    backfill_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outbound_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # IANA timezone identifier — drives default event_timezone for
    # events created against this account.
    default_event_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/New_York"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    access_grants: Mapped[list["CalendarAccountAccess"]] = relationship(
        "CalendarAccountAccess",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["CalendarEvent"]] = relationship(
        "CalendarEvent",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    sync_state: Mapped["CalendarAccountSyncState | None"] = relationship(
        "CalendarAccountSyncState",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
# 2. CalendarAccountAccess — per-user-per-account access grant
# ─────────────────────────────────────────────────────────────────────


class CalendarAccountAccess(Base):
    __tablename__ = "calendar_account_access"
    __table_args__ = (
        CheckConstraint(
            "access_level IN ('read', 'read_write', 'admin')",
            name="ck_calendar_account_access_level",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    access_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="read"
    )
    granted_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    account: Mapped["CalendarAccount"] = relationship(
        "CalendarAccount", back_populates="access_grants"
    )
    user = relationship("User", foreign_keys=[user_id])


# ─────────────────────────────────────────────────────────────────────
# 3. CalendarEvent — the event canonical entity
# ─────────────────────────────────────────────────────────────────────


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('tentative', 'confirmed', 'cancelled')",
            name="ck_calendar_events_status",
        ),
        CheckConstraint(
            "transparency IN ('opaque', 'transparent')",
            name="ck_calendar_events_transparency",
        ),
        CheckConstraint(
            "end_at >= start_at",
            name="ck_calendar_events_time_order",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Provider-side identifier; nullable for Bridgeable-native events
    # (local provider) and pre-provider-sync.
    provider_event_id: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_all_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # IANA timezone — distinct from start_at's tz; preserved verbatim
    # from RFC 5545 DTSTART;TZID per §3.26.16.2.
    event_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # RFC 5545 RRULE string — nullable for non-recurring. Step 2 wires
    # the canonical recurrence engine; Step 1 stores the string verbatim.
    recurrence_rule: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    # Self-FK — populated only on instance-override rows; null on master
    # event + non-recurring.
    recurrence_master_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    recurrence_instance_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="confirmed"
    )
    transparency: Mapped[str] = mapped_column(
        String(16), nullable=False, default="opaque"
    )
    is_cross_tenant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # Step 3 — state-change provenance per §3.26.16.18.
    # generation_source canonical values: "manual" (default semantics
    # for NULL) | "state_change" (drafted from canonical 7-mapping per
    # §3.26.16.18) | "intelligence_inferred" (post-Step-5 reserved).
    generation_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    generation_entity_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    generation_entity_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    # Step 4 — operational-action affordance payload per §3.26.16.17.
    # Mirrors EmailMessage.message_payload shape (Email primitive
    # parallel per substrate consolidation discipline). Actions live
    # at ``action_payload['actions'][idx]`` with canonical shape:
    # ``{action_type, action_target_type, action_target_id,
    # action_metadata, action_status, action_completed_at,
    # action_completed_by, action_completion_metadata}``.
    # Empty dict default for events without actions.
    action_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    account: Mapped["CalendarAccount"] = relationship(
        "CalendarAccount", back_populates="events"
    )
    attendees: Mapped[list["CalendarEventAttendee"]] = relationship(
        "CalendarEventAttendee",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    linkages: Mapped[list["CalendarEventLinkage"]] = relationship(
        "CalendarEventLinkage",
        back_populates="event",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
# 4. CalendarEventAttendee — per-event-per-attendee status + role
# ─────────────────────────────────────────────────────────────────────


class CalendarEventAttendee(Base):
    __tablename__ = "calendar_event_attendees"
    __table_args__ = (
        CheckConstraint(
            "role IN ('organizer', 'required_attendee', 'optional_attendee', 'chair', 'non_participant')",
            name="ck_calendar_event_attendees_role",
        ),
        CheckConstraint(
            "response_status IN ('needs_action', 'accepted', 'declined', 'tentative', 'delegated')",
            name="ck_calendar_event_attendees_response_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_company_entity_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="required_attendee"
    )
    response_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="needs_action"
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    event: Mapped["CalendarEvent"] = relationship(
        "CalendarEvent", back_populates="attendees"
    )
    reminders: Mapped[list["CalendarEventReminder"]] = relationship(
        "CalendarEventReminder",
        back_populates="attendee",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
# 5. CalendarEventInstanceOverride — RFC 5545 modified/cancelled
#    instance shadowing
# ─────────────────────────────────────────────────────────────────────


class CalendarEventInstanceOverride(Base):
    __tablename__ = "calendar_event_instance_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    master_event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    recurrence_instance_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_cancelled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # When is_cancelled=False, override_event_id points at the modified
    # instance event row (with recurrence_master_event_id =
    # master_event_id) so RFC 5545 EXDATE+modified-instance shadowing
    # applies correctly.
    override_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships — explicit FK disambiguation because both columns
    # reference calendar_events.
    master_event = relationship(
        "CalendarEvent", foreign_keys=[master_event_id]
    )
    override_event = relationship(
        "CalendarEvent", foreign_keys=[override_event_id]
    )


# ─────────────────────────────────────────────────────────────────────
# 6. CalendarEventReminder — per-attendee reminder configuration with
#    deduplication discipline
# ─────────────────────────────────────────────────────────────────────


class CalendarEventReminder(Base):
    __tablename__ = "calendar_event_reminders"
    __table_args__ = (
        CheckConstraint(
            "surface IN ('provider_default', 'bridgeable_pulse', 'bridgeable_email', 'bridgeable_sms')",
            name="ck_calendar_event_reminders_surface",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    attendee_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_event_attendees.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    minutes_before_start: Mapped[int] = mapped_column(Integer, nullable=False)
    # provider_default canonical default; bridgeable_* are operator opt-in
    # per the deduplication discipline in §3.26.16.2.
    surface: Mapped[str] = mapped_column(
        String(32), nullable=False, default="provider_default"
    )
    fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    attendee: Mapped["CalendarEventAttendee"] = relationship(
        "CalendarEventAttendee", back_populates="reminders"
    )


# ─────────────────────────────────────────────────────────────────────
# 7. CalendarEventLinkage — polymorphic linkage to Bridgeable entities
# ─────────────────────────────────────────────────────────────────────


class CalendarEventLinkage(Base):
    __tablename__ = "calendar_event_linkages"
    __table_args__ = (
        CheckConstraint(
            "linkage_source IN ('manual_pre_link', 'manual_post_link', 'intelligence_inferred')",
            name="ck_calendar_event_linkages_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    linked_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    linkage_source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    linked_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    event: Mapped["CalendarEvent"] = relationship(
        "CalendarEvent", back_populates="linkages"
    )


# ─────────────────────────────────────────────────────────────────────
# 8. CrossTenantEventPairing — paired-event junction across tenants
# ─────────────────────────────────────────────────────────────────────


class CrossTenantEventPairing(Base):
    __tablename__ = "cross_tenant_event_pairing"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_a_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Step 4 (Q2 confirmed pre-build): nullable. Pending state = no
    # partner-side CalendarEvent row exists yet (created at accept).
    event_b_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    tenant_a_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    tenant_b_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    relationship_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("platform_tenant_relationships.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Step 4 (Q2 confirmed pre-build): nullable semantics.
    #   NULL       = pending bilateral acceptance
    #   timestamp  = finalized post-accept (paired)
    # Single semantic field; no parallel pairing_status discriminator.
    paired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships — explicit FK disambiguation.
    event_a = relationship("CalendarEvent", foreign_keys=[event_a_id])
    event_b = relationship("CalendarEvent", foreign_keys=[event_b_id])


# ─────────────────────────────────────────────────────────────────────
# 9. CalendarAuditLog — per-tenant calendar-action audit log
# ─────────────────────────────────────────────────────────────────────


class CalendarAuditLog(Base):
    __tablename__ = "calendar_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


# ─────────────────────────────────────────────────────────────────────
# 10. CalendarAccountSyncState — Step 2 sync state per canonical §3.26.16.4
# ─────────────────────────────────────────────────────────────────────


class CalendarAccountSyncState(Base):
    """Per-account sync state — one row per CalendarAccount.

    Mirrors ``email_account_sync_state`` shape with the canonical
    Email-r63-plus-r64 unified columns. Calendar Step 1 deferred this
    table; Step 2 ships it with full canonical shape in a single new
    table per Email r64 precedent.

    **Cursor management** — provider-agnostic via ``last_provider_cursor``
    JSONB. Per-provider shape:
      - Google Calendar: ``{"sync_token": "..."}``
      - MS Graph: ``{"delta_token": "https://graph.microsoft.com/...delta..."}``

    **Circuit breaker** — after 5 consecutive sync failures, sync_status
    flips to "error" and consecutive_error_count keeps tracking.

    **Sync mutex** — sync_in_progress=true prevents two sweeps from
    double-syncing the same account.
    """

    __tablename__ = "calendar_account_sync_state"
    __table_args__ = (
        CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'synced', 'error')",
            name="ck_calendar_sync_state_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calendar_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_provider_cursor: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    sync_in_progress: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    sync_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    sync_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Step 2 stubs subscription_expires_at + subscription_resource_id;
    # real subscription provisioning ships in Step 2.1.
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_resource_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    account: Mapped["CalendarAccount"] = relationship(
        "CalendarAccount", back_populates="sync_state"
    )
