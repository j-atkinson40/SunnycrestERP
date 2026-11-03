"""Normalize `roles.limited_to_areas` JSON `null` to SQL NULL.

### The defect

`limited_to_areas` is JSONB. SQLAlchemy writes Python `None` into a JSONB column
as the **JSON value `null`**, not as SQL NULL, unless the column is declared
`JSONB(none_as_null=True)`. r221 declared it without that flag, so every role
created by `seed_default_roles` after r221 — which is every role in every
freshly-built database — holds `'null'` instead of NULL.

Proven 2026-11-03: a `Role(limited_to_areas=None)` insert yielded
`limited_to_areas::text = 'null'` and `jsonb_typeof(...) = 'null'`, with
`limited_to_areas IS NULL` returning **false**.

### What was and was not affected

⚠️ **THE AREA GUARD WAS NEVER WRONG, AND THAT DISTINCTION MATTERS.**
`enforce_area_limit` tests `role.limited_to_areas is None` in Python, and JSON
null reads back through SQLAlchemy as `None` — so no user ever gained or lost
access from this. There is no security consequence to undo.

What broke was every SQL query over the column:
  - r223's divergence check would have reported every seeded `payroll` role as
    divergent (fixed there too, by treating `'null'` as absent);
  - three assertions in `test_area_limited_roles.py` and
    `test_payroll_role_slice.py` used `IS NULL` / `IS NOT NULL` and were wrong.

⚠️ **AND A DEV DATABASE CANNOT SEE THIS.** Local roles predate the column and
`seed_default_roles` skips roles that already exist, so nothing locally was ever
inserted with `None`. CI builds a database from scratch and caught it on the
first run — the "a suite that has only ever run against one database state"
shape, exactly.

### What this does

Sets the column to SQL NULL wherever it currently holds JSON `null`. The model
fix (`none_as_null=True`) stops new rows acquiring it; this cleans up the rows
that already did.

⚠️ **IT TOUCHES ONLY `jsonb_typeof(...) = 'null'` ROWS.** A role holding a real
array — `["payroll"]` — is left alone, and so is one already at SQL NULL. The
predicate cannot match a row carrying a measured value, so this is not the
"filling a column" hazard CLAUDE.md §5 warns about: it is converting one spelling
of "not established" into the other.
"""
from alembic import op
import sqlalchemy as sa

revision = "r224_normalize_limited_to_areas_null"
down_revision = "r223_payroll_role_in_every_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    before = conn.execute(
        sa.text("SELECT count(*) FROM roles WHERE jsonb_typeof(limited_to_areas) = 'null'")
    ).scalar()
    conn.execute(
        sa.text(
            "UPDATE roles SET limited_to_areas = NULL "
            "WHERE jsonb_typeof(limited_to_areas) = 'null'"
        )
    )
    after = conn.execute(
        sa.text("SELECT count(*) FROM roles WHERE jsonb_typeof(limited_to_areas) = 'null'")
    ).scalar()
    real = conn.execute(
        sa.text("SELECT count(*) FROM roles WHERE limited_to_areas IS NOT NULL")
    ).scalar()
    print(f"[r224] rows holding JSON null before: {before}, after: {after}")
    print(f"[r224] rows holding a real area list: {real} (untouched)")


def downgrade() -> None:
    # ⚠️ NO-OP, DELIBERATELY. The two spellings are indistinguishable to every
    # Python reader of this column, so "restoring" JSON null would reintroduce a
    # defect while changing no behaviour. A downgrade that re-creates a bug is
    # not a downgrade.
    pass
