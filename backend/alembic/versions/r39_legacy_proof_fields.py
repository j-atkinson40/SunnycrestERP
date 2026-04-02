"""Add legacy proof fields to order_personalization_tasks.

Revision ID: r39_legacy_proof_fields
Revises: r38_personalization_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r39_legacy_proof_fields"
down_revision = "r38_personalization_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_personalization_tasks", sa.Column("proof_url", sa.Text, nullable=True))
    op.add_column("order_personalization_tasks", sa.Column("tif_url", sa.Text, nullable=True))
    op.add_column("order_personalization_tasks", sa.Column("default_layout", JSONB, nullable=True))
    op.add_column("order_personalization_tasks", sa.Column("approved_layout", JSONB, nullable=True))
    op.add_column("order_personalization_tasks", sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("order_personalization_tasks", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("order_personalization_tasks", "approved_at")
    op.drop_column("order_personalization_tasks", "approved_by")
    op.drop_column("order_personalization_tasks", "approved_layout")
    op.drop_column("order_personalization_tasks", "default_layout")
    op.drop_column("order_personalization_tasks", "tif_url")
    op.drop_column("order_personalization_tasks", "proof_url")
