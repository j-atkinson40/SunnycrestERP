"""Add employee track columns for two-track model.

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-20 12:00:00.000000+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("users", "track"):
        op.add_column(
            "users",
            sa.Column(
                "track",
                sa.String(30),
                nullable=False,
                server_default="office_management",
            ),
        )

    if not _column_exists("users", "username"):
        op.add_column(
            "users",
            sa.Column("username", sa.String(50), nullable=True),
        )

    if not _column_exists("users", "pin_encrypted"):
        op.add_column(
            "users",
            sa.Column("pin_encrypted", sa.String(255), nullable=True),
        )

    if not _column_exists("users", "pin_set_at"):
        op.add_column(
            "users",
            sa.Column("pin_set_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists("users", "console_access"):
        op.add_column(
            "users",
            sa.Column("console_access", JSONB, nullable=True),
        )

    if not _column_exists("users", "idle_timeout_minutes"):
        op.add_column(
            "users",
            sa.Column(
                "idle_timeout_minutes",
                sa.Integer,
                nullable=True,
                server_default="30",
            ),
        )

    if not _column_exists("users", "last_console_login_at"):
        op.add_column(
            "users",
            sa.Column(
                "last_console_login_at", sa.DateTime(timezone=True), nullable=True
            ),
        )

    # Partial unique index: username must be unique per tenant (where not null)
    conn = op.get_bind()
    idx_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE indexname = 'uq_users_username_company'"
        )
    ).fetchone()
    if not idx_exists:
        op.execute(
            "CREATE UNIQUE INDEX uq_users_username_company "
            "ON users (company_id, username) WHERE username IS NOT NULL"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_username_company")
    for col in [
        "last_console_login_at",
        "idle_timeout_minutes",
        "console_access",
        "pin_set_at",
        "pin_encrypted",
        "username",
        "track",
    ]:
        if _column_exists("users", col):
            op.drop_column("users", col)
