"""Tenant Ponder-Editor P2 — the fork lineage handle.

`moc_task_catalog.forked_from_task_id`: a tenant_override row created by the
prompted fork records WHICH vertical-default row it was born from. The column
serves two jobs from day one:

  1. THE MERGED-VIEW YIELD — a tenant's map shows THEIR version instead of
     the default it forked from (the default row is excluded from that
     tenant's merged read only; every other tenant's view is unchanged).
  2. PROVENANCE — the offer-reach handle for P3 (vertical-default updates
     offered to forked tenants), shipped now so lineage is never retrofitted.

ON DELETE SET NULL: a deleted default orphans the lineage pointer without
touching the tenant's row (their fork outlives the default honestly).

Revision ID: r128_moc_task_fork_lineage
Revises: r127_moc_task_ponder
"""
from alembic import op
import sqlalchemy as sa

revision = "r128_moc_task_fork_lineage"
down_revision = "r127_moc_task_ponder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "moc_task_catalog",
        sa.Column("forked_from_task_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_moc_task_forked_from",
        "moc_task_catalog",
        "moc_task_catalog",
        ["forked_from_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_moc_task_catalog_forked_from_task_id",
        "moc_task_catalog",
        ["forked_from_task_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_moc_task_catalog_forked_from_task_id", table_name="moc_task_catalog"
    )
    op.drop_constraint(
        "fk_moc_task_forked_from", "moc_task_catalog", type_="foreignkey"
    )
    op.drop_column("moc_task_catalog", "forked_from_task_id")
