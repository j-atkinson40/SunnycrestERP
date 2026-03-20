"""Add driver milestone settings, delivery area, and service territories.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- manufacturer_service_territories table ---
    op.create_table(
        "manufacturer_service_territories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("county_name", sa.String(100), nullable=False),
        sa.Column("county_fips", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_mst_company_id",
        "manufacturer_service_territories",
        ["company_id"],
    )
    op.create_index(
        "ix_mst_state_county",
        "manufacturer_service_territories",
        ["state_code", "county_name"],
    )

    # --- Remove set_delivery_area checklist item (if it exists) ---
    # This is done at the app level via onboarding_service, not via SQL here,
    # since the items are seeded per-tenant.  The seed code is being updated.

    # --- Existing tenants: set delivery_area_configured = true
    # if they have territories.  Done at app startup via seed logic.


def downgrade() -> None:
    op.drop_index("ix_mst_state_county", table_name="manufacturer_service_territories")
    op.drop_index("ix_mst_company_id", table_name="manufacturer_service_territories")
    op.drop_table("manufacturer_service_territories")
