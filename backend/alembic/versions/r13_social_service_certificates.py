"""Add social_service_certificates table.

Revision ID: r13_social_service_certificates
Revises: r12_urn_catalog_ingestion
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa

revision = "r13_social_service_certificates"
down_revision = "r12_urn_catalog_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_service_certificates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("certificate_number", sa.String(100), unique=True, nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_approval"),
        sa.Column("pdf_r2_key", sa.String(500), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent_to", sa.String(255), nullable=True),
    )
    op.create_index("ix_social_service_certificates_status", "social_service_certificates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_social_service_certificates_status", table_name="social_service_certificates")
    op.drop_table("social_service_certificates")
