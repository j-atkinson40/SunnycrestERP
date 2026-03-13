"""Add company_modules table for module permission system

Revision ID: g1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import uuid
from datetime import datetime, UTC

# revision identifiers, used by Alembic.
revision = "g1a2b3c4d5e6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

# All available modules and their default enabled state
MODULES = {
    "core": True,
    "products": True,
    "inventory": True,
    "hr_time": False,
    "driver_delivery": False,
    "pos": False,
    "project_mgmt": False,
    "analytics": False,
}


def upgrade() -> None:
    # Create company_modules table
    op.create_table(
        "company_modules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint("company_id", "module", name="uq_company_module"),
    )

    # Seed modules for all existing companies
    conn = op.get_bind()
    companies = conn.execute(sa.text("SELECT id FROM companies")).fetchall()
    now = datetime.now(UTC)

    for (company_id,) in companies:
        for module_key, default_enabled in MODULES.items():
            conn.execute(
                sa.text(
                    "INSERT INTO company_modules (id, company_id, module, enabled, created_at, updated_at) "
                    "VALUES (:id, :company_id, :module, :enabled, :created_at, :updated_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "company_id": company_id,
                    "module": module_key,
                    "enabled": default_enabled,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade() -> None:
    op.drop_table("company_modules")
