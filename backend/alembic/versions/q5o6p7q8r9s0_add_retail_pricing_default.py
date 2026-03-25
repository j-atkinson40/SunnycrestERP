"""Add retail pricing default and auto_created flag.

Revision ID: q5o6p7q8r9s0
Revises: q4n5o6p7q8r9
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "q5o6p7q8r9s0"
down_revision = "q4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add auto_created column
    op.add_column("inter_licensee_price_lists", sa.Column("auto_created", sa.Boolean(), server_default="false"))

    # Change default pricing_method to 'retail'
    op.alter_column("inter_licensee_price_lists", "pricing_method", server_default="retail")


def downgrade() -> None:
    op.alter_column("inter_licensee_price_lists", "pricing_method", server_default="fixed")
    op.drop_column("inter_licensee_price_lists", "auto_created")
