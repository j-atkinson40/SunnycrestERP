"""The Map Home campaign — the engagement substrate (commit set 3/5).

`ponder_engagement`: ONE keyspace across task / area / onboarding ponders
(`ponder_key` = 'task:<id>' | 'area:<vertical>:<area>' | 'onboarding:<key>').
Written QUIETLY on open / finish / dismiss; company-scoped reads. This is
the substrate that makes usage-driven suggestions honest LATER and
onboarding-state real NOW (an admin with unviewed onboarding compositions
IS new — no separate flag to drift). No behavior beyond recording + the
rule-based-v1 suggestion reads.

Revision ID: r131_ponder_engagement
Revises: r130_moc_composition
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa

revision = "r131_ponder_engagement"
down_revision = "r130_moc_composition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ponder_engagement",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("ponder_key", sa.String(200), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ux_ponder_engagement_user_key", "ponder_engagement",
        ["user_id", "ponder_key"], unique=True,
    )
    op.create_index(
        "ix_ponder_engagement_company", "ponder_engagement", ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ponder_engagement_company", table_name="ponder_engagement")
    op.drop_index("ux_ponder_engagement_user_key", table_name="ponder_engagement")
    op.drop_table("ponder_engagement")
