"""FH-1b cross-tenant network tables: cemetery_plots + cemetery_map_config.

platform_tenant_relationships already exists (from earlier platform_tenant_relationship
migration) — we reuse it. This migration only adds cemetery-specific tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "fh_02_cross_tenant"
down_revision = "fh_01_case_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────────
    # cemetery_plots — individual plots in a cemetery tenant's inventory
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "cemetery_plots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("section", sa.String(50), nullable=True),
        sa.Column("row", sa.String(50), nullable=True),
        sa.Column("number", sa.String(50), nullable=True),
        sa.Column("plot_label", sa.String(100), nullable=True),
        sa.Column("plot_type", sa.String(50), nullable=False, server_default="single"),
        # single | double | cremation_niche | mausoleum | green | veteran
        sa.Column("status", sa.String(50), nullable=False, server_default="available"),
        # available | reserved | sold | unavailable
        # Coordinates as percentages (0-100) so the SVG scales to any container
        sa.Column("map_x", sa.Float, nullable=True),
        sa.Column("map_y", sa.Float, nullable=True),
        sa.Column("map_width", sa.Float, nullable=True),
        sa.Column("map_height", sa.Float, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("opening_closing_fee", sa.Numeric(10, 2), nullable=True),
        # Reservation state
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reserved_for_case_id", sa.String(36), nullable=True),
        sa.Column("reserved_by_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
        # Sold state
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cemetery_plots_company", "cemetery_plots", ["company_id"])
    op.create_index("ix_cemetery_plots_company_status", "cemetery_plots", ["company_id", "status"])
    op.create_index(
        "uq_cemetery_plot_location",
        "cemetery_plots",
        ["company_id", "section", "row", "number"],
        unique=True,
    )

    # ─────────────────────────────────────────────────────────────
    # cemetery_map_config — one per cemetery tenant
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "cemetery_map_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("map_image_url", sa.String(500), nullable=True),
        sa.Column("map_width_ft", sa.Float, nullable=True),
        sa.Column("map_height_ft", sa.Float, nullable=True),
        sa.Column("sections", JSONB, nullable=True),   # [{name, color, description}]
        sa.Column("legend", JSONB, nullable=True),     # [{plot_type, color, label}]
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("cemetery_map_config")
    op.drop_index("uq_cemetery_plot_location", table_name="cemetery_plots")
    op.drop_index("ix_cemetery_plots_company_status", table_name="cemetery_plots")
    op.drop_index("ix_cemetery_plots_company", table_name="cemetery_plots")
    op.drop_table("cemetery_plots")
