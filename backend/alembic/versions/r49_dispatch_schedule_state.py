"""Phase B Session 1 — Dispatch schedule state machine + hole-dug field.

Revision ID: r49_dispatch_schedule_state
Revises: r48_focus_sessions_and_layout_defaults

Ships two concerns together because they share a migration window:

  1. `delivery_schedules` — per-tenant per-date aggregate table carrying
     the draft/finalized state machine. Lazy-created on first access;
     not every day gets a row. State machine: draft → finalized (explicit
     by user OR auto at 1pm local) → reverts to draft if any delivery
     on that date is edited after finalize.

  2. `deliveries.hole_dug_status` — three-state quick-edit field
     (unknown | yes | no) surfaced from the Dispatch Monitor card.

**Filename collision note:** an orphaned parallel migration file
`r49_crm_opportunities.py` exists on disk but is NOT part of the
active alembic graph (it descends from a dead `r48_manufacturer_
profiles_crm_settings` branch that was never applied). Flagged as
tech debt; does not affect this migration's graph.
"""

from alembic import op
import sqlalchemy as sa


revision = "r49_dispatch_schedule_state"
down_revision = "r48_focus_sessions_and_layout_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── delivery_schedules: per-tenant per-date state machine ──────────
    op.create_table(
        "delivery_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schedule_date", sa.Date, nullable=False),
        # state: draft | finalized
        # The enum is intentionally narrow; auto_finalized=True is how
        # we distinguish "user clicked Finalize" from "1pm job stamped."
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "finalized_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finalized_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # True iff the 1pm scheduler job stamped the finalize. Null
        # otherwise (draft row) or False (explicit user finalize).
        sa.Column(
            "auto_finalized",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Revert audit: preserved across state flips so we can tell
        # "this was finalized on X, then reverted on Y."
        sa.Column(
            "last_reverted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_revert_reason",
            sa.String(200),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "state IN ('draft', 'finalized')",
            name="ck_delivery_schedules_state",
        ),
        sa.UniqueConstraint(
            "company_id",
            "schedule_date",
            name="uq_delivery_schedules_company_date",
        ),
    )

    # Hot-path index for Monitor 3-day queries (range scan filtered by
    # company_id, sorted by schedule_date).
    op.create_index(
        "ix_delivery_schedules_company_date",
        "delivery_schedules",
        ["company_id", "schedule_date"],
    )

    # Partial index supports "find all pending-finalize schedules"
    # queries the auto-finalize job runs.
    op.create_index(
        "ix_delivery_schedules_pending_finalize",
        "delivery_schedules",
        ["company_id", "schedule_date"],
        postgresql_where=sa.text("state = 'draft'"),
    )

    # ── deliveries.hole_dug_status ─────────────────────────────────────
    # NULL on existing rows → treated as "unknown" by the service
    # layer. Nullable (instead of default="unknown") so existing
    # deliveries don't get a false-positive "unknown" stamp that
    # implies "a dispatcher looked at this and said they don't know."
    # A null value means "nobody touched this yet."
    op.add_column(
        "deliveries",
        sa.Column(
            "hole_dug_status",
            sa.String(16),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_deliveries_hole_dug_status",
        "deliveries",
        "hole_dug_status IS NULL OR hole_dug_status IN ('unknown', 'yes', 'no')",
    )


def downgrade() -> None:
    # Reverse order of upgrade.
    op.drop_constraint(
        "ck_deliveries_hole_dug_status",
        "deliveries",
        type_="check",
    )
    op.drop_column("deliveries", "hole_dug_status")

    op.drop_index(
        "ix_delivery_schedules_pending_finalize",
        table_name="delivery_schedules",
    )
    op.drop_index(
        "ix_delivery_schedules_company_date",
        table_name="delivery_schedules",
    )
    op.drop_table("delivery_schedules")
