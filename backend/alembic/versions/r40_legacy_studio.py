"""Add Legacy Studio tables — legacy_proofs, legacy_proof_versions, legacy_proof_photos.

Revision ID: r40_legacy_studio
Revises: r39_legacy_proof_fields
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r40_legacy_studio"
down_revision = "r39_legacy_proof_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_proofs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True),
        sa.Column("personalization_task_id", sa.String(36), nullable=True),
        sa.Column("legacy_type", sa.String(20), nullable=False),
        sa.Column("print_name", sa.String(200), nullable=True),
        sa.Column("is_urn", sa.Boolean, server_default="false"),
        sa.Column("inscription_name", sa.Text, nullable=True),
        sa.Column("inscription_dates", sa.Text, nullable=True),
        sa.Column("inscription_additional", sa.Text, nullable=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("deceased_name", sa.Text, nullable=True),
        sa.Column("service_date", sa.Date, nullable=True),
        sa.Column("approved_layout", JSONB, nullable=True),
        sa.Column("proof_url", sa.Text, nullable=True),
        sa.Column("tif_url", sa.Text, nullable=True),
        sa.Column("background_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), server_default="draft"),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("family_approved", sa.Boolean, server_default="false"),
        sa.Column("proof_emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proof_emailed_to", JSONB, nullable=True),
        sa.Column("watermarked", sa.Boolean, server_default="false"),
        sa.Column("watermark_text", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_legacy_proofs_company", "legacy_proofs", ["company_id"])
    op.create_index("idx_legacy_proofs_customer", "legacy_proofs", ["customer_id"], postgresql_where=sa.text("customer_id IS NOT NULL"))
    op.create_index("idx_legacy_proofs_order", "legacy_proofs", ["order_id"], postgresql_where=sa.text("order_id IS NOT NULL"))
    op.create_index("idx_legacy_proofs_status", "legacy_proofs", ["company_id", "status"])

    op.create_table(
        "legacy_proof_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("legacy_proof_id", sa.String(36), sa.ForeignKey("legacy_proofs.id"), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("approved_layout", JSONB, nullable=True),
        sa.Column("proof_url", sa.Text, nullable=True),
        sa.Column("tif_url", sa.Text, nullable=True),
        sa.Column("inscription_name", sa.Text, nullable=True),
        sa.Column("inscription_dates", sa.Text, nullable=True),
        sa.Column("inscription_additional", sa.Text, nullable=True),
        sa.Column("print_name", sa.String(200), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("kept", sa.Boolean, server_default="true"),
    )
    op.create_index("idx_legacy_versions_proof", "legacy_proof_versions", ["legacy_proof_id"])

    op.create_table(
        "legacy_proof_photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("legacy_proof_id", sa.String(36), sa.ForeignKey("legacy_proofs.id"), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("legacy_proof_photos")
    op.drop_index("idx_legacy_versions_proof", table_name="legacy_proof_versions")
    op.drop_table("legacy_proof_versions")
    op.drop_index("idx_legacy_proofs_status", table_name="legacy_proofs")
    op.drop_index("idx_legacy_proofs_order", table_name="legacy_proofs")
    op.drop_index("idx_legacy_proofs_customer", table_name="legacy_proofs")
    op.drop_index("idx_legacy_proofs_company", table_name="legacy_proofs")
    op.drop_table("legacy_proofs")
