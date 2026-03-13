"""Add vendor tables

Revision ID: r2l3m4n5o6p7
Revises: q1k2l3m4n5o6
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "r2l3m4n5o6p7"
down_revision = "q1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- vendors table ---
    op.create_table(
        "vendors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
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
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        # Core
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("fax", sa.String(30), nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        # Address
        sa.Column("address_line1", sa.String(200), nullable=True),
        sa.Column("address_line2", sa.String(200), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(100), nullable=True, server_default="US"),
        # Purchasing info
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column(
            "vendor_status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("minimum_order", sa.Numeric(12, 2), nullable=True),
        # Other
        sa.Column("tax_id", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Sage
        sa.Column("sage_vendor_id", sa.String(50), nullable=True),
        # Constraints
        sa.UniqueConstraint(
            "account_number", "company_id", name="uq_vendor_account_company"
        ),
    )

    # --- vendor_contacts table ---
    op.create_table(
        "vendor_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="0"),
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

    # --- vendor_notes table ---
    op.create_table(
        "vendor_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "note_type",
            sa.String(20),
            nullable=False,
            server_default="general",
        ),
        sa.Column("content", sa.Text(), nullable=False),
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
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
    )

    # Enable "purchasing" module for all existing companies
    op.execute(
        """
        INSERT INTO company_modules (id, company_id, module, enabled, created_at, updated_at)
        SELECT
            gen_random_uuid()::varchar,
            c.id,
            'purchasing',
            true,
            now(),
            now()
        FROM companies c
        WHERE NOT EXISTS (
            SELECT 1 FROM company_modules cm
            WHERE cm.company_id = c.id AND cm.module = 'purchasing'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM company_modules WHERE module = 'purchasing'")
    op.drop_table("vendor_notes")
    op.drop_table("vendor_contacts")
    op.drop_table("vendors")
