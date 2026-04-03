"""Add proof_contact_ids to legacy_fh_email_config for contact-based recipients.

Revision ID: r46_legacy_fh_contact_ids
Revises: r45_contacts
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r46_legacy_fh_contact_ids"
down_revision = "r45_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "legacy_fh_email_config",
        sa.Column("proof_contact_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("legacy_fh_email_config", "proof_contact_ids")
