"""Add tenant_website_intelligence and website_intelligence_suggestions tables.

Revision ID: e8f9g0h1i2j3
Revises: d7e8f9g0h1i2
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "e8f9g0h1i2j3"
down_revision = "d7e8f9g0h1i2"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa_inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # ── tenant_website_intelligence ──
    if not _table_exists(conn, "tenant_website_intelligence"):
        op.create_table(
            "tenant_website_intelligence",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("website_url", sa.String(500), nullable=False),
            sa.Column(
                "scrape_status",
                sa.String(20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("scrape_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scrape_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw_content", sa.Text, nullable=True),
            sa.Column("pages_scraped", sa.Text, nullable=True),
            sa.Column("analysis_result", sa.Text, nullable=True),
            sa.Column("confidence_scores", sa.Text, nullable=True),
            sa.Column(
                "applied_to_onboarding",
                sa.Boolean,
                server_default=sa.text("false"),
            ),
            sa.Column("tenant_confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("input_tokens", sa.Integer, nullable=True),
            sa.Column("output_tokens", sa.Integer, nullable=True),
            sa.Column("estimated_cost", sa.Numeric(8, 4), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_tenant_website_intelligence_tenant_id",
            "tenant_website_intelligence",
            ["tenant_id"],
            unique=True,
        )

    # ── website_intelligence_suggestions ──
    if not _table_exists(conn, "website_intelligence_suggestions"):
        op.create_table(
            "website_intelligence_suggestions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("suggestion_type", sa.String(30), nullable=False),
            sa.Column("suggestion_key", sa.String(100), nullable=False),
            sa.Column("suggestion_label", sa.String(255), nullable=False),
            sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
            sa.Column("evidence", sa.Text, nullable=True),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_website_intelligence_suggestions_tenant_id",
            "website_intelligence_suggestions",
            ["tenant_id"],
        )


def downgrade() -> None:
    op.drop_table("website_intelligence_suggestions")
    op.drop_table("tenant_website_intelligence")
