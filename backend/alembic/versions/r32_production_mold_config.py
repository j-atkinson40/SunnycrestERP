"""Rename vault_mold_configs to production_mold_configs, add product_category.

Revision ID: r32_production_mold_config
Revises: r31_vault_mold_setup
"""

from alembic import op
import sqlalchemy as sa

revision = "r32_production_mold_config"
down_revision = "r31_vault_mold_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename table
    op.rename_table("vault_mold_configs", "production_mold_configs")

    # Add product_category column
    op.add_column(
        "production_mold_configs",
        sa.Column("product_category", sa.String(50), server_default="burial_vault"),
    )

    # Backfill existing records
    op.execute(
        "UPDATE production_mold_configs SET product_category = 'burial_vault' "
        "WHERE product_category IS NULL"
    )

    # Drop old index, create new ones
    op.drop_index("idx_vault_mold_configs_company", table_name="production_mold_configs")

    op.create_index(
        "idx_production_mold_configs_company",
        "production_mold_configs",
        ["company_id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_production_mold_configs_category",
        "production_mold_configs",
        ["company_id", "product_category"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("idx_production_mold_configs_category", table_name="production_mold_configs")
    op.drop_index("idx_production_mold_configs_company", table_name="production_mold_configs")
    op.create_index(
        "idx_vault_mold_configs_company",
        "production_mold_configs",
        ["company_id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_column("production_mold_configs", "product_category")
    op.rename_table("production_mold_configs", "vault_mold_configs")
