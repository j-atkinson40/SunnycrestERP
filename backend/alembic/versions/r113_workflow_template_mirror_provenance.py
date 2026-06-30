"""MoC workflow backfill (Build 1) — workflow_template mirror provenance.

Adds `workflow_templates.mirrored_from_workflow_id` (nullable FK → workflows.id,
ondelete SET NULL). When set, the template is an INERT snapshot-mirror of that
runtime workflow (its canvas faithfully reproduces the runtime steps but does not
execute + may drift). NULL for authored/seeded templates. The queryable
debt-handle: the future canvas↔runtime bridge finds mirrors via this column to
retire them when the real reconciliation lands.

Reversible. Nullable + indexed; existing rows are unaffected (NULL).

Revision ID: r113_workflow_template_mirror_provenance
Revises: r112_moc_task_catalog
"""
from alembic import op
import sqlalchemy as sa

revision = "r113_workflow_template_mirror_provenance"
down_revision = "r112_moc_task_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_templates",
        sa.Column(
            "mirrored_from_workflow_id",
            sa.String(36),
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_workflow_templates_mirrored_from_workflow_id",
        "workflow_templates",
        ["mirrored_from_workflow_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_templates_mirrored_from_workflow_id",
        table_name="workflow_templates",
    )
    op.drop_column("workflow_templates", "mirrored_from_workflow_id")
