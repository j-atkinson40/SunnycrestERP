"""Add funeral home directory tables for manufacturer customer onboarding.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "c3d4e5f6g7h8"
down_revision = "e8f9g0h1i2j3"
branch_labels = None
depends_on = None


def _get_tables(conn) -> list[str]:
    inspector = sa_inspect(conn)
    return inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_tables(conn)

    # ── funeral_home_directory (platform-level, no tenant_id) ──
    if "funeral_home_directory" not in tables:
        op.create_table(
            "funeral_home_directory",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("place_id", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("address", sa.String(500), nullable=True),
            sa.Column("city", sa.String(100), nullable=True),
            sa.Column("state_code", sa.String(2), nullable=True),
            sa.Column("zip_code", sa.String(10), nullable=True),
            sa.Column("county_fips", sa.String(5), nullable=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("website", sa.String(500), nullable=True),
            sa.Column("google_rating", sa.Numeric(3, 2), nullable=True),
            sa.Column("google_review_count", sa.Integer, nullable=True),
            sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
            sa.Column("longitude", sa.Numeric(11, 7), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean,
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "linked_tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=True,
            ),
            sa.Column(
                "first_fetched_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "last_verified_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_fh_directory_place_id",
            "funeral_home_directory",
            ["place_id"],
            unique=True,
        )

    # ── directory_fetch_log ──
    if "directory_fetch_log" not in tables:
        op.create_table(
            "directory_fetch_log",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("fetch_type", sa.String(20), nullable=False),
            sa.Column("county_fips", sa.String(5), nullable=True),
            sa.Column("center_lat", sa.Numeric(10, 7), nullable=True),
            sa.Column("center_lng", sa.Numeric(11, 7), nullable=True),
            sa.Column("radius_miles", sa.Integer, nullable=True),
            sa.Column(
                "results_count",
                sa.Integer,
                server_default=sa.text("0"),
                nullable=False,
            ),
            sa.Column(
                "fetched_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "fetched_for_tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
        )

    # ── manufacturer_directory_selections ──
    if "manufacturer_directory_selections" not in tables:
        op.create_table(
            "manufacturer_directory_selections",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "directory_entry_id",
                sa.String(36),
                sa.ForeignKey("funeral_home_directory.id"),
                nullable=False,
            ),
            sa.Column("action", sa.String(20), nullable=False),
            sa.Column("customer_id", sa.String(36), nullable=True),
            sa.Column("invitation_id", sa.String(36), nullable=True),
            sa.Column(
                "actioned_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # ── extension_customer_onboarding ──
    if "extension_customer_onboarding" not in tables:
        op.create_table(
            "extension_customer_onboarding",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("extension_key", sa.String(100), nullable=False),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="not_started",
            ),
            sa.Column("customer_types_covered", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    op.drop_table("extension_customer_onboarding")
    op.drop_table("manufacturer_directory_selections")
    op.drop_table("directory_fetch_log")
    op.drop_index("ix_fh_directory_place_id", table_name="funeral_home_directory")
    op.drop_table("funeral_home_directory")
