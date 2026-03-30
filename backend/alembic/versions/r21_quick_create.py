"""r21 — quick create: setup_complete on customers

Revision ID: r21_quick_create
Revises: r20_cemetery_experience
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r21_quick_create"
down_revision = "r20_cemetery_experience"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "customers",
        sa.Column(
            "setup_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade():
    op.drop_column("customers", "setup_complete")
