"""Add legacy delivery settings and print shop contacts.

Revision ID: r41_legacy_settings
Revises: r40_legacy_studio
"""

from alembic import op
import sqlalchemy as sa

revision = "r41_legacy_settings"
down_revision = "r40_legacy_studio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("print_deadline_days_before", sa.Integer, server_default="1"),
        sa.Column("watermark_enabled", sa.Boolean, server_default="false"),
        sa.Column("watermark_text", sa.String(200), server_default="PROOF"),
        sa.Column("watermark_opacity", sa.Numeric(3, 2), server_default="0.30"),
        sa.Column("watermark_position", sa.String(20), server_default="center"),
        sa.Column("tif_filename_template", sa.String(500), server_default="'{print_name} - {name}.tif'"),
        sa.Column("dropbox_connected", sa.Boolean, server_default="false"),
        sa.Column("dropbox_access_token", sa.Text, nullable=True),
        sa.Column("dropbox_refresh_token", sa.Text, nullable=True),
        sa.Column("dropbox_target_folder", sa.String(500), nullable=True),
        sa.Column("dropbox_auto_save", sa.Boolean, server_default="false"),
        sa.Column("gdrive_connected", sa.Boolean, server_default="false"),
        sa.Column("gdrive_access_token", sa.Text, nullable=True),
        sa.Column("gdrive_refresh_token", sa.Text, nullable=True),
        sa.Column("gdrive_folder_id", sa.String(200), nullable=True),
        sa.Column("gdrive_folder_name", sa.String(500), nullable=True),
        sa.Column("gdrive_auto_save", sa.Boolean, server_default="false"),
        sa.Column("print_shop_delivery", sa.String(20), server_default="link"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "legacy_print_shop_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(500), nullable=False),
        sa.Column("is_primary", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("legacy_print_shop_contacts")
    op.drop_table("legacy_settings")
