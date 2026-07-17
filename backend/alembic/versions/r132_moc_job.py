"""Reframe R-1 — the JOB entity + the polymorphic reference spine.

TASKS = the jobs (displayed "Task"; code name `moc_job` — the honest
divergence per tasks_reframe_investigation.md §3: the old entity keeps its
code surface, the new entity keeps its clean display name). The current
catalog rows are AUTOMATIONS (the means).

`moc_job` — platform/vertical tiers only (option A; the tenant tier
arrives by its own migration when called — no speculative columns).

`moc_job_ref` — ONE polymorphic reference table (the offers-table
precedent): kind ∈ {automation, triage_queue, focus}, key lineage-stable
per kind (automation: catalog row id; triage_queue: the stable queue_id;
focus: template_slug — the version-bump rebind lesson). Capability +
document refs slot in later with zero migrations.

Revision ID: r132_moc_job
Revises: r131_ponder_engagement
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r132_moc_job"
down_revision = "r131_ponder_engagement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_job",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(24), nullable=False, server_default="vertical_default"),
        sa.Column("vertical", sa.String(32), sa.ForeignKey("verticals.slug"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("task_type", sa.String(120), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ponder", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_moc_job_scope",
        ),
    )
    op.create_index(
        "ux_moc_job_identity", "moc_job", ["scope", "vertical", "name"],
        unique=True, postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "moc_job_ref",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id", sa.String(36),
            sa.ForeignKey("moc_job.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("ref_kind", sa.String(24), nullable=False),
        sa.Column("ref_key", sa.String(120), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "ref_kind IN ('automation', 'triage_queue', 'focus')",
            name="ck_moc_job_ref_kind",
        ),
    )
    op.create_index(
        "ux_moc_job_ref", "moc_job_ref", ["job_id", "ref_kind", "ref_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_moc_job_ref", table_name="moc_job_ref")
    op.drop_table("moc_job_ref")
    op.drop_index("ux_moc_job_identity", table_name="moc_job")
    op.drop_table("moc_job")
