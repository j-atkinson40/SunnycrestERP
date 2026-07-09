"""C-10 heal — re-assert the f1g2h3i4j5k6 quotes block (edited-after-applied).

Staging's `quotes` table is missing the order-station quotes block that
`f1g2h3i4j5k6_add_quick_quote_templates` adds (10 columns + the customer_id
nullable relax), while the SAME migration's `quick_quote_templates` table
exists — the migration file was edited after staging recorded its revision
(its git history shows a post-creation "fix migration cycle: rename
duplicate revision, fix chain ordering" edit), so alembic considers it
applied and will never re-run it. Consequence witnessed 2026-07-09: every
Quote ORM query 500s on staging (query.count() selects all mapped columns),
QUOTE_AUTO_EXPIRY fails nightly, seed_quotes fails at INSERT.

This heal re-asserts that block VERBATIM behind the same if-not-present
guards (r38-heals-r36 precedent): a NO-OP on any healthy DB (dev,
production-when-healthy, fresh CI), heals staging on the next deploy.

DOWNGRADE IS A DELIBERATE NO-OP. These columns belong canonically to
f1g2h3i4j5k6 — at downgrade time this migration cannot distinguish "column
I added to a stale DB" from "column a healthy DB got from the original",
and dropping would strip healthy databases. One-way heal, like r38.

The durable class-killer rides separately: the boot-time schema-drift
check (app/services/schema_drift.py) fails the deploy loudly if any
model-mapped column is ever missing again.

Revision ID: r124_heal_quotes_quick_quote_columns
Revises: r123_moc_planning_item
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "r124_heal_quotes_quick_quote_columns"
down_revision = "r123_moc_planning_item"
branch_labels = None
depends_on = None


# The f1g2h3i4j5k6 quotes block, verbatim (name → type factory — fresh
# sa.Column per add; Column objects are single-use).
_QUOTES_BLOCK: list[tuple[str, "sa.types.TypeEngine"]] = [
    ("product_line", sa.String(50)),
    ("permit_number", sa.String(100)),
    ("permit_jurisdiction", sa.String(100)),
    ("installation_address", sa.String(500)),
    ("installation_city", sa.String(100)),
    ("installation_state", sa.String(50)),
    ("contact_name", sa.String(200)),
    ("contact_phone", sa.String(50)),
    ("delivery_charge", sa.Numeric(12, 2)),
    ("template_id", sa.String(36)),
    ("customer_name", sa.String(255)),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    quote_cols = {c["name"] for c in inspector.get_columns("quotes")}

    for name, type_ in _QUOTES_BLOCK:
        if name not in quote_cols:
            op.add_column("quotes", sa.Column(name, type_, nullable=True))

    # customer_id nullable relax (walk-in / quick quotes) — guarded on the
    # live nullability so healthy DBs no-op.
    customer_id = next(
        (c for c in inspector.get_columns("quotes") if c["name"] == "customer_id"),
        None,
    )
    if customer_id is not None and not customer_id["nullable"]:
        op.alter_column(
            "quotes", "customer_id",
            existing_type=sa.String(36), nullable=True,
        )


def downgrade() -> None:
    # Deliberate no-op — see module docstring. The columns belong to
    # f1g2h3i4j5k6; dropping here would strip healthy databases.
    pass
