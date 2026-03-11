"""add multi-tenancy with companies

Revision ID: a2f3b4c5d6e7
Revises: e1e2120b6b65
Create Date: 2026-03-11 00:00:00.000000

"""

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2f3b4c5d6e7"
down_revision: Union[str, None] = "e1e2120b6b65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_slug", "companies", ["slug"], unique=True)

    # 2. Insert a default company for any existing users
    default_company_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    op.execute(
        sa.text(
            "INSERT INTO companies (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :slug, true, :now, :now)"
        ).bindparams(
            id=default_company_id,
            name="Default Company",
            slug="default",
            now=now,
        )
    )

    # 3. Add company_id column as nullable first
    op.add_column("users", sa.Column("company_id", sa.String(length=36), nullable=True))

    # 4. Backfill all existing users with the default company
    op.execute(
        sa.text("UPDATE users SET company_id = :company_id").bindparams(
            company_id=default_company_id
        )
    )

    # 5. Make company_id NOT NULL
    op.alter_column("users", "company_id", nullable=False)

    # 6. Add foreign key constraint
    op.create_foreign_key(
        "fk_users_company_id", "users", "companies", ["company_id"], ["id"]
    )

    # 7. Drop old unique email index, create non-unique index + composite unique
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_unique_constraint(
        "uq_users_email_company", "users", ["email", "company_id"]
    )

    # 8. Index on company_id for tenant-scoped queries
    op.create_index("ix_users_company_id", "users", ["company_id"])


def downgrade() -> None:
    # Remove company_id index
    op.drop_index("ix_users_company_id", table_name="users")

    # Remove composite unique constraint
    op.drop_constraint("uq_users_email_company", "users", type_="unique")

    # Restore unique email index
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Remove FK and column
    op.drop_constraint("fk_users_company_id", "users", type_="foreignkey")
    op.drop_column("users", "company_id")

    # Drop companies table
    op.drop_index("ix_companies_slug", table_name="companies")
    op.drop_table("companies")
