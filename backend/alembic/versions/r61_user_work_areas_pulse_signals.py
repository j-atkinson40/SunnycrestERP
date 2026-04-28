"""Phase W-4a Commit 1 — User work_areas + responsibilities + pulse_signals.

Adds two operator-profile columns to ``users`` plus the ``pulse_signals``
table that backs the Pulse Tier 2 signal-driven intelligence (dismiss
+ navigation tracking).

**Schema additions:**

1. ``users.work_areas`` (JSONB NULL)
   - Multi-select work-area enum values per BRIDGEABLE_MASTER §3.26.3.1
   - Examples: ['Production Scheduling', 'Delivery Scheduling',
     'Inventory Management']
   - Drives Tier 1 rule-based Pulse composition (which widgets surface
     for which user)
   - NULL during the user-not-yet-onboarded window — falls back to
     vertical-default Pulse composition (D4 resolution)
   - JSONB chosen over Postgres ARRAY for cross-DB test compatibility
     (existing Documents test suite uses SQLite in-memory which
     can't render ARRAY). No consumer of work_areas currently needs
     Postgres `&&` overlap operators; JSONB list[str] storage
     supports all current and demo-quality query needs (`@>`
     containment) and aligns with the established preferences-JSONB
     storage pattern for user-scoped list data.

2. ``users.responsibilities_description`` (TEXT NULL)
   - Free-text natural-language description per §3.26.3.2
   - Used by Tier 2+ intelligence (responsibilities feed personalized
     anomaly synthesis when V2 Haiku-cached ships post-W-4a)
   - NULL during onboarding window

3. ``pulse_signals`` (new table)
   - Persists Pulse content interaction signals for Tier 2 algorithms
     (dismiss tracking + navigation tracking). Storage chosen per D3
     resolution as a dedicated table (not user_space_affinity
     extension; not JSONB on preferences) because:
     (a) Pulse signals are first-class platform data (audit trail,
         future cross-tenant analytics for Mutual underwriting per
         BRIDGEABLE_MASTER §1.7)
     (b) Distinct semantically from command-bar affinity
     (c) TTL-cleanup-friendly (90-day retention contemplated; cleanup
         job lands separately)
     (d) Bounded per-user volume (~hundreds/week worst case) but
         queryable across users for analytics
   - Schema:
       id (UUID PK)
       user_id (FK → users)
       company_id (FK → companies) — tenant scoping discipline
       signal_type (VARCHAR — currently {"dismiss", "navigate"})
       layer (VARCHAR — {"personal","operational","anomaly","activity"})
       component_key (VARCHAR — e.g., "vault_schedule",
                      "anomaly_intelligence_stream")
       timestamp (TIMESTAMPTZ — when the signal fired)
       metadata (JSONB — standardized per signal_type)
   - **Standardized JSONB metadata shapes** (per user direction):
       Dismiss signals: {component_key, time_of_day,
                         work_areas_at_dismiss}
       Navigation signals: {from_component_key, to_route,
                            dwell_time_seconds}
   - Indexes:
       (user_id, timestamp DESC) — primary read path for "what has
                                    this user dismissed recently"
       (company_id, timestamp DESC) — analytics / Mutual cross-tenant
                                      aggregation read path

**Migration semantics:**
- Backfill: existing users keep NULL work_areas + NULL responsibilities
  until they complete operator onboarding. Pulse falls back to
  vertical-default composition per D4.
- Reversible: downgrade drops both columns + the table cleanly.

Revision ID: r61_user_work_areas_pulse_signals
Revises: r60_backfill_tenant_product_lines_vault
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r61_user_work_areas_pulse_signals"
down_revision = "r60_backfill_tenant_product_lines_vault"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.work_areas ────────────────────────────────────────────
    # JSONB storage of list[str] — ARRAY(String) was considered but
    # rejected for cross-DB test compat. See module docstring for
    # full rationale.
    op.add_column(
        "users",
        sa.Column(
            "work_areas",
            JSONB,
            nullable=True,
            comment=(
                "Phase W-4a — operator multi-select work areas per "
                "BRIDGEABLE_MASTER §3.26.3.1. NULL during onboarding "
                "window; falls back to vertical-default Pulse."
            ),
        ),
    )

    # ── users.responsibilities_description ──────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "responsibilities_description",
            sa.Text(),
            nullable=True,
            comment=(
                "Phase W-4a — free-text responsibilities per §3.26.3.2. "
                "Feeds Tier 2+ Pulse intelligence post-W-4a."
            ),
        ),
    )

    # ── pulse_signals table ─────────────────────────────────────────
    op.create_table(
        "pulse_signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "signal_type",
            sa.String(32),
            nullable=False,
            comment="dismiss | navigate (extensible)",
        ),
        sa.Column(
            "layer",
            sa.String(32),
            nullable=False,
            comment="personal | operational | anomaly | activity",
        ),
        sa.Column(
            "component_key",
            sa.String(128),
            nullable=False,
            comment=(
                "Pulse piece identifier. For pinable widgets: widget_id "
                "(e.g., 'vault_schedule'). For intelligence streams: "
                "stream key (e.g., 'anomaly_intelligence_stream')."
            ),
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment=(
                "Standardized per signal_type. "
                "Dismiss: {component_key, time_of_day, "
                "work_areas_at_dismiss}. "
                "Navigate: {from_component_key, to_route, "
                "dwell_time_seconds}."
            ),
        ),
    )
    op.create_index(
        "ix_pulse_signals_user_timestamp",
        "pulse_signals",
        ["user_id", sa.text("timestamp DESC")],
    )
    op.create_index(
        "ix_pulse_signals_company_timestamp",
        "pulse_signals",
        ["company_id", sa.text("timestamp DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_pulse_signals_company_timestamp", table_name="pulse_signals")
    op.drop_index("ix_pulse_signals_user_timestamp", table_name="pulse_signals")
    op.drop_table("pulse_signals")
    op.drop_column("users", "responsibilities_description")
    op.drop_column("users", "work_areas")
