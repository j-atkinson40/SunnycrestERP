"""r17 cemetery directory — add cemetery_directory, cemetery_directory_selections,
and cemetery_directory_fetch_logs tables.

Revision ID: r17_cemetery_directory
Revises: r16_seasonal_templates
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r17_cemetery_directory"
down_revision = "r16_seasonal_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cemetery_directory — cached Google Places results, scoped per company
    op.create_table(
        "cemetery_directory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("place_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state_code", sa.String(2), nullable=True),
        sa.Column("zip_code", sa.String(10), nullable=True),
        sa.Column("county", sa.String(100), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("google_rating", sa.Numeric(3, 1), nullable=True),
        sa.Column("google_review_count", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("first_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("company_id", "place_id", name="uq_cemetery_directory_company_place"),
    )
    op.create_index("idx_cemetery_directory_company", "cemetery_directory", ["company_id"])

    # cemetery_directory_selections — tracks add/skip decisions per company
    op.create_table(
        "cemetery_directory_selections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("place_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("action", sa.String(20), nullable=False, server_default="skipped"),
        sa.Column("cemetery_id", sa.String(36), sa.ForeignKey("cemeteries.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_cemetery_dir_sel_company", "cemetery_directory_selections", ["company_id"]
    )
    op.create_index(
        "idx_cemetery_dir_sel_cemetery", "cemetery_directory_selections", ["cemetery_id"]
    )

    # cemetery_directory_fetch_logs — 90-day cache invalidation audit trail
    op.create_table(
        "cemetery_directory_fetch_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("result_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("search_radius_miles", sa.Integer, nullable=False, server_default="50"),
        sa.Column("center_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("center_lng", sa.Numeric(9, 6), nullable=True),
    )
    op.create_index(
        "idx_cemetery_fetch_log_company", "cemetery_directory_fetch_logs", ["company_id"]
    )


def downgrade() -> None:
    op.drop_table("cemetery_directory_fetch_logs")
    op.drop_table("cemetery_directory_selections")
    op.drop_table("cemetery_directory")
