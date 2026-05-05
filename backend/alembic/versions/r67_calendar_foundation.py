"""Phase W-4b Layer 1 Calendar Step 1 — entity foundation.

Creates the foundational entity tables for the Calendar Primitive
(BRIDGEABLE_MASTER §3.26.16). Step 1 ships entities + provider
abstraction stubs + CalendarAccount UI; subsequent Steps 2-N (sync,
RRULE engine activation, outbound, free/busy substrate, cross-tenant
joint events, action tokens, cross-surface rendering, Workshop
integration, Intelligence integration) build atop this foundation.

Mirrors Email Step 1 (r63) precedent exactly:
  - 8 entity tables in atomic migration
  - Plus 1 audit log table per §3.26.16.8 (parallel to email_audit_log)
  - Cross-tenant pairing junction included; full bilateral-acceptance
    flow deferred to Step 4 (depends on platform_action_tokens
    substrate consolidation per §3.26.16.17 Phase B Q13 refinement)
  - Encrypted credentials column included on calendar_accounts but
    nullable; Step 2 wires real OAuth + token persistence

**Architectural separation reminder**: this primitive is distinct
from the existing Vault iCal feed at ``GET /api/v1/vault/calendar.ics``
which serializes VaultItems with event_type to RFC 5545 iCalendar
text. The two surfaces coexist per CLAUDE.md coexist-with-legacy
discipline; legacy Vault iCal feed continues to function for one-way
calendar export from Bridgeable to external clients (operator's
phone calendar subscribed via token). The canonical Calendar primitive
ships threaded calendar/account/sync/freebusy infrastructure for
inbound + outbound + cross-tenant joint scheduling — different
architectural concern.

**9 tables shipped this migration** (per §3.26.16.2 + §3.26.16.8):

Account layer:
  1. calendar_accounts            — per-tenant account config
                                    (shared/personal, provider_type,
                                    encrypted_credentials placeholder)
  2. calendar_account_access      — (account_id, user_id, access_level)
                                    junction

Event/attendee layer (per §3.26.16.2):
  3. calendar_events              — Event canonical entity with
                                    is_cross_tenant marker + RFC 5545
                                    fields (recurrence_rule, status,
                                    transparency, event_timezone)
  4. calendar_event_attendees     — Per-event-per-attendee status + role
  5. calendar_event_instance_overrides
                                  — RFC 5545 modified-instance +
                                    cancelled-instance shadowing
  6. calendar_event_reminders     — Per-attendee reminder configuration
                                    with deduplication discipline
                                    (canonical default provider_default)
  7. calendar_event_linkages      — Polymorphic linkage to Bridgeable
                                    entities (Quote in canonical
                                    catalog per §3.26.16.7)

Cross-tenant pairing (per §3.26.16.6):
  8. cross_tenant_event_pairing   — Paired-event junction across tenants
                                    (bilateral acceptance flow ships in
                                    Step 4 after platform_action_tokens
                                    substrate consolidation)

Audit (§3.26.16.8):
  9. calendar_audit_log           — Per-tenant calendar-action audit log

**Revisable scope discipline (Email r63 precedent):**
RRULE engine, free/busy substrate, real OAuth credentials, sync
activation, outbound flows, cross-tenant bilateral acceptance, and
cross-surface rendering all defer to subsequent steps. Step 1 is the
entity foundation only.

Revision ID: r67_calendar_foundation
Revises: r66_email_action_tokens
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r67_calendar_foundation"
down_revision = "r66_email_action_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. calendar_accounts ──────────────────────────────────────────
    op.create_table(
        "calendar_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_type",
            sa.String(16),
            nullable=False,
            server_default="shared",
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("primary_email_address", sa.String(320), nullable=False),
        # Per §3.26.16.4 + Q3 architectural decision: CalDAV omitted
        # entirely from Step 1. Provider catalog: gmail / msgraph / local.
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column(
            "provider_config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Per §3.26.16.2 — Step 2 wires real OAuth + token persistence
        # via Fernet under platform-wide CREDENTIAL_ENCRYPTION_KEY.
        # NULL until first successful credential capture.
        sa.Column("encrypted_credentials", sa.Text, nullable=True),
        sa.Column(
            "outbound_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        # IANA timezone identifier — drives default event_timezone for
        # events created against this account.
        sa.Column(
            "default_event_timezone",
            sa.String(64),
            nullable=False,
            server_default="America/New_York",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "account_type IN ('shared', 'personal')",
            name="ck_calendar_accounts_account_type",
        ),
        sa.CheckConstraint(
            "provider_type IN ('google_calendar', 'msgraph', 'local')",
            name="ck_calendar_accounts_provider_type",
        ),
    )
    op.create_index(
        "ix_calendar_accounts_tenant",
        "calendar_accounts",
        ["tenant_id"],
    )
    op.create_index(
        "uq_calendar_accounts_tenant_email",
        "calendar_accounts",
        ["tenant_id", "primary_email_address"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # ── 2. calendar_account_access ────────────────────────────────────
    op.create_table(
        "calendar_account_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("calendar_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "access_level",
            sa.String(16),
            nullable=False,
            server_default="read",
        ),
        sa.Column(
            "granted_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "access_level IN ('read', 'read_write', 'admin')",
            name="ck_calendar_account_access_level",
        ),
    )
    op.create_index(
        "uq_calendar_account_access_active",
        "calendar_account_access",
        ["account_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_calendar_account_access_user",
        "calendar_account_access",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # ── 3. calendar_events ────────────────────────────────────────────
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("calendar_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Provider-side identifier; nullable for Bridgeable-native events
        # (local provider) and pre-provider-sync.
        sa.Column("provider_event_id", sa.String(512), nullable=True),
        sa.Column("subject", sa.String(998), nullable=True),
        sa.Column("description_text", sa.Text, nullable=True),
        sa.Column("description_html", sa.Text, nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_all_day",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        # IANA timezone — distinct from start_at's tz; preserved verbatim
        # from RFC 5545 DTSTART;TZID per §3.26.16.2.
        sa.Column("event_timezone", sa.String(64), nullable=True),
        # RFC 5545 RRULE string — nullable for non-recurring.
        # Step 2 wires the canonical recurrence engine that materializes
        # instances on demand; Step 1 stores the string verbatim.
        sa.Column("recurrence_rule", sa.String(1024), nullable=True),
        # Self-FK — populated only on instance-override rows; null on
        # master event + non-recurring.
        sa.Column(
            "recurrence_master_event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "recurrence_instance_start_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # RFC 5545 STATUS: tentative / confirmed / cancelled.
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="confirmed",
        ),
        # RFC 5545 TRANSP: opaque (default — counts toward free/busy)
        # / transparent (does not count toward free/busy).
        sa.Column(
            "transparency",
            sa.String(16),
            nullable=False,
            server_default="opaque",
        ),
        sa.Column(
            "is_cross_tenant",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('tentative', 'confirmed', 'cancelled')",
            name="ck_calendar_events_status",
        ),
        sa.CheckConstraint(
            "transparency IN ('opaque', 'transparent')",
            name="ck_calendar_events_transparency",
        ),
        # end_at >= start_at sanity (RFC 5545 DTEND >= DTSTART
        # except for all-day events where canonical equality is
        # also valid). Use >=, not >, to accept all-day same-day events.
        sa.CheckConstraint(
            "end_at >= start_at",
            name="ck_calendar_events_time_order",
        ),
    )
    op.create_index(
        "ix_calendar_events_tenant_start",
        "calendar_events",
        ["tenant_id", "start_at"],
    )
    op.create_index(
        "ix_calendar_events_account_start",
        "calendar_events",
        ["account_id", "start_at"],
    )
    op.create_index(
        "ix_calendar_events_provider_id",
        "calendar_events",
        ["account_id", "provider_event_id"],
        unique=True,
        postgresql_where=sa.text("provider_event_id IS NOT NULL"),
    )
    op.create_index(
        "ix_calendar_events_recurrence_master",
        "calendar_events",
        ["recurrence_master_event_id"],
        postgresql_where=sa.text("recurrence_master_event_id IS NOT NULL"),
    )
    op.create_index(
        "ix_calendar_events_cross_tenant",
        "calendar_events",
        ["tenant_id"],
        postgresql_where=sa.text("is_cross_tenant = true"),
    )

    # ── 4. calendar_event_attendees ───────────────────────────────────
    op.create_table(
        "calendar_event_attendees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column(
            "resolved_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_company_entity_id",
            sa.String(36),
            sa.ForeignKey("company_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "external_tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # RFC 5545 ROLE.
        sa.Column(
            "role",
            sa.String(32),
            nullable=False,
            server_default="required_attendee",
        ),
        # RFC 5545 PARTSTAT.
        sa.Column(
            "response_status",
            sa.String(16),
            nullable=False,
            server_default="needs_action",
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        # Comment from response — many providers surface a comment field
        # on accept/decline.
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column(
            "is_internal",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('organizer', 'required_attendee', 'optional_attendee', 'chair', 'non_participant')",
            name="ck_calendar_event_attendees_role",
        ),
        sa.CheckConstraint(
            "response_status IN ('needs_action', 'accepted', 'declined', 'tentative', 'delegated')",
            name="ck_calendar_event_attendees_response_status",
        ),
    )
    op.create_index(
        "ix_calendar_event_attendees_event",
        "calendar_event_attendees",
        ["event_id"],
    )
    op.create_index(
        "ix_calendar_event_attendees_email",
        "calendar_event_attendees",
        ["email_address"],
    )
    op.create_index(
        "uq_calendar_event_attendees_event_email",
        "calendar_event_attendees",
        ["event_id", "email_address"],
        unique=True,
    )

    # ── 5. calendar_event_instance_overrides ──────────────────────────
    # RFC 5545 modified-instance + cancelled-instance shadowing per
    # §3.26.16.2. When a recurring event has one instance modified or
    # cancelled, the override row shadows that one instance.
    op.create_table(
        "calendar_event_instance_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "master_event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recurrence_instance_start_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "is_cancelled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        # When is_cancelled=False, override_event_id points at the
        # modified-instance event row (carrying recurrence_master_event_id
        # = master_event_id so RFC 5545 EXDATE+modified-instance
        # shadowing applies correctly).
        sa.Column(
            "override_event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_calendar_event_instance_overrides_master_instance",
        "calendar_event_instance_overrides",
        ["master_event_id", "recurrence_instance_start_at"],
        unique=True,
    )
    op.create_index(
        "ix_calendar_event_instance_overrides_override",
        "calendar_event_instance_overrides",
        ["override_event_id"],
        postgresql_where=sa.text("override_event_id IS NOT NULL"),
    )

    # ── 6. calendar_event_reminders ───────────────────────────────────
    # Per-attendee reminder configuration with deduplication discipline
    # (per §3.26.16.2 Phase A refinement). Canonical default
    # provider_default prevents canonical-default-double-notification.
    op.create_table(
        "calendar_event_reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attendee_id",
            sa.String(36),
            sa.ForeignKey("calendar_event_attendees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("minutes_before_start", sa.Integer, nullable=False),
        # provider_default is canonical default; bridgeable_pulse |
        # bridgeable_email | bridgeable_sms are operator opt-in.
        sa.Column(
            "surface",
            sa.String(32),
            nullable=False,
            server_default="provider_default",
        ),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "surface IN ('provider_default', 'bridgeable_pulse', 'bridgeable_email', 'bridgeable_sms')",
            name="ck_calendar_event_reminders_surface",
        ),
    )
    op.create_index(
        "ix_calendar_event_reminders_attendee",
        "calendar_event_reminders",
        ["attendee_id"],
    )
    op.create_index(
        "ix_calendar_event_reminders_pending",
        "calendar_event_reminders",
        ["minutes_before_start"],
        postgresql_where=sa.text(
            "fired_at IS NULL AND surface != 'provider_default'"
        ),
    )

    # ── 7. calendar_event_linkages ────────────────────────────────────
    # Polymorphic linkage to Bridgeable entities per §3.26.16.7.
    # Mirrors email_thread_linkages shape verbatim.
    op.create_table(
        "calendar_event_linkages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("linked_entity_type", sa.String(64), nullable=False),
        sa.Column("linked_entity_id", sa.String(36), nullable=False),
        sa.Column(
            "linkage_source",
            sa.String(32),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "linked_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "linkage_source IN ('manual_pre_link', 'manual_post_link', 'intelligence_inferred')",
            name="ck_calendar_event_linkages_source",
        ),
    )
    op.create_index(
        "ix_calendar_event_linkages_event",
        "calendar_event_linkages",
        ["event_id"],
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )
    op.create_index(
        "ix_calendar_event_linkages_entity",
        "calendar_event_linkages",
        ["linked_entity_type", "linked_entity_id"],
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )
    op.create_index(
        "uq_calendar_event_linkages_active",
        "calendar_event_linkages",
        ["event_id", "linked_entity_type", "linked_entity_id"],
        unique=True,
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )

    # ── 8. cross_tenant_event_pairing ─────────────────────────────────
    # Per §3.26.16.6 — junction table for cross-tenant joint events.
    # Each tenant has its own copy under its own ownership; this junction
    # tracks which events pair across tenants. Bilateral acceptance flow
    # ships in Step 4 after platform_action_tokens substrate consolidation.
    op.create_table(
        "cross_tenant_event_pairing",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "event_a_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_b_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_a_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_b_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship_id",
            sa.String(36),
            sa.ForeignKey("platform_tenant_relationships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "paired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_cross_tenant_event_pairing",
        "cross_tenant_event_pairing",
        ["event_a_id", "event_b_id"],
        unique=True,
    )
    op.create_index(
        "ix_cross_tenant_event_pairing_b",
        "cross_tenant_event_pairing",
        ["event_b_id"],
    )

    # ── 9. calendar_audit_log ─────────────────────────────────────────
    # Per §3.26.16.8 — calendar primitive maintains its own audit channel
    # distinct from the general ``audit_logs`` table because calendar
    # events have calendar-specific shape (account_id linkage, provider
    # context). Subsequent steps may consolidate.
    op.create_table(
        "calendar_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("changes", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_calendar_audit_log_tenant_created",
        "calendar_audit_log",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_calendar_audit_log_entity",
        "calendar_audit_log",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    # Drop in reverse-FK order so dependent tables go first.
    op.drop_table("calendar_audit_log")
    op.drop_table("cross_tenant_event_pairing")
    op.drop_table("calendar_event_linkages")
    op.drop_table("calendar_event_reminders")
    op.drop_table("calendar_event_instance_overrides")
    op.drop_table("calendar_event_attendees")
    op.drop_table("calendar_events")
    op.drop_table("calendar_account_access")
    op.drop_table("calendar_accounts")
