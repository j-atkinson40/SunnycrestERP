"""r18 extension visibility — add is_extension_hidden and visibility_requires_extension
to customers and products tables, then backfill existing data.

Revision ID: r18_extension_visibility
Revises: r17_cemetery_directory
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "r18_extension_visibility"
down_revision = "r17_cemetery_directory"
branch_labels = None
depends_on = None


def upgrade():
    # ── customers ─────────────────────────────────────────────────────────────
    op.add_column(
        "customers",
        sa.Column(
            "visibility_requires_extension",
            sa.String(30),
            nullable=True,
            comment="'any_product_line' for contractors, null = always visible",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "is_extension_hidden",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="true = hidden until extension enabled, separate from is_active",
        ),
    )

    # ── products ──────────────────────────────────────────────────────────────
    op.add_column(
        "products",
        sa.Column(
            "visibility_requires_extension",
            sa.String(30),
            nullable=True,
            comment="'wastewater', 'redi_rock', 'rosetta', null = always visible",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "is_extension_hidden",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="true = hidden until extension enabled",
        ),
    )

    # ── backfill: funeral homes always visible ────────────────────────────────
    op.execute(
        text("""
        UPDATE customers
        SET visibility_requires_extension = NULL,
            is_extension_hidden = FALSE
        WHERE customer_type = 'funeral_home'
        """)
    )

    # ── backfill: contractors hidden if no product-line extension active ───────
    # Uses tenant_extensions table (the real extension system — not company_modules)
    op.execute(
        text("""
        UPDATE customers
        SET visibility_requires_extension = 'any_product_line',
            is_extension_hidden = TRUE
        WHERE customer_type = 'contractor'
        AND company_id NOT IN (
            SELECT DISTINCT tenant_id
            FROM tenant_extensions
            WHERE extension_key IN ('wastewater', 'redi_rock', 'rosetta')
            AND status = 'active'
        )
        """)
    )

    # Contractors at tenants that DO have an extension — stay visible
    op.execute(
        text("""
        UPDATE customers
        SET visibility_requires_extension = 'any_product_line',
            is_extension_hidden = FALSE
        WHERE customer_type = 'contractor'
        AND company_id IN (
            SELECT DISTINCT tenant_id
            FROM tenant_extensions
            WHERE extension_key IN ('wastewater', 'redi_rock', 'rosetta')
            AND status = 'active'
        )
        """)
    )


def downgrade():
    op.drop_column("products", "is_extension_hidden")
    op.drop_column("products", "visibility_requires_extension")
    op.drop_column("customers", "is_extension_hidden")
    op.drop_column("customers", "visibility_requires_extension")
