"""MoC witness marker — the benign-but-real effect table (Canvas↔Runtime Bridge
T-2.1b-WITNESS).

A DEDICATED, ISOLATED table whose ONLY writer is the `record_marker` action
handler. It exists so the platform's FIRST autonomous real scheduled fire has a
target that is genuinely REAL (a persisted, attributable row — proving live
firing end-to-end, not another dry-run) yet genuinely BENIGN (a table nothing
else reads — no invoice, no notification, no external call, no business effect).
Reversible: a witness marker means nothing but "a compiled MoC task fired live at
T"; the rows are safe to delete.

`vault_items` was NOT reused — `_handle_log_vault_item` silently swallows its
INSERT (vault_items.vault_id is NOT NULL without a default), so it writes nothing
and could not prove a live fire. This table is the clean marker target.

Attribution columns (run_id / moc_task_trigger_id) are plain nullable strings, NOT
FKs — breadcrumbs that keep the witness table decoupled + independently
deletable. company_id carries a real FK (tenant scoping is load-bearing).

Revision ID: r118_moc_witness_marker
Revises: r117_moc_task_trigger_is_live
"""
from alembic import op
import sqlalchemy as sa

revision = "r118_moc_witness_marker"
down_revision = "r117_moc_task_trigger_is_live"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_witness_marker",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        # Attribution breadcrumbs (no FK — keeps the marker table isolated).
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("moc_task_trigger_id", sa.String(36), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("moc_witness_marker")
