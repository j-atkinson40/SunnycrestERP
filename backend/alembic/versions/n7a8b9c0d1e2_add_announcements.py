"""add announcements

Revision ID: n7a8b9c0d1e2
Revises: n6a7b8c9d0e1
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "n7a8b9c0d1e2"
down_revision: Union[str, None] = "n6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create announcements table
    op.create_table(
        "announcements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "priority", sa.String(20), nullable=False, server_default="info"
        ),
        sa.Column(
            "target_type",
            sa.String(30),
            nullable=False,
            server_default="everyone",
        ),
        sa.Column("target_value", sa.String(200), nullable=True),
        sa.Column("target_employee_ids", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("pin_to_top", sa.Boolean(), default=False),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=True
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

    # Create announcement_reads table
    op.create_table(
        "announcement_reads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "announcement_id",
            sa.String(36),
            sa.ForeignKey("announcements.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "dismissed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.UniqueConstraint(
            "announcement_id",
            "user_id",
            name="uq_announcement_reads_ann_user",
        ),
    )

    # Add can_create_announcements to employee_profiles
    op.add_column(
        "employee_profiles",
        sa.Column(
            "can_create_announcements",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("employee_profiles", "can_create_announcements")
    op.drop_table("announcement_reads")
    op.drop_table("announcements")
