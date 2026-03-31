"""r28 — Merge payment improvements branch with main chain

Revision ID: r28_merge_payment_improvements
Revises: r26_payment_improvements, r27_branding
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'r28_merge_payment_improvements'
down_revision = ('r26_payment_improvements', 'r27_branding')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
