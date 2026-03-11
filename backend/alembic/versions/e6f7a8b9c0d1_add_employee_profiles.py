"""Add employee profiles

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            unique=True,
            nullable=False,
        ),
        # Professional
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("hire_date", sa.Date, nullable=True),
        # Address
        sa.Column("address_street", sa.String(255), nullable=True),
        sa.Column("address_city", sa.String(100), nullable=True),
        sa.Column("address_state", sa.String(50), nullable=True),
        sa.Column("address_zip", sa.String(20), nullable=True),
        # Emergency contact
        sa.Column("emergency_contact_name", sa.String(200), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(30), nullable=True),
        # Admin-only
        sa.Column("notes", sa.Text, nullable=True),
        # Timestamps
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
    op.create_index("ix_employee_profiles_user_id", "employee_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_employee_profiles_user_id", table_name="employee_profiles")
    op.drop_table("employee_profiles")
