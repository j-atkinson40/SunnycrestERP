"""r23 — add cemetery fields to quotes

Revision ID: r23_quote_cemetery
Revises: r22_cemetery_directory_source
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r23_quote_cemetery"
down_revision = "r22_cemetery_directory_source"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "quotes",
        sa.Column(
            "cemetery_id",
            sa.String(36),
            sa.ForeignKey("cemeteries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "quotes",
        sa.Column("cemetery_name", sa.String(200), nullable=True),
    )
    op.create_index(
        "idx_quotes_cemetery",
        "quotes",
        ["cemetery_id"],
        postgresql_where=sa.text("cemetery_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("idx_quotes_cemetery", table_name="quotes")
    op.drop_column("quotes", "cemetery_name")
    op.drop_column("quotes", "cemetery_id")
