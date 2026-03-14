"""add api_keys and api_key_usage tables

Revision ID: u5v6w7x8y9z0
Revises: t4n5o6p7q8r9
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = "u5v6w7x8y9z0"
down_revision = "t4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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
    op.create_index("ix_api_keys_company", "api_keys", ["company_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["key_prefix"])

    op.create_table(
        "api_key_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "api_key_id",
            sa.String(36),
            sa.ForeignKey("api_keys.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0"),
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_api_key_usage_key_hour", "api_key_usage", ["api_key_id", "hour_bucket"]
    )


def downgrade() -> None:
    op.drop_table("api_key_usage")
    op.drop_table("api_keys")
