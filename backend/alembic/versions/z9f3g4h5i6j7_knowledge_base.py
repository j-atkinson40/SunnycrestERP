"""Knowledge Base tables: kb_categories, kb_documents, kb_chunks, kb_pricing_entries, kb_extension_notifications

Revision ID: z9f3g4h5i6j7
Revises: z9e2f3g4h5i6
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "z9f3g4h5i6j7"
down_revision = "z9e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("display_order", sa.Integer, server_default="0"),
        sa.Column("is_system", sa.Boolean, server_default="true"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_kb_categories_tenant_slug"),
    )

    op.create_table(
        "kb_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("kb_categories.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_type", sa.String(50), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("raw_content", sa.Text, nullable=True),
        sa.Column("parsed_content", sa.Text, nullable=True),
        sa.Column("parsing_status", sa.String(50), server_default="pending"),
        sa.Column("parsing_error", sa.Text, nullable=True),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("uploaded_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("last_parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_kb_documents_category", "kb_documents", ["category_id"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("kb_categories.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunks_doc_index"),
    )
    op.create_index("ix_kb_chunks_document", "kb_chunks", ["document_id"])

    op.create_table(
        "kb_pricing_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("kb_documents.id"), nullable=True),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("product_code", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("standard_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("contractor_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("homeowner_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit", sa.String(50), server_default="each"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "kb_extension_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("extension_slug", sa.String(100), nullable=False),
        sa.Column("extension_name", sa.String(200), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("briefing_date", sa.Date, nullable=False),
        sa.Column("acknowledged", sa.Boolean, server_default="false"),
    )


def downgrade() -> None:
    op.drop_table("kb_extension_notifications")
    op.drop_table("kb_pricing_entries")
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("kb_categories")
