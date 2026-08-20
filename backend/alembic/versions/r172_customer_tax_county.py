"""TAX-3 — the operator's answer for a ZIP that cannot give one.

⚠️ 22 ZIP CODES IN SUNNYCREST'S OWN TWELVE COUNTIES DO NOT DETERMINE A RATE.
Measured against New York State's ZIP→County cross-reference (data.ny.gov
`juva-r6g2`): 57 ZIPs span two or more of the twelve, and 22 of those touch
Oneida (8.75%) or Ontario (7.5%) — the only two of the twelve that are not 8%.
For a customer in one of those, a ZIP lookup returns whichever county the source
assigned and is wrong for roughly half the customers in that ZIP, by 0.5 to 0.75
points, in both directions, on every order they ever place.

New York says so itself in Publication 718: *"the use of ZIP codes for tax
collection results in a high degree of inaccurate tax reporting."* What the
measurement adds is that this is not distant-metro caution — it lands in the
tenant's home territory.

This column is the escape hatch that makes refusing tolerable. Resolution order
becomes:

    explicit tax_county  →  cemetery county  →  unambiguous ZIP  →  UNRESOLVED

Filling every ambiguous ZIP in with a guess was the option rejected: it writes a
known-wrong answer into a table that looks authoritative. Refusing is the shape
this codebase already uses — `require_resolution=True` raises rather than
defaulting to zero, and an exemption flag without a certificate resolves TAXABLE
with the gap listed. "I cannot determine this" is already a first-class answer
here.

NULLABLE AND NO BACKFILL, and the measurement says why: production has zero
customers with a ZIP at all, so there is nothing to disambiguate yet. NULL is a
true statement about every existing row rather than a placeholder.

Deliberately NOT a FK to anything. The counties live in `platform_tax_rates` and
in two data files; pointing at any one of them would make the operator's
correction depend on a row the platform owns, and the whole point of this column
is that it is the human's answer when the data cannot give one.

Revision ID: r172_customer_tax_county
Revises: r171_platform_tax_rates
"""

import sqlalchemy as sa
from alembic import op

revision = "r172_customer_tax_county"
down_revision = "r171_platform_tax_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive and idempotent via env.py's op.add_column wrapper.
    op.add_column(
        "customers",
        sa.Column("tax_county", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "tax_county")
