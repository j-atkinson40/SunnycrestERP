"""Add driver portal visibility settings to delivery_settings.

Revision ID: r36_driver_portal_settings
Revises: r35_training_progress
"""

from alembic import op
import sqlalchemy as sa

revision = "r36_driver_portal_settings"
down_revision = "r35_training_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_settings", sa.Column("show_en_route_button", sa.Boolean, server_default="true"))
    op.add_column("delivery_settings", sa.Column("show_exception_button", sa.Boolean, server_default="true"))
    op.add_column("delivery_settings", sa.Column("show_delivered_button", sa.Boolean, server_default="true"))
    op.add_column("delivery_settings", sa.Column("show_equipment_checklist", sa.Boolean, server_default="false"))
    op.add_column("delivery_settings", sa.Column("show_funeral_home_contact", sa.Boolean, server_default="true"))
    op.add_column("delivery_settings", sa.Column("show_cemetery_contact", sa.Boolean, server_default="true"))
    op.add_column("delivery_settings", sa.Column("show_get_directions", sa.Boolean, server_default="true"))
    op.add_column("delivery_settings", sa.Column("show_call_office_button", sa.Boolean, server_default="true"))


def downgrade() -> None:
    op.drop_column("delivery_settings", "show_call_office_button")
    op.drop_column("delivery_settings", "show_get_directions")
    op.drop_column("delivery_settings", "show_cemetery_contact")
    op.drop_column("delivery_settings", "show_funeral_home_contact")
    op.drop_column("delivery_settings", "show_equipment_checklist")
    op.drop_column("delivery_settings", "show_delivered_button")
    op.drop_column("delivery_settings", "show_exception_button")
    op.drop_column("delivery_settings", "show_en_route_button")
