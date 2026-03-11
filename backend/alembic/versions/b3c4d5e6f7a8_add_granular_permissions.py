"""Add granular permissions system

Revision ID: b3c4d5e6f7a8
Revises: a2f3b4c5d6e7
Create Date: 2026-03-11 12:00:00.000000

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.permissions import EMPLOYEE_DEFAULT_PERMISSIONS

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2f3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create roles table
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system", sa.Boolean(), default=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", "company_id", name="uq_roles_slug_company"),
    )

    # 2. Create role_permissions table
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "role_id",
            sa.String(36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("permission_key", sa.String(100), nullable=False),
        sa.UniqueConstraint(
            "role_id", "permission_key", name="uq_role_permission"
        ),
    )

    # 3. Create user_permission_overrides table
    op.create_table(
        "user_permission_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("permission_key", sa.String(100), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id", "permission_key", name="uq_user_permission_override"
        ),
    )

    # 4. Seed system roles for each existing company
    conn = op.get_bind()
    companies = conn.execute(sa.text("SELECT id FROM companies")).fetchall()

    for (company_id,) in companies:
        admin_role_id = str(uuid.uuid4())
        employee_role_id = str(uuid.uuid4())

        # Create Admin system role
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, company_id, name, slug, description, is_system, is_active, created_at, updated_at) "
                "VALUES (:id, :company_id, :name, :slug, :description, :is_system, :is_active, NOW(), NOW())"
            ),
            {
                "id": admin_role_id,
                "company_id": company_id,
                "name": "Admin",
                "slug": "admin",
                "description": "Full system access",
                "is_system": True,
                "is_active": True,
            },
        )

        # Create Employee system role
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, company_id, name, slug, description, is_system, is_active, created_at, updated_at) "
                "VALUES (:id, :company_id, :name, :slug, :description, :is_system, :is_active, NOW(), NOW())"
            ),
            {
                "id": employee_role_id,
                "company_id": company_id,
                "name": "Employee",
                "slug": "employee",
                "description": "Basic employee access",
                "is_system": True,
                "is_active": True,
            },
        )

        # 5. Seed default permissions for Employee role
        for perm_key in EMPLOYEE_DEFAULT_PERMISSIONS:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (id, role_id, permission_key) "
                    "VALUES (:id, :role_id, :perm_key)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "role_id": employee_role_id,
                    "perm_key": perm_key,
                },
            )

    # 6. Add role_id column to users (nullable initially)
    op.add_column("users", sa.Column("role_id", sa.String(36), nullable=True))

    # 7. Backfill role_id from old role string column
    conn.execute(
        sa.text(
            "UPDATE users u "
            "SET role_id = r.id "
            "FROM roles r "
            "WHERE r.company_id = u.company_id AND r.slug = u.role"
        )
    )

    # 8. Make role_id NOT NULL
    op.alter_column("users", "role_id", nullable=False)

    # 9. Add FK constraint and index
    op.create_foreign_key(
        "fk_users_role_id", "users", "roles", ["role_id"], ["id"]
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])

    # 10. Drop old role column
    op.drop_column("users", "role")


def downgrade() -> None:
    # Re-add the old role string column
    op.add_column(
        "users", sa.Column("role", sa.String(20), nullable=True)
    )

    # Backfill role from roles.slug
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users u "
            "SET role = r.slug "
            "FROM roles r "
            "WHERE r.id = u.role_id"
        )
    )

    op.alter_column("users", "role", nullable=False)

    # Drop role_id FK, index, and column
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "role_id")

    # Drop new tables
    op.drop_table("user_permission_overrides")
    op.drop_table("role_permissions")
    op.drop_table("roles")
