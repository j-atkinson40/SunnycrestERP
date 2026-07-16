"""Ponder P0 — the authored-caption block on the task-catalog row.

`moc_task_catalog.ponder` (JSONB, nullable): the per-beat authored caption
overlay for the ponder walkthrough, keyed by stable beat keys (node slugs
for step beats — the C-2.1.2 slug-is-identity pattern; reserved keys for
when/downstream/garnish beats). Shape:

    {"captions": {"step:identify_customers": "…", "when": "…"}}

Flagged deviation from the investigation's "no new table, rides the
existing row": the task-catalog row had NO JSONB column to ride — this
adds the column (still no new table). Reversible.

Revision ID: r127_moc_task_ponder
Revises: r126_heal_proof_contact_ids
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r127_moc_task_ponder"
down_revision = "r126_heal_proof_contact_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "moc_task_catalog",
        sa.Column("ponder", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("moc_task_catalog", "ponder")
