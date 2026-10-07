"""Cemetery uniqueness becomes (company_id, name, city) — section B.

⚠️ THE OLD CONSTRAINT CONTRADICTED A STATED BUSINESS FACT. `uq_cemetery_company_name
UNIQUE (company_id, name)` made it impossible for one licensee to hold two cemeteries
with the same name — and several cemeteries Sunnycrest serves share a name in different
towns. It was found by trying to construct a test fixture for exactly that case and
getting a UniqueViolation.

⚠️ NO PRODUCTION ROW IS AFFECTED, AND THE REASON MATTERS MORE THAN THE REASSURANCE.
Measured read-only on production 2026-10-07: 3 cemeteries, 0 with a NULL or empty city,
no name collisions, and no sign of manual disambiguation (no parentheses, no town inside
the name). ⚠️ All three belong to `testco` — the SYNTHETIC DEV TENANT. `sunnycrest` has
ZERO cemeteries. So the business fact cannot be observed in the data, and "how have they
worked around it" has no answer there: they have not entered their cemeteries yet.

⚠️ NULL CITY IS THE ONE REAL HAZARD, AND POSTGRES'S DEFAULT IS WRONG FOR IT. In a plain
UNIQUE, NULLs are DISTINCT — so `('acme', "St Mary's", NULL)` could be inserted twice and
the constraint would permit both. That turns "two St Mary's in different towns" into "any
number of St Mary's with no town", which is the duplicate the old constraint existed to
stop.

`NULLS NOT DISTINCT` (PostgreSQL 15+) fixes it: at most one row per (company, name) with
no town, plus one per named town. Postgres 16 is the stated version (CLAUDE.md §2), so it
is available. The migration asserts the server version rather than assuming it, because
silently falling back to NULLS DISTINCT would reintroduce the hole while reporting
success.

⚠️ EXPAND-THEN-CONTRACT IS NOT USED HERE AND THAT IS DELIBERATE. The new constraint is
strictly WEAKER than the old one for named towns and strictly stronger for NULL towns, so
there is no window in which both can hold. The old one is dropped and the new one added in
one transaction.
"""
import sqlalchemy as sa
from alembic import op

revision = "r205_cemetery_unique_with_city"
down_revision = "r204_platform_availability"
branch_labels = None
depends_on = None

_TABLE = "cemeteries"
_OLD = "uq_cemetery_company_name"
_NEW = "uq_cemetery_company_name_city"


def _constraints(conn) -> dict[str, str]:
    return {
        r[0]: r[1]
        for r in conn.execute(sa.text(
            "SELECT c.conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = :t AND c.contype = 'u'"
        ), {"t": _TABLE})
    }


def upgrade() -> None:
    conn = op.get_bind()

    # ⚠️ POSITIVE CONTROL. An empty constraint read is indistinguishable from a table
    # with no unique constraints, and the assertions below would then pass vacuously.
    before = _constraints(conn)
    assert _OLD in before, f"{_OLD} is not present; constraints are {sorted(before)}"
    assert "company_id, name" in before[_OLD], before[_OLD]

    # ⚠️ THE SERVER VERSION IS ASSERTED, NOT ASSUMED. `NULLS NOT DISTINCT` is 15+, and
    # without it this migration would create a constraint that permits unlimited
    # NULL-city duplicates while reporting success.
    ver = conn.execute(sa.text("SHOW server_version_num")).scalar()
    assert int(ver) >= 150000, (
        f"server_version_num={ver}; NULLS NOT DISTINCT needs PostgreSQL 15+. Without it "
        f"this constraint would not stop duplicate NULL-city rows."
    )

    # ⚠️ PRE-FLIGHT ON THE DATA. The new constraint is weaker for named towns, so it
    # cannot fail on rows the old one permitted — EXCEPT for NULL-city duplicates, which
    # the old constraint already forbade by name alone. Checked anyway, because an
    # assertion that cannot fire costs nothing and a surprise here aborts a deploy.
    dupes = conn.execute(sa.text(
        "SELECT company_id, name, count(*) FROM cemeteries "
        "WHERE city IS NULL OR city = '' "
        "GROUP BY company_id, name HAVING count(*) > 1"
    )).all()
    assert not dupes, f"NULL-city duplicates already exist and would block the new constraint: {dupes}"

    op.drop_constraint(_OLD, _TABLE, type_="unique")
    # ⚠️ RAW SQL, BECAUSE ALEMBIC'S `create_unique_constraint` CANNOT EXPRESS
    # `NULLS NOT DISTINCT`. Using the helper would silently produce the NULLS DISTINCT
    # form — the exact hole this migration exists to close.
    op.execute(sa.text(
        f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_NEW} "
        "UNIQUE NULLS NOT DISTINCT (company_id, name, city)"
    ))

    after = _constraints(conn)
    assert _OLD not in after, f"{_OLD} survived"
    assert _NEW in after, f"{_NEW} was not created; have {sorted(after)}"
    definition = after[_NEW]
    assert "company_id, name, city" in definition, definition
    assert "NULLS NOT DISTINCT" in definition, (
        f"the constraint is NULLS DISTINCT, so unlimited NULL-city duplicates are "
        f"permitted: {definition}"
    )


def downgrade() -> None:
    conn = op.get_bind()
    present = _constraints(conn)

    # ⚠️ THE DOWNGRADE CAN FAIL ON DATA THE UPGRADE PERMITTED, AND THAT IS CORRECT
    # RATHER THAN A DEFECT. Once two St Mary's in different towns exist, restoring
    # UNIQUE (company_id, name) is impossible without deciding which one to delete —
    # and a migration must not make that choice. It raises with the rows named.
    collisions = conn.execute(sa.text(
        "SELECT company_id, name, count(*) FROM cemeteries "
        "GROUP BY company_id, name HAVING count(*) > 1"
    )).all()
    assert not collisions, (
        f"cannot restore UNIQUE (company_id, name): these now collide and the "
        f"downgrade will not choose which to delete — {collisions}"
    )

    if _NEW in present:
        op.drop_constraint(_NEW, _TABLE, type_="unique")
    if _OLD not in present:
        op.create_unique_constraint(_OLD, _TABLE, ["company_id", "name"])

    after = _constraints(conn)
    assert _OLD in after and _NEW not in after, sorted(after)
