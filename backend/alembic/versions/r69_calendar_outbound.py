"""Phase W-4b Layer 1 Calendar Step 3 — outbound + iTIP + state-changes-generate-events.

Calendar Step 1 (r67) shipped the entity foundation; Calendar Step 2
(r68) shipped credentials + sync state + RRULE engine. Step 3 builds
on Step 2 substrate to ship outbound infrastructure + iTIP scheduling
+ free/busy substrate cross-tenant + state-changes-generate-events.

**4 column additions** (3 to calendar_events; 1 to platform_tenant_relationships):

State-change provenance per §3.26.16.18:
  1. ``calendar_events.generation_source`` String(32) nullable —
     canonical values: ``"manual"`` (default semantics for nullable;
     manually-created events) | ``"state_change"`` (drafted from a
     canonical 7-mapping per §3.26.16.18) | ``"intelligence_inferred"``
     (post-Step-5 Intelligence layer scope; reserved). NULL means
     manual creation pre-Step-3.
  2. ``calendar_events.generation_entity_type`` String(64) nullable —
     source operational entity type (e.g. ``"sales_order"`` /
     ``"fh_case"`` / ``"quote"`` / etc per canonical 7-mapping).
  3. ``calendar_events.generation_entity_id`` String(36) nullable —
     source operational entity id (deliberately not FK; references any
     of 7 entity types per canonical 7-mapping).

Cross-tenant freebusy consent state per §3.26.16.14 + Q1 Path A:
  4. ``platform_tenant_relationships.calendar_freebusy_consent`` String(16)
     DEFAULT ``'free_busy_only'`` — canonical bilateral consent state.
     ``'free_busy_only'`` (default privacy-preserving) returns busy/free
     windows + status only; ``'full_details'`` (bilateral upgrade)
     additionally returns subject + location + attendee_count_bucket
     per §3.26.16.6 three-tier anonymization. Step 3 ships read-side;
     Step 4 ships bilateral consent upgrade UI.

NO new tables. NO column on calendar_accounts (``outbound_enabled``
already shipped at Step 1 r67 per Step 1 deviation 4 — verified at
Step 2 ship). The Step 1 + 2 entity model already supports outbound:
  - calendar_events.is_active flag for soft-delete on cancellation
  - calendar_events.status accepts 'cancelled' for RFC 5545 STATUS
  - calendar_events.recurrence_rule for RRULE encoding to wire format
  - calendar_event_instance_overrides for RECURRENCE-ID scoping per
    §3.26.16.5 Path 2 update + cancellation propagation

Revision ID: r69_calendar_outbound
Revises: r68_calendar_step2_credentials
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r69_calendar_outbound"
down_revision = "r68_calendar_step2_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── calendar_events state-change provenance ──────────────────────
    op.add_column(
        "calendar_events",
        sa.Column("generation_source", sa.String(32), nullable=True),
    )
    op.add_column(
        "calendar_events",
        sa.Column("generation_entity_type", sa.String(64), nullable=True),
    )
    op.add_column(
        "calendar_events",
        sa.Column("generation_entity_id", sa.String(36), nullable=True),
    )
    # Index supports fast lookup of state-change-generated events for
    # the per-entity drafted-event review queue (frontend /calendar/drafts
    # filters by generation_source="state_change").
    op.create_index(
        "ix_calendar_events_generation_state_change",
        "calendar_events",
        ["tenant_id", "generation_source"],
        postgresql_where=sa.text("generation_source = 'state_change'"),
    )

    # ── platform_tenant_relationships cross-tenant freebusy consent ──
    # Per Q1 Path A: extend PTR with bilateral consent state.
    op.add_column(
        "platform_tenant_relationships",
        sa.Column(
            "calendar_freebusy_consent",
            sa.String(16),
            nullable=False,
            server_default="free_busy_only",
        ),
    )
    op.create_check_constraint(
        "ck_ptr_calendar_freebusy_consent",
        "platform_tenant_relationships",
        "calendar_freebusy_consent IN ('free_busy_only', 'full_details')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ptr_calendar_freebusy_consent",
        "platform_tenant_relationships",
        type_="check",
    )
    op.drop_column(
        "platform_tenant_relationships", "calendar_freebusy_consent"
    )
    op.drop_index(
        "ix_calendar_events_generation_state_change",
        table_name="calendar_events",
    )
    op.drop_column("calendar_events", "generation_entity_id")
    op.drop_column("calendar_events", "generation_entity_type")
    op.drop_column("calendar_events", "generation_source")
