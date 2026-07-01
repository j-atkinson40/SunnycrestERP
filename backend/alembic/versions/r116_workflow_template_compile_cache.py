"""Compiled-workflow cache on workflow_templates (Canvas↔Runtime Bridge T-2.1a).

The MoC schedule sweep fires on a cadence; a draft-task template recompiled every
tick would bloat `workflows` (§7 of the T-2.1 investigation). This adds a cache:
the compiled runtime workflow is stored ONCE per template version and reused on
subsequent fires. `compiled_version` tracks the template version it was compiled
at — a version bump invalidates the cache (recompile). `compiled_workflow_id`
carries ON DELETE SET NULL so a deleted compiled workflow also invalidates it.

Mirror templates don't use the cache (re-point reuses the runtime source). No
data backfill — both columns start NULL (never-compiled).

Revision ID: r116_workflow_template_compile_cache
Revises: r115_moc_task_triggers
"""
from alembic import op
import sqlalchemy as sa

revision = "r116_workflow_template_compile_cache"
down_revision = "r115_moc_task_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_templates",
        sa.Column(
            "compiled_workflow_id", sa.String(36),
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "workflow_templates",
        sa.Column("compiled_version", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_templates", "compiled_version")
    op.drop_column("workflow_templates", "compiled_workflow_id")
