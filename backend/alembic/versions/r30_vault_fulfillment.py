"""r30_vault_fulfillment

Revision ID: r30_vault_fulfillment
Revises: r29_customer_credit_balance
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'r30_vault_fulfillment'
down_revision = 'r29_customer_credit_balance'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('companies', sa.Column('vault_fulfillment_mode', sa.String(20), nullable=True, server_default='produce'))
    op.add_column('inventory_items', sa.Column('fulfillment_method', sa.String(20), nullable=True))

    op.create_table(
        'vault_suppliers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('vendor_id', sa.String(36), sa.ForeignKey('vendors.id'), nullable=False),
        sa.Column('supplier_tenant_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=True),
        sa.Column('order_quantity', sa.Integer(), nullable=False),
        sa.Column('lead_time_days', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('delivery_schedule', sa.String(20), nullable=False, server_default='on_demand'),
        sa.Column('delivery_days', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('is_primary', sa.Boolean(), server_default='true'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('company_id', 'vendor_id', name='uq_vault_supplier_company_vendor'),
    )
    op.create_index('idx_vault_suppliers_company', 'vault_suppliers', ['company_id'])


def downgrade():
    op.drop_index('idx_vault_suppliers_company', 'vault_suppliers')
    op.drop_table('vault_suppliers')
    op.drop_column('inventory_items', 'fulfillment_method')
    op.drop_column('companies', 'vault_fulfillment_mode')
