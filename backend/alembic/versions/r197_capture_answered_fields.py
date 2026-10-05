"""The server decides what is CAPTURED as well as what is missing

Revision ID: r197_capture_answered_fields
Revises: r196_is_manufactured_unestablished
Create Date: 2026-10-05

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Adds one nullable
column. No row is created, deleted, or modified.

THE RULE THIS COMPLETES, which is the reason it is a migration rather than a
refactor.

`The model extracts; the server decides what is missing` (DECISIONS 2026-09-22)
had an unstated half. The server also decides what is **CAPTURED**, and the
client renders both and derives neither. Nothing wrote that down, and the
omission produced exactly what you would predict:

    capture_state.missing       persisted, served, rendered     ✓
    capture_state.answered      computed, written to ONE log
                                line, and DISCARDED             ✗

Having nothing to render for "captured", the client re-derived it — twice, from
raw extraction columns, with two different hardcoded field lists that disagree
with each other and with the template. `ActiveCallCard` names 4 fields,
`ReviewCard` names 10, the template holds 11, and four of ReviewCard's exist
nowhere in the schema. That is not three defects; it is one asymmetry with three
symptoms, and this column removes the class rather than the instances.

⚠️ AND NEITHER CLIENT LIST HAS EVER RENDERED ANYTHING, by a second mechanism
measured 2026-10-05. The client types every extracted field as
`{value, confidence}`; the serializer sends flat strings with one separate
`confidence` dict, and `call-context.tsx:279` assigns the payload raw. So
`extraction.deceased_name?.value` is `undefined` for EVERY field, not only the
four phantom ones. `missing_fields` is `string[]` on both sides and works —
the server-computed set functions and the client-derived set never has.

NULLABLE, NO DEFAULT, AND NOT `[]`.

Per CLAUDE.md §5: a column added to a populated table is nullable unless every
existing row has been shown to satisfy the value. `[]` here would assert "this
call answered nothing", which is false — the truth is that nothing computed an
answered set for rows written before this column existed.

    NULL   no answered set was computed for this row
    []     the capture answered nothing

Measured 2026-10-05: `ringcentral_call_extractions` holds **0 rows on dev**, and
the call overlay has **no production entrance** — RingCentral has no OAuth
initiation anywhere, so nothing can have written an extraction there either.
⚠️ That is an argument from the absent writer, not a production row count; a
production count was not taken. The distinction is kept because it is the whole
reason the column is nullable rather than defaulted: nullable is correct whether
or not legacy rows exist, and a default would be a claim about rows I have not
counted.

JSONB, matching the sibling `missing_fields` on the same table rather than
introducing a second representation for the same shape.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r197_capture_answered_fields"
down_revision = "r196_is_manufactured_unestablished"
branch_labels = None
depends_on = None

_TABLE = "ringcentral_call_extractions"
_COLUMN = "answered_fields"


def upgrade() -> None:
    bind = op.get_bind()

    # ⚠️ POSITIVE CONTROL, READ BEFORE THE WRITE. The sibling must be present and
    # JSONB: this column's whole justification is symmetry with `missing_fields`,
    # and if that column is not what this migration believes it is, the premise
    # is wrong rather than the step being merely unnecessary.
    sibling = bind.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = 'missing_fields'"
        ),
        {"t": _TABLE},
    ).scalar_one_or_none()
    assert sibling == "jsonb", (
        f"{_TABLE}.missing_fields is {sibling!r}, not jsonb — this migration adds "
        f"its symmetric counterpart and the premise does not hold"
    )

    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # ⚠️ ASSERT WHAT WAS ACTUALLY CREATED, not that the call returned. `op.add_column`
    # is monkey-patched idempotent by `alembic/env.py`, so a no-op and a success are
    # indistinguishable from the call alone.
    created = bind.execute(
        sa.text(
            "SELECT data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": _TABLE, "c": _COLUMN},
    ).one_or_none()
    assert created is not None, f"{_TABLE}.{_COLUMN} was not created"
    assert created.data_type == "jsonb", f"expected jsonb, got {created.data_type!r}"
    assert created.is_nullable == "YES", "the column must be nullable — see docstring"
    assert created.column_default is None, (
        f"the column acquired default {created.column_default!r}; a default would "
        f"assert an answered set for rows nothing computed one for"
    )


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
