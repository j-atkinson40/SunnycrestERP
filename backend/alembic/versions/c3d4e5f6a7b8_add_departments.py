"""Add departments table and migrate employee_profiles.department → department_id FK.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create departments table
    op.create_table(
        "departments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
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
        sa.UniqueConstraint("name", "company_id", name="uq_department_name_company"),
    )

    # 2. Add department_id column to employee_profiles
    op.add_column(
        "employee_profiles",
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id"), nullable=True),
    )
    op.create_index(
        "ix_employee_profiles_department_id",
        "employee_profiles",
        ["department_id"],
    )

    # 3. Data migration: create department records from existing string values
    conn = op.get_bind()

    # Get distinct (department, company_id) values from employee_profiles
    # We need to join with users to get the company_id
    rows = conn.execute(
        sa.text(
            """
            SELECT DISTINCT ep.department, u.company_id
            FROM employee_profiles ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.department IS NOT NULL AND ep.department != ''
            """
        )
    ).fetchall()

    # Insert department records and collect the mapping
    for row in rows:
        dept_name = row[0]
        company_id = row[1]
        dept_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO departments (id, company_id, name, is_active, created_at, updated_at)
                VALUES (:id, :company_id, :name, true, NOW(), NOW())
                """
            ),
            {"id": dept_id, "company_id": company_id, "name": dept_name},
        )
        # Update employee_profiles that match this department + company
        conn.execute(
            sa.text(
                """
                UPDATE employee_profiles ep
                SET department_id = :dept_id
                FROM users u
                WHERE u.id = ep.user_id
                  AND u.company_id = :company_id
                  AND ep.department = :dept_name
                """
            ),
            {"dept_id": dept_id, "company_id": company_id, "dept_name": dept_name},
        )

    # 4. Drop old department column
    op.drop_column("employee_profiles", "department")


def downgrade() -> None:
    # Re-add department string column
    op.add_column(
        "employee_profiles",
        sa.Column("department", sa.String(100), nullable=True),
    )

    # Migrate data back from department_id to department string
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE employee_profiles ep
            SET department = d.name
            FROM departments d
            WHERE d.id = ep.department_id
            """
        )
    )

    # Remove department_id column and index
    op.drop_index("ix_employee_profiles_department_id", table_name="employee_profiles")
    op.drop_column("employee_profiles", "department_id")

    # Drop departments table
    op.drop_table("departments")
