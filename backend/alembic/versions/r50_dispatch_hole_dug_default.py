"""Phase B Session 1 Phase 3.1 — hole_dug_status NOT NULL default 'unknown'.

Revision ID: r50_dispatch_hole_dug_default
Revises: r49_dispatch_schedule_state

Phase 3 Monitor user testing surfaced that a null state for hole_dug is
confusing in practice. Dispatchers want three clean states:

  - unknown  (default — we haven't checked yet)
  - yes      (hole is dug, ready for vault)
  - no       (hole is NOT dug, flag for follow-up)

The 2026-04-23 Phase 3.1 feedback was explicit:
"Make hole-dug NON-NULLABLE with default 'unknown'. The null state
adds a fourth option that nobody asked for. Every delivery has a
hole-dug state — the question is whether we've confirmed it yet."

**Migration steps:**

  1. Backfill NULL → 'unknown' for every existing delivery.
  2. Alter column NOT NULL with server_default='unknown'.

**Downgrade:** relax NOT NULL + drop default. NULL values are not
restored (that would require an audit column tracking "was originally
null" — not worth the machinery for a reversible-by-not-restoring-
empty-state migration).

**Filename collision note:** an orphaned `r50_company_classification.py`
exists on the dead `r49_crm_opportunities` branch. This file sits on
the live graph (`r49_dispatch_schedule_state` → r50_dispatch_hole_dug_
default). Two r50 files on disk; one alembic graph. Tech debt tracked.
"""

from alembic import op
import sqlalchemy as sa


revision = "r50_dispatch_hole_dug_default"
down_revision = "r49_dispatch_schedule_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill: any pre-existing NULL becomes 'unknown'.
    op.execute(
        "UPDATE deliveries SET hole_dug_status = 'unknown' "
        "WHERE hole_dug_status IS NULL"
    )

    # Alter to NOT NULL with server_default.
    op.alter_column(
        "deliveries",
        "hole_dug_status",
        existing_type=sa.String(16),
        nullable=False,
        server_default=sa.text("'unknown'"),
    )


def downgrade() -> None:
    # Relax NOT NULL; drop default. NULL values not restored.
    op.alter_column(
        "deliveries",
        "hole_dug_status",
        existing_type=sa.String(16),
        nullable=True,
        server_default=None,
    )
