"""Add accounting_connections table.

Revision ID: z6a7b8c9d0e1
Revises: z5a6b7c8d9e0
Create Date: 2026-03-20

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "z6a7b8c9d0e1"
down_revision = "z5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        # Provider: quickbooks_online | quickbooks_desktop | sage_100
        sa.Column("provider", sa.String(50), nullable=False),
        # Status: not_started | connecting | connected | error | disconnected | skipped
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="not_started",
        ),
        # Stage tracking: select_software | connect | configure_sync | complete
        sa.Column("setup_stage", sa.String(30), nullable=True),
        # QBO-specific
        sa.Column("qbo_realm_id", sa.String(50), nullable=True),
        sa.Column("qbo_company_name", sa.String(255), nullable=True),
        sa.Column("qbo_access_token_encrypted", sa.Text, nullable=True),
        sa.Column("qbo_refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column(
            "qbo_token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        # QB Desktop-specific
        sa.Column("qbd_file_id", sa.String(100), nullable=True),
        sa.Column("qbd_qwc_token", sa.String(255), nullable=True),
        sa.Column("qbd_last_poll_at", sa.DateTime(timezone=True), nullable=True),
        # Sage 100-specific
        sa.Column("sage_version", sa.String(20), nullable=True),
        sa.Column(
            "sage_connection_method", sa.String(20), nullable=True
        ),  # api | csv
        sa.Column("sage_api_endpoint", sa.String(500), nullable=True),
        sa.Column("sage_api_key_encrypted", sa.Text, nullable=True),
        sa.Column("sage_csv_schedule", sa.String(20), nullable=True),
        # Sync configuration
        sa.Column("sync_config", JSONB, nullable=True),
        # Account mappings snapshot
        sa.Column("account_mappings", JSONB, nullable=True),
        # Last sync info
        sa.Column(
            "last_sync_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_sync_status", sa.String(30), nullable=True),
        sa.Column("last_sync_error", sa.Text, nullable=True),
        sa.Column("last_sync_records", sa.Integer, nullable=True),
        # Accountant invite
        sa.Column("accountant_email", sa.String(255), nullable=True),
        sa.Column("accountant_token", sa.String(255), nullable=True),
        sa.Column(
            "accountant_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("accountant_name", sa.String(200), nullable=True),
        # Skip tracking
        sa.Column("skip_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        # Who set this up
        sa.Column("connected_by", sa.String(36), nullable=True),
        sa.Column(
            "connected_at", sa.DateTime(timezone=True), nullable=True
        ),
        # Standard timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("accounting_connections")
