"""r16 seasonal templates — add template_seasons table and seasonal_only column.

Revision ID: r16_seasonal_templates
Revises: r15_cemeteries
Create Date: 2026-03-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "r16_seasonal_templates"
down_revision = "r15_cemeteries"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "quick_quote_templates",
        sa.Column("seasonal_only", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_table(
        "template_seasons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("season_name", sa.String(100), nullable=False),
        sa.Column("start_month", sa.Integer(), nullable=False),
        sa.Column("start_day", sa.Integer(), nullable=False),
        sa.Column("end_month", sa.Integer(), nullable=False),
        sa.Column("end_day", sa.Integer(), nullable=False),
        sa.Column("active_template_ids", JSONB(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("idx_template_seasons_company", "template_seasons", ["company_id"])


def downgrade():
    op.drop_index("idx_template_seasons_company", table_name="template_seasons")
    op.drop_table("template_seasons")
    op.drop_column("quick_quote_templates", "seasonal_only")
