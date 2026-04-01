"""Add vault mold configs table, spare component columns, production component tracking.

Revision ID: r31_vault_mold_setup
Revises: r30_vault_fulfillment
"""

from alembic import op
import sqlalchemy as sa

revision = "r31_vault_mold_setup"
down_revision = "r30_vault_fulfillment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: vault_mold_configs ────────────────────────────────────
    op.create_table(
        "vault_mold_configs",
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
        sa.Column("daily_capacity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("notes", sa.Text, nullable=True),
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
        sa.UniqueConstraint("company_id", "product_id", name="uq_vault_mold_company_product"),
    )
    op.create_index(
        "idx_vault_mold_configs_company",
        "vault_mold_configs",
        ["company_id"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ── Spare component columns on inventory_items ───────────────────────
    op.add_column(
        "inventory_items",
        sa.Column("spare_covers", sa.Integer, server_default="0"),
    )
    op.add_column(
        "inventory_items",
        sa.Column("spare_bases", sa.Integer, server_default="0"),
    )

    # ── Component tracking on ops_production_log_entries ──────────────────
    op.add_column(
        "ops_production_log_entries",
        sa.Column("component_type", sa.String(20), server_default="complete"),
    )
    op.add_column(
        "ops_production_log_entries",
        sa.Column("component_reason", sa.String(50), nullable=True),
    )

    # ── Visibility condition on onboarding_checklist_items ────────────────
    op.add_column(
        "onboarding_checklist_items",
        sa.Column("visibility_condition", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("onboarding_checklist_items", "visibility_condition")
    op.drop_column("ops_production_log_entries", "component_reason")
    op.drop_column("ops_production_log_entries", "component_type")
    op.drop_column("inventory_items", "spare_bases")
    op.drop_column("inventory_items", "spare_covers")
    op.drop_index("idx_vault_mold_configs_company", table_name="vault_mold_configs")
    op.drop_table("vault_mold_configs")
