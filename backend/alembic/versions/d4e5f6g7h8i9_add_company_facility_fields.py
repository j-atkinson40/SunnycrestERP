"""Add facility address, geocoding, NPCA, and admin notes fields to companies.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    columns = [
        ("company_legal_name", sa.String(255), None),
        ("facility_address_line1", sa.String(500), None),
        ("facility_address_line2", sa.String(255), None),
        ("facility_city", sa.String(100), None),
        ("facility_state", sa.String(2), None),
        ("facility_zip", sa.String(10), None),
        ("facility_latitude", sa.Numeric(10, 7), None),
        ("facility_longitude", sa.Numeric(11, 7), None),
        ("company_phone", sa.String(20), None),
        ("npca_certification_status", sa.String(30), "unknown"),
        ("npca_certification_set_by", sa.String(30), None),
        ("spring_burials_known_at_creation", sa.Boolean(), False),
        ("internal_admin_notes", sa.Text(), None),
    ]

    for col_name, col_type, default in columns:
        if not _has_column("companies", col_name):
            kwargs = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = str(default).lower() if isinstance(default, bool) else default
            op.add_column("companies", sa.Column(col_name, col_type, **kwargs))


def downgrade() -> None:
    columns = [
        "internal_admin_notes",
        "spring_burials_known_at_creation",
        "npca_certification_set_by",
        "npca_certification_status",
        "company_phone",
        "facility_longitude",
        "facility_latitude",
        "facility_zip",
        "facility_state",
        "facility_city",
        "facility_address_line2",
        "facility_address_line1",
        "company_legal_name",
    ]
    for col_name in columns:
        if _has_column("companies", col_name):
            op.drop_column("companies", col_name)
