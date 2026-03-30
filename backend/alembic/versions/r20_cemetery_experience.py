"""Cemetery experience rebuild — new columns on 4 tables.

Adds:
  cemeteries.customer_id       FK → customers (billing link)
  cemeteries.latitude          Numeric(9,6)
  cemeteries.longitude         Numeric(9,6)
  cemeteries.tax_county_confirmed  Boolean default false
  sales_orders.cemetery_id     FK → cemeteries (hard FK replacing free-text)
  licensee_transfers.cemetery_id  FK → cemeteries

Revision ID: r20_cemetery_experience
Revises: r19_classification_metadata
"""

revision = "r20_cemetery_experience"
down_revision = "r19_classification_metadata"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # cemeteries: customer billing link
    op.add_column("cemeteries", sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True))
    op.create_index("idx_cemeteries_customer", "cemeteries", ["customer_id"], postgresql_where=sa.text("customer_id IS NOT NULL"))

    # cemeteries: geo coordinates
    op.add_column("cemeteries", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("cemeteries", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))

    # cemeteries: tax county confirmation
    op.add_column("cemeteries", sa.Column("tax_county_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # sales_orders: cemetery FK
    op.add_column("sales_orders", sa.Column("cemetery_id", sa.String(36), sa.ForeignKey("cemeteries.id", ondelete="SET NULL"), nullable=True))
    op.create_index("idx_orders_cemetery", "sales_orders", ["cemetery_id"], postgresql_where=sa.text("cemetery_id IS NOT NULL"))

    # licensee_transfers: cemetery FK
    op.add_column("licensee_transfers", sa.Column("cemetery_id", sa.String(36), sa.ForeignKey("cemeteries.id", ondelete="SET NULL"), nullable=True))
    op.create_index("idx_transfers_cemetery", "licensee_transfers", ["cemetery_id"], postgresql_where=sa.text("cemetery_id IS NOT NULL"))


def downgrade():
    op.drop_index("idx_transfers_cemetery", "licensee_transfers")
    op.drop_column("licensee_transfers", "cemetery_id")
    op.drop_index("idx_orders_cemetery", "sales_orders")
    op.drop_column("sales_orders", "cemetery_id")
    op.drop_column("cemeteries", "tax_county_confirmed")
    op.drop_column("cemeteries", "longitude")
    op.drop_column("cemeteries", "latitude")
    op.drop_index("idx_cemeteries_customer", "cemeteries")
    op.drop_column("cemeteries", "customer_id")
