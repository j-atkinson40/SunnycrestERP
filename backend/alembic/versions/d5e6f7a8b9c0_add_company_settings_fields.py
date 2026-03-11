"""Add company settings fields

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("address_street", sa.String(255), nullable=True))
    op.add_column("companies", sa.Column("address_city", sa.String(100), nullable=True))
    op.add_column("companies", sa.Column("address_state", sa.String(50), nullable=True))
    op.add_column("companies", sa.Column("address_zip", sa.String(20), nullable=True))
    op.add_column("companies", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("companies", sa.Column("email", sa.String(255), nullable=True))
    op.add_column(
        "companies",
        sa.Column("timezone", sa.String(50), nullable=True, server_default="America/Los_Angeles"),
    )
    op.add_column("companies", sa.Column("logo_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "logo_url")
    op.drop_column("companies", "timezone")
    op.drop_column("companies", "email")
    op.drop_column("companies", "phone")
    op.drop_column("companies", "address_zip")
    op.drop_column("companies", "address_state")
    op.drop_column("companies", "address_city")
    op.drop_column("companies", "address_street")
