"""Extraction columns for order capture part 1 — R1/R3/R4.

⚠️ EXPAND-ONLY, NULLABLE, NO DEFAULT. Five columns added, nothing renamed, nothing
dropped, nothing backfilled. Every existing row keeps NULL on all five, which is the
honest value: NULL means NOT ESTABLISHED, and nobody has measured a service date or a
personalization answer for any call that has already happened.

⚠️ AND THE NO-DEFAULT PART IS THE LOAD-BEARING HALF, per CLAUDE.md §5. A
`server_default` here would write a value onto every pre-existing row — the same false
assertion `products.is_manufactured` made with `false` (r196) and
`product_templates.personalization_capability` made with a literal `[]` (r188). Both
read as data. `personalization` defaulting to `'none'` would read as data too, and
would claim that every historical call declined personalization. It is nullable and
the rows stay NULL.

⚠️ THE TABLE IS EMPTY IN BOTH ENVIRONMENTS AND THAT IS NOT THE REASON THIS IS SAFE.
`ringcentral_call_extractions` held 0 rows in dev and 0 in production when measured
2026-10-05, so no row is touched either way. The nullable-no-default discipline is
applied because the NEXT migration against this table may not be so lucky, and a
reader copying this one should copy the correct shape.

WHAT EACH COLUMN IS FOR

    service_date              R4. REQUIRED on the capture template. Distinct from
                              `burial_date`, which already exists — a service at a
                              church in the morning and a burial later are two facts,
                              the same distinction the `burial_time` -> `service_time`
                              rename made for times in r199.
    cemetery_city             R4. Prompted, not required. Cemeteries share names
                              across towns.
    personalization           R1. THE ONE ANSWER, replacing three questions. One of
                              `none | legacy_print | nameplate_only |
                              nameplate_and_cover_emblem | cover_emblem_only |
                              lifes_reflections | nameplate_and_lifes_reflections`.
    legacy_print_name         R3. WHICH print the director named, verbatim as spoken.
                              Resolved against the print list by a resolver that
                              returns candidates; this column holds the phrase, never
                              the resolution.
    lifes_reflections_symbol  Which vinyl symbol. ⚠️ NOT FROM A RULING — R1 collapsed
                              the eight symbols from answers into one answer, so
                              without this the symbol a family chose has nowhere to
                              land. Flagged for James in the report.

⚠️ NO CHECK CONSTRAINT ON `personalization`, DELIBERATELY AND CONSISTENTLY WITH r199.
`service_location` took a `String(20)` with no CHECK for the same reason: the
vocabulary lives in `schema.py` where the conditions that compare against it live, and
`test_piece4_conditionals` asserts every literal any condition uses is a member of it.
A database CHECK is a separate decision; taking it here would put the vocabulary in
two places.

⚠️ NO COLUMN FOR `nameplate_date_format`. It is a template field with no extraction
column, which means it can never be answered from a call — a real gap, pre-existing,
and already reported by `orphan_field_ids` as one of the two declared orphans. Adding
a column would imply the extractor can hear a lettering preference off a phone call,
which nobody has established. Left absent on purpose.
"""
import sqlalchemy as sa
from alembic import op

revision = "r200_order_capture_part1_columns"
down_revision = "r199_service_time_and_eta"
branch_labels = None
depends_on = None

_TABLE = "ringcentral_call_extractions"

#: (name, type). ⚠️ ONE LIST, WALKED BY BOTH DIRECTIONS, so an upgrade and a
#: downgrade cannot disagree about which columns this migration owns.
_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("service_date", sa.Date()),
    ("cemetery_city", sa.String(120)),
    ("personalization", sa.String(40)),
    ("legacy_print_name", sa.String(120)),
    ("lifes_reflections_symbol", sa.String(60)),
)


def _existing(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t"
            ),
            {"t": _TABLE},
        )
    }


def upgrade() -> None:
    conn = op.get_bind()

    # ⚠️ POSITIVE CONTROL BEFORE THE WRITE. An `information_schema` query that
    # returns nothing is indistinguishable from a table that exists with no columns,
    # so the assertions after the write would be satisfied by a dead instrument.
    # Requiring a non-zero count first, and requiring a column we know is there,
    # makes the reader prove it can see (CLAUDE.md §11 — an instrument that cannot
    # see returns what a true absence returns).
    before = _existing(conn)
    assert len(before) > 20, (
        f"expected {_TABLE} to have >20 columns before this migration, saw "
        f"{len(before)} — the reader is not seeing the table"
    )
    assert "burial_date" in before, (
        "`burial_date` is missing, so this is not the table r199 left behind"
    )

    for name, type_ in _COLUMNS:
        if name not in before:
            op.add_column(_TABLE, sa.Column(name, type_, nullable=True))

    after = _existing(conn)
    for name, _ in _COLUMNS:
        assert name in after, f"{name} was not added"

    # ⚠️ ASSERTED NULLABLE AND DEFAULT-FREE, not merely present. "The column exists"
    # is satisfied by a NOT NULL column with a server default, which is the exact
    # thing this migration must not create.
    rows = conn.execute(
        sa.text(
            "SELECT column_name, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = ANY(:names)"
        ),
        {"t": _TABLE, "names": [n for n, _ in _COLUMNS]},
    ).all()
    assert len(rows) == len(_COLUMNS), f"expected {len(_COLUMNS)} rows, got {len(rows)}"
    for name, is_nullable, default in rows:
        assert is_nullable == "YES", f"{name} is NOT NULL; it must be nullable"
        assert default is None, f"{name} carries default {default!r}; it must have none"


def downgrade() -> None:
    conn = op.get_bind()
    present = _existing(conn)
    for name, _ in _COLUMNS:
        if name in present:
            op.drop_column(_TABLE, name)

    after = _existing(conn)
    for name, _ in _COLUMNS:
        assert name not in after, f"{name} survived the downgrade"
