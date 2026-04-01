"""Add personalization scheduling gate setting.

Revision ID: r38_personalization_settings
Revises: r37_vault_personalization
"""

from alembic import op
import sqlalchemy as sa

revision = "r38_personalization_settings"
down_revision = "r37_vault_personalization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_settings",
        sa.Column("require_personalization_complete", sa.Boolean, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("delivery_settings", "require_personalization_complete")
