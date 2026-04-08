"""Add document_type, r2_key, metadata_json columns to documents table.

Extends the existing documents table to support R2-backed document storage
with typed document classification and structured metadata for intelligence
features (e.g. call overlay invoice lookup).

Revision ID: r9_document_r2
Revises: r8_disinterment_ext
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "r9_document_r2"
down_revision = "r8_disinterment_ext"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("document_type", sa.String(100), nullable=True, index=True),
    )
    op.add_column(
        "documents",
        sa.Column("r2_key", sa.String(500), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    # The idempotent env.py wrappers handle "column already exists" gracefully.


def downgrade() -> None:
    op.drop_column("documents", "metadata_json")
    op.drop_column("documents", "r2_key")
    op.drop_column("documents", "document_type")
