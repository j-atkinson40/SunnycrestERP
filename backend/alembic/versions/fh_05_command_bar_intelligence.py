"""Command Bar Intelligence — document search index, history, overlay_config."""

from alembic import op
import sqlalchemy as sa


revision = "fh_05_command_bar_intelligence"
down_revision = "fh_04_workflow_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. document_search_index — unified search across content types
    op.create_table(
        "document_search_index",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("vault_documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("content_source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_chunks", sa.JSON, nullable=False),
        sa.Column("full_text", sa.Text, nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index(
        "ix_document_search_company",
        "document_search_index",
        ["company_id", "content_source"],
    )
    op.create_index("ix_document_search_source", "document_search_index", ["source_id"])

    # PostgreSQL tsvector + GIN index for fast full-text search.
    # Wrapped in try/except DO blocks so SQLite or other backends don't crash.
    op.execute(
        """
        ALTER TABLE document_search_index
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english',
                coalesce(title, '') || ' ' ||
                coalesce(full_text, ''))
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_document_search_fts ON document_search_index USING GIN (search_vector)"
    )

    # 2. command_bar_history — recent items + pre-fill context
    op.create_table(
        "command_bar_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("result_type", sa.String(50), nullable=False),
        sa.Column("result_id", sa.String(36), nullable=True),
        sa.Column("result_title", sa.String(255), nullable=False),
        sa.Column("query_text", sa.String(500), nullable=True),
        sa.Column("context_data", sa.JSON, nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_command_bar_history_user", "command_bar_history", ["user_id", "used_at"])

    # 3. workflows.overlay_config — command bar overlay layout
    op.add_column("workflows", sa.Column("overlay_config", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("workflows", "overlay_config")
    op.drop_index("ix_command_bar_history_user", table_name="command_bar_history")
    op.drop_table("command_bar_history")
    op.execute("DROP INDEX IF EXISTS ix_document_search_fts")
    op.drop_index("ix_document_search_source", table_name="document_search_index")
    op.drop_index("ix_document_search_company", table_name="document_search_index")
    op.drop_table("document_search_index")
