"""Add cremation tracking fields to fh_cases and cannot_disable to extension_definitions.

Revision ID: z3a4b5c6d7e8
Revises: y2z3a4b5c6d7
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "z3a4b5c6d7e8"
down_revision = "y2z3a4b5c6d7"
branch_labels = None
depends_on = None


def _get_columns(conn, table_name: str) -> list[str]:
    inspector = sa_inspect(conn)
    return [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    conn = op.get_bind()

    # ── fh_cases: cremation tracking columns ──
    fh_cols = _get_columns(conn, "fh_cases")

    if "cremation_authorization_status" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_authorization_status", sa.String(20), nullable=True))
    if "cremation_authorization_signed_at" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_authorization_signed_at", sa.DateTime(timezone=True), nullable=True))
    if "cremation_authorization_signed_by" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_authorization_signed_by", sa.String(255), nullable=True))
    if "cremation_scheduled_date" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_scheduled_date", sa.Date, nullable=True))
    if "cremation_completed_date" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_completed_date", sa.Date, nullable=True))
    if "remains_disposition" not in fh_cols:
        op.add_column("fh_cases", sa.Column("remains_disposition", sa.String(30), nullable=True))
    if "remains_released_at" not in fh_cols:
        op.add_column("fh_cases", sa.Column("remains_released_at", sa.DateTime(timezone=True), nullable=True))
    if "remains_released_to" not in fh_cols:
        op.add_column("fh_cases", sa.Column("remains_released_to", sa.Text, nullable=True))
    if "cremation_provider" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_provider", sa.Text, nullable=True))
    if "cremation_provider_case_number" not in fh_cols:
        op.add_column("fh_cases", sa.Column("cremation_provider_case_number", sa.String(100), nullable=True))

    # ── extension_definitions: cannot_disable ──
    ext_cols = _get_columns(conn, "extension_definitions")

    if "cannot_disable" not in ext_cols:
        op.add_column("extension_definitions", sa.Column("cannot_disable", sa.Boolean, server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("extension_definitions", "cannot_disable")

    op.drop_column("fh_cases", "cremation_provider_case_number")
    op.drop_column("fh_cases", "cremation_provider")
    op.drop_column("fh_cases", "remains_released_to")
    op.drop_column("fh_cases", "remains_released_at")
    op.drop_column("fh_cases", "remains_disposition")
    op.drop_column("fh_cases", "cremation_completed_date")
    op.drop_column("fh_cases", "cremation_scheduled_date")
    op.drop_column("fh_cases", "cremation_authorization_signed_by")
    op.drop_column("fh_cases", "cremation_authorization_signed_at")
    op.drop_column("fh_cases", "cremation_authorization_status")
