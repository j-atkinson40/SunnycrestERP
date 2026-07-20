"""Audit #2 KILL 3 — document numbers made collision-safe.

UNIQUE (company_id, number) on quotes, sales_orders, invoices — the loud
backstop under the new atomic allocator (advisory-locked, numeric-max).
Dev + staging censused clean of duplicates before cutting. Reversible.

Revision ID: r138_document_number_unique
Revises: r137_composition_kinds
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa

revision = "r138_document_number_unique"
down_revision = "r137_composition_kinds"
branch_labels = None
depends_on = None

_TABLES = ("quotes", "sales_orders", "invoices")


def upgrade() -> None:
    conn = op.get_bind()
    # PRE-STEP — deterministic dedupe (staging census found 4 testco
    # invoice pairs: the LIVE collision the old allocator produced — the
    # 18:00 batch re-issued seed-taken numbers). The EARLIEST row keeps
    # its number; later duplicates get a -DUP{n} suffix. Censused.
    for t in _TABLES:
        renamed = conn.execute(sa.text(f"""
            WITH d AS (
                SELECT id, number,
                       ROW_NUMBER() OVER (PARTITION BY company_id, number
                                          ORDER BY created_at, id) AS rn
                FROM {t}
            )
            UPDATE {t} SET number = {t}.number || '-DUP' || d.rn
            FROM d WHERE d.id = {t}.id AND d.rn > 1
        """)).rowcount
        print(f"[r138 census] {t}: {renamed} duplicate number(s) renamed")
    for t in _TABLES:
        op.create_index(f"ux_{t}_company_number", t, ["company_id", "number"],
                        unique=True)


def downgrade() -> None:
    for t in _TABLES:
        op.drop_index(f"ux_{t}_company_number", table_name=t)
