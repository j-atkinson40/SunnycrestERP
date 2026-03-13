"""Add documents table for file storage

Revision ID: m7g8h9i0j1k2
Revises: l6f7a8b9c0d1
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "m7g8h9i0j1k2"
down_revision = "l6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("documents")
