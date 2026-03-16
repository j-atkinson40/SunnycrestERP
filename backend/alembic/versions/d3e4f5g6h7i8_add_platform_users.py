"""Add platform users and impersonation sessions

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2026-03-16 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d3e4f5g6h7i8"
down_revision = "c2d3e4f5g6h7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Platform users — super admins outside tenant scope
    op.create_table(
        "platform_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "email", sa.String(255), unique=True, nullable=False, index=True
        ),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column(
            "role", sa.String(30), nullable=False, server_default="super_admin"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Impersonation sessions — audit trail for platform admin impersonation
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "platform_user_id",
            sa.String(36),
            sa.ForeignKey("platform_users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "impersonated_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "actions_performed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("impersonation_sessions")
    op.drop_table("platform_users")
