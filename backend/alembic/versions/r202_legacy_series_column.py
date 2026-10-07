"""`legacy_series` extraction column — R2, standard vs custom.

⚠️ ONE COLUMN, NULLABLE, NO DEFAULT, EXPAND-ONLY. Same shape and same reasoning as
r200: NULL means NOT ESTABLISHED, and nobody has measured whether a historical call
asked for a standard or a custom Legacy print. A `server_default` of `'standard'`
would read as data and would assert something about every pre-existing row.

⚠️ WHY IT IS A SEPARATE REVISION FROM r200. R1 collapsed the standard-vs-custom
distinction out of the answer set on 2026-10-07; R2 restored it as a FIELD later the
same day, after r200 had already been written and round-tripped. Folding it into r200
would have meant editing a revision that had already been pushed.

⚠️ AND IT IS SEPARATE FROM r201 BECAUSE r201 IS DATA-ONLY, by ruling. Mixing a column
add into a data migration makes the data migration unrevertable without also dropping
the column.

`legacy_print_name` (r200) now hangs off this field: the ordering portal shows its
print picker only for STANDARD (`components/OrderFlow.tsx:279`), so custom carries
artwork that follows separately and names no catalogue print.
"""
import sqlalchemy as sa
from alembic import op

revision = "r202_legacy_series_column"
down_revision = "r201_personalization_availability_data"
branch_labels = None
depends_on = None

_TABLE = "ringcentral_call_extractions"
_COLUMN = "legacy_series"


def _existing(conn) -> set[str]:
    return {
        r[0] for r in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
        ), {"t": _TABLE})
    }


def upgrade() -> None:
    conn = op.get_bind()
    before = _existing(conn)
    # ⚠️ POSITIVE CONTROL. An information_schema read that returns nothing is
    # indistinguishable from a table with no columns, and the assertion after the
    # write would then be satisfied by a dead instrument.
    assert len(before) > 25, f"saw {len(before)} columns on {_TABLE}; reader is blind"
    assert "legacy_print_name" in before, (
        "`legacy_print_name` is absent, so this is not the table r200 left behind"
    )

    if _COLUMN not in before:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(20), nullable=True))

    row = conn.execute(sa.text(
        "SELECT is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": _TABLE, "c": _COLUMN}).first()
    assert row is not None, f"{_COLUMN} was not added"
    assert row[0] == "YES", f"{_COLUMN} is NOT NULL; it must be nullable"
    assert row[1] is None, f"{_COLUMN} carries default {row[1]!r}; it must have none"


def downgrade() -> None:
    conn = op.get_bind()
    if _COLUMN in _existing(conn):
        op.drop_column(_TABLE, _COLUMN)
    assert _COLUMN not in _existing(conn), f"{_COLUMN} survived the downgrade"
