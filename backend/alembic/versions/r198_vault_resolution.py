"""The vault phrase's resolution, so an ambiguity is not silence

Revision ID: r198_vault_resolution
Revises: r197_capture_answered_fields
Create Date: 2026-10-05

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Adds one nullable
column. No row is created, deleted or modified.

WHAT THIS CLOSES, and it is the oldest open thing in the capture arc.

`resolve_schema` omits the three conditional personalization questions when
`vault_product_id is None`. That argument has been None at every call site since
the field existed, because NOTHING turned a vault NAME into a product id. So the
three questions have never been asked on any call — not intermittently, never —
and `resolve_schema`'s only conditional branch has never executed in this
codebase. The mechanism we spent a morning trying to generalise had never run.

`product_name_resolver` now resolves the phrase, so the branch can execute. This
column is what makes the MIDDLE outcome survive.

⚠️ THREE OUTCOMES, NOT TWO, AND THE MIDDLE ONE IS WHY A COLUMN IS NEEDED:

    one candidate    -> vault_product_id resolves, the conditionals appear
    SEVERAL          -> vault_product_id stays None, AND the capture must surface
                        the discriminator as a question
    no match         -> as before

Without somewhere to put it, the middle case reaches the client as an empty
capture list — indistinguishable from no match, which throws away the entire
reason the resolver returns a set rather than a winner. `{"candidates": [...],
"discriminator": "form"}` is the difference between "we could not find that
vault" and "Bronze Triune — burial or urn?".

NULLABLE, NO DEFAULT. Per CLAUDE.md §5: NULL means no resolution was attempted
for this row, which is true of every row written before this column existed. `{}`
would assert an attempt that produced nothing. Measured 2026-10-05:
`ringcentral_call_extractions` holds 0 rows in dev AND 0 in production (read-only
preflight for r197), so no legacy row exists either way — the nullability is
correct independent of that count, which is why it does not rest on it.

JSONB, matching `missing_fields` and `answered_fields` on the same table rather
than adding a third representation.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r198_vault_resolution"
down_revision = "r197_capture_answered_fields"
branch_labels = None
depends_on = None

_TABLE = "ringcentral_call_extractions"
_COLUMN = "vault_resolution"


def upgrade() -> None:
    bind = op.get_bind()

    # ⚠️ POSITIVE CONTROL BEFORE THE WRITE. The column this one sits beside must
    # be present and jsonb — symmetry with the two existing capture columns is
    # the stated reason for the type, and if that is not what this migration
    # believes, the premise is wrong rather than the step merely unnecessary.
    sibling = bind.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = 'answered_fields'"
        ),
        {"t": _TABLE},
    ).scalar_one_or_none()
    assert sibling == "jsonb", (
        f"{_TABLE}.answered_fields is {sibling!r}, not jsonb — r197 is not applied "
        f"and this migration's premise does not hold"
    )

    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # ⚠️ ASSERT WHAT WAS CREATED, not that the call returned. `op.add_column` is
    # monkey-patched idempotent by `alembic/env.py`, so a no-op and a success are
    # indistinguishable from the call alone.
    got = bind.execute(
        sa.text(
            "SELECT data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": _TABLE, "c": _COLUMN},
    ).one_or_none()
    assert got is not None, f"{_TABLE}.{_COLUMN} was not created"
    assert got.data_type == "jsonb", f"expected jsonb, got {got.data_type!r}"
    assert got.is_nullable == "YES", "must be nullable — see docstring"
    assert got.column_default is None, (
        f"acquired default {got.column_default!r}; a default would assert a "
        f"resolution attempt for rows nothing attempted one for"
    )


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
