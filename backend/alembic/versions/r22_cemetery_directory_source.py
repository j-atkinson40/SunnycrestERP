"""r22 — cemetery directory source tracking

Revision ID: r22_cemetery_directory_source
Revises: r21_quick_create
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r22_cemetery_directory_source"
down_revision = "r21_quick_create"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cemetery_directory",
        sa.Column("source", sa.String(20), nullable=False, server_default="google_places"),
    )
    op.add_column(
        "cemetery_directory",
        sa.Column("osm_id", sa.String(50), nullable=True),
    )


def downgrade():
    op.drop_column("cemetery_directory", "osm_id")
    op.drop_column("cemetery_directory", "source")
