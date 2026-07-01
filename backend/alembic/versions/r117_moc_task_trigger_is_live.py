"""MoC task trigger is_live promotion (Canvas↔Runtime Bridge T-2.1b).

Per-trigger live-promotion gate. EVERY existing trigger starts is_live=FALSE
(unpromoted → dry-run). The schedule sweep fires live ONLY when a trigger is
is_live AND its task resolves to a COMPILED (single-owner) workflow (the §6
double-fire hazard defers mirror-task live-scheduling). Default FALSE is the
safety posture: promotion is a deliberate per-trigger act.

Revision ID: r117_moc_task_trigger_is_live
Revises: r116_workflow_template_compile_cache
"""
from alembic import op
import sqlalchemy as sa

revision = "r117_moc_task_trigger_is_live"
down_revision = "r116_workflow_template_compile_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "moc_task_trigger",
        sa.Column(
            "is_live", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("moc_task_trigger", "is_live")
