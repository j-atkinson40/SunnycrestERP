"""Add is_personalized_default flag to tenant_training_docs.

Revision ID: o2a3b4c5d6e7
Revises: o1a2b3c4d5e6
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op

revision = "o2a3b4c5d6e7"
down_revision = "o1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_training_docs",
        sa.Column("is_personalized_default", sa.Boolean(), server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("tenant_training_docs", "is_personalized_default")
