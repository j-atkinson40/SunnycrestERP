"""Add display_name to workflow_steps.

Revision ID: fh_08_step_display_name
Revises: fh_07_playwright_workflows
Create Date: 2026-04-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "fh_08_step_display_name"
down_revision = "fh_07_playwright_workflows"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workflow_steps",
        sa.Column("display_name", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("workflow_steps", "display_name")
