"""add inventory

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11

"""

from typing import Sequence, Union

import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Inventory items table
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("quantity_on_hand", sa.Integer, server_default=sa.text("0")),
        sa.Column("reorder_point", sa.Integer, nullable=True),
        sa.Column("reorder_quantity", sa.Integer, nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("last_counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "product_id", "company_id", name="uq_inventory_product_company"
        ),
    )

    # Inventory transactions table
    op.create_table(
        "inventory_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("quantity_change", sa.Integer, nullable=False),
        sa.Column("quantity_after", sa.Integer, nullable=False),
        sa.Column("reference", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_inv_tx_company_created",
        "inventory_transactions",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_inv_tx_product",
        "inventory_transactions",
        ["product_id"],
    )

    # Backfill: create inventory items for all existing products
    conn = op.get_bind()
    products = conn.execute(
        sa.text("SELECT id, company_id FROM products")
    ).fetchall()
    for product_id, company_id in products:
        conn.execute(
            sa.text(
                "INSERT INTO inventory_items (id, company_id, product_id, quantity_on_hand) "
                "VALUES (:id, :company_id, :product_id, 0)"
            ),
            {
                "id": str(uuid.uuid4()),
                "company_id": company_id,
                "product_id": product_id,
            },
        )


def downgrade() -> None:
    op.drop_table("inventory_transactions")
    op.drop_table("inventory_items")
