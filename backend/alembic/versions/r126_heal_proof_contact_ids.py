"""C-10 heal, round 3 — the r46 column on the r125-healed table.

The gate's second production-tier catch (staging, r125 deploy, 2026-07-15):

    Missing: legacy_fh_email_config.proof_contact_ids

Root: r46_legacy_fh_contact_ids added this column AFTER r42 created the
table — but staging never had the table when r46 was recorded (the same
stamped-past window), so the add_column no-op'd/failed silently. r125 then
healed the table to its r42 BIRTH shape, not its current MODEL shape, and
the r46 column stayed missing. Lesson (banked): heal migrations must
re-assert to the MODEL, not to the originating migration — downstream
column-adds ride on healed tables.

Verified model-complete: with this column, all three r125 tables match
Base.metadata exactly (legacy_email_settings 18/18, legacy_fh_email_config
9/9, company_migration_reviews 13/13) — no round 4 exists in these tables.

Guarded add (r124/r125 shape); downgrade deliberate no-op (same rationale).

Revision ID: r126_heal_proof_contact_ids
Revises: r125_heal_missing_tables
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = "r126_heal_proof_contact_ids"
down_revision = "r125_heal_missing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {c["name"] for c in sa_inspect(conn).get_columns("legacy_fh_email_config")}
    if "proof_contact_ids" not in cols:
        # Verbatim from r46_legacy_fh_contact_ids.
        op.add_column(
            "legacy_fh_email_config",
            sa.Column(
                "proof_contact_ids", JSONB,
                server_default=sa.text("'[]'::jsonb"), nullable=True,
            ),
        )


def downgrade() -> None:
    # Deliberate no-op — r124 rationale (the column belongs to r46).
    pass
