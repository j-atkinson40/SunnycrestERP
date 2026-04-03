"""Add legacy email settings and per-FH email config.

Revision ID: r42_legacy_email_settings
Revises: r41_legacy_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r42_legacy_email_settings"
down_revision = "r41_legacy_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_email_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("sender_tier", sa.String(20), server_default="bridgeable"),
        sa.Column("reply_to_email", sa.String(500), nullable=True),
        sa.Column("custom_from_email", sa.String(500), nullable=True),
        sa.Column("custom_from_name", sa.String(200), nullable=True),
        sa.Column("domain_verified", sa.Boolean, server_default="false"),
        sa.Column("resend_domain_id", sa.String(200), nullable=True),
        sa.Column("proof_email_subject", sa.String(500), server_default="'Legacy Proof — {name}'"),
        sa.Column("proof_email_body", sa.Text, nullable=True),
        sa.Column("proof_email_reply_to", sa.String(500), nullable=True),
        sa.Column("print_email_subject", sa.String(500), server_default="'Legacy Ready — {name}, needed by {deadline}'"),
        sa.Column("print_email_body", sa.Text, nullable=True),
        sa.Column("use_invoice_branding", sa.Boolean, server_default="true"),
        sa.Column("header_color", sa.String(7), nullable=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "legacy_fh_email_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("recipients", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("custom_subject", sa.String(500), nullable=True),
        sa.Column("custom_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "customer_id", name="uq_legacy_fh_email_config"),
    )


def downgrade() -> None:
    op.drop_table("legacy_fh_email_config")
    op.drop_table("legacy_email_settings")
