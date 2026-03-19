"""Add spring burial fields to sales_orders and seasonal fields to customers.

Revision ID: a4b5c6d7e8f9
Revises: z3a4b5c6d7e8
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "a4b5c6d7e8f9"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    # -- Spring burial fields on sales_orders --
    so_cols = [c["name"] for c in inspector.get_columns("sales_orders")]
    if "is_spring_burial" not in so_cols:
        op.add_column("sales_orders", sa.Column("is_spring_burial", sa.Boolean, server_default="false"))
    if "spring_burial_added_at" not in so_cols:
        op.add_column("sales_orders", sa.Column("spring_burial_added_at", sa.DateTime(timezone=True), nullable=True))
    if "spring_burial_added_by" not in so_cols:
        op.add_column("sales_orders", sa.Column("spring_burial_added_by", sa.String(36), nullable=True))
    if "spring_burial_notes" not in so_cols:
        op.add_column("sales_orders", sa.Column("spring_burial_notes", sa.Text, nullable=True))
    if "spring_burial_scheduled_at" not in so_cols:
        op.add_column("sales_orders", sa.Column("spring_burial_scheduled_at", sa.DateTime(timezone=True), nullable=True))
    if "spring_burial_scheduled_by" not in so_cols:
        op.add_column("sales_orders", sa.Column("spring_burial_scheduled_by", sa.String(36), nullable=True))

    # -- Seasonal fields on customers --
    cust_cols = [c["name"] for c in inspector.get_columns("customers")]
    if "typical_opening_date" not in cust_cols:
        op.add_column("customers", sa.Column("typical_opening_date", sa.String(5), nullable=True))
    if "winter_closure_start" not in cust_cols:
        op.add_column("customers", sa.Column("winter_closure_start", sa.String(5), nullable=True))
    if "is_seasonal" not in cust_cols:
        op.add_column("customers", sa.Column("is_seasonal", sa.Boolean, server_default="false"))
    if "opening_date_notes" not in cust_cols:
        op.add_column("customers", sa.Column("opening_date_notes", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "opening_date_notes")
    op.drop_column("customers", "is_seasonal")
    op.drop_column("customers", "winter_closure_start")
    op.drop_column("customers", "typical_opening_date")
    op.drop_column("sales_orders", "spring_burial_scheduled_by")
    op.drop_column("sales_orders", "spring_burial_scheduled_at")
    op.drop_column("sales_orders", "spring_burial_notes")
    op.drop_column("sales_orders", "spring_burial_added_by")
    op.drop_column("sales_orders", "spring_burial_added_at")
    op.drop_column("sales_orders", "is_spring_burial")
