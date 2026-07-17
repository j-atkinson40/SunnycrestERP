"""Transfer T-1 — the runtime schedule's retire surface.

`workflows.schedule_retired_at`: NULL = the runtime scheduler owns this
workflow's schedule (status quo); a timestamp = the schedule authority was
ADOPTED into the MoC trigger at that moment — the runtime scheduler skips it
permanently (the one-way transfer; de-promoting the MoC trigger is the off
switch, the runtime entry does not resurrect).

Deliberately a timestamp, not a boolean: the adopt moment IS the audit trail
(when did authority move), and the T-0 discriminator + the scheduler query
both read plain NULL-ness. `trigger_type` + `trigger_config` stay untouched —
the workflow's authored shape remains honest history.

Revision ID: r129_workflow_schedule_retired
Revises: r128_moc_task_fork_lineage
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa

revision = "r129_workflow_schedule_retired"
down_revision = "r128_moc_task_fork_lineage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("schedule_retired_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflows", "schedule_retired_at")
