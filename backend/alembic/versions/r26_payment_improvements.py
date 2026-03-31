"""r26_payment_improvements

Revision ID: r26_payment_improvements
Revises: r25_funeral_home_preferences
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'r26_payment_improvements'
down_revision = 'r25_funeral_home_preferences'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('invoices', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoices', sa.Column('discount_amount', sa.Numeric(10, 2), nullable=True, server_default='0.00'))
    op.add_column('invoices', sa.Column('discount_deadline', sa.Date(), nullable=True))
    op.add_column('invoices', sa.Column('discounted_total', sa.Numeric(10, 2), nullable=True))
    op.add_column('customer_payment_applications', sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('invoices', 'paid_at')
    op.drop_column('invoices', 'discount_amount')
    op.drop_column('invoices', 'discount_deadline')
    op.drop_column('invoices', 'discounted_total')
    op.drop_column('customer_payment_applications', 'notes')
