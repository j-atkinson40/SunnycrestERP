"""Rename order status shipped -> delivered

Revision ID: z9j7k8l9m0n1
Revises: z9i6j7k8l9m0
Create Date: 2026-04-07
"""
from alembic import op

revision = "z9j7k8l9m0n1"
down_revision = "z9i6j7k8l9m0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE sales_orders SET status = 'delivered' WHERE status = 'shipped'")


def downgrade() -> None:
    op.execute("UPDATE sales_orders SET status = 'shipped' WHERE status = 'delivered'")
