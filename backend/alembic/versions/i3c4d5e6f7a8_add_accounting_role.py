"""Add accounting system role for all existing companies

Revision ID: i3c4d5e6f7a8
Revises: h2b3c4d5e6f7
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision = "i3c4d5e6f7a8"
down_revision = "h2b3c4d5e6f7"
branch_labels = None
depends_on = None

ACCOUNTING_PERMISSIONS = [
    "dashboard.view",
    "products.view",
    "inventory.view",
    "audit.view",
    "company.view",
    "departments.view",
    "employees.view",
]


def upgrade() -> None:
    conn = op.get_bind()
    companies = conn.execute(sa.text("SELECT id FROM companies")).fetchall()

    for (company_id,) in companies:
        # Check if accounting role already exists
        existing = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE company_id = :cid AND slug = 'accounting' AND is_system = true"
            ),
            {"cid": company_id},
        ).fetchone()

        if existing:
            continue

        role_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, company_id, name, slug, description, is_system, is_active) "
                "VALUES (:id, :cid, 'Accounting', 'accounting', "
                "'Read access to financial and operational data', true, true)"
            ),
            {"id": role_id, "cid": company_id},
        )

        for perm_key in ACCOUNTING_PERMISSIONS:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (id, role_id, permission_key) "
                    "VALUES (:id, :rid, :pkey)"
                ),
                {"id": str(uuid.uuid4()), "rid": role_id, "pkey": perm_key},
            )


def downgrade() -> None:
    conn = op.get_bind()
    # Remove accounting role permissions first, then the role
    accounting_roles = conn.execute(
        sa.text("SELECT id FROM roles WHERE slug = 'accounting' AND is_system = true")
    ).fetchall()

    for (role_id,) in accounting_roles:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE role_id = :rid"),
            {"rid": role_id},
        )
        conn.execute(
            sa.text("DELETE FROM roles WHERE id = :rid"),
            {"rid": role_id},
        )
