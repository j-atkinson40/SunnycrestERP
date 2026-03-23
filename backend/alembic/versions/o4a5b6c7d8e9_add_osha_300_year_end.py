"""Add OSHA 300 year-end workflow tables and locked entry support.

Revision ID: o4a5b6c7d8e9
Revises: o3a4b5c6d7e8
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op

revision = "o4a5b6c7d8e9"
down_revision = "o3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Year-end workflow records
    op.create_table(
        "osha_300_year_end_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("review_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_completed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("entry_count_at_review", sa.Integer(), nullable=True),
        sa.Column("form_300a_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_300a_file_url", sa.String(500), nullable=True),
        sa.Column("form_300a_certified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("form_300a_certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_300a_certified_name", sa.String(200), nullable=True),
        sa.Column("form_300a_certified_title", sa.String(200), nullable=True),
        sa.Column("posting_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posting_location", sa.String(500), nullable=True),
        sa.Column("posting_period_end_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "year", name="uq_osha_300_year_end_tenant_year"),
    )

    # Add locked/correction columns to osha_300_entries
    op.add_column("osha_300_entries", sa.Column("is_locked", sa.Boolean(), server_default="false"))
    op.add_column("osha_300_entries", sa.Column("correction_notes", sa.Text(), nullable=True))
    op.add_column("osha_300_entries", sa.Column("corrected_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("osha_300_entries", sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("osha_300_entries", "corrected_at")
    op.drop_column("osha_300_entries", "corrected_by")
    op.drop_column("osha_300_entries", "correction_notes")
    op.drop_column("osha_300_entries", "is_locked")
    op.drop_table("osha_300_year_end_records")
