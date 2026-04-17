"""VaultDocument — native document layer on top of R2 for tenant-facing file access."""

from alembic import op
import sqlalchemy as sa


revision = "vault_08_documents"
down_revision = "fh_03_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vault_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.String(36), nullable=True),
        sa.Column("vault_id", sa.String(36), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("workflow_run_id", sa.String(36), nullable=True),
        sa.Column("is_family_accessible", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by_user_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vault_documents_entity", "vault_documents", ["related_entity_type", "related_entity_id"])
    op.create_index("ix_vault_documents_company", "vault_documents", ["company_id", "document_type"])


def downgrade() -> None:
    op.drop_index("ix_vault_documents_company", table_name="vault_documents")
    op.drop_index("ix_vault_documents_entity", table_name="vault_documents")
    op.drop_table("vault_documents")
