"""merge_billing_groups

Revision ID: aa8e8fe9eb0a
Revises: r55_name_suggestions, z8a9b0c1d2e3
Create Date: 2026-04-06 11:41:41.143796

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa8e8fe9eb0a'
down_revision: Union[str, None] = ('r55_name_suggestions', 'z8a9b0c1d2e3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
