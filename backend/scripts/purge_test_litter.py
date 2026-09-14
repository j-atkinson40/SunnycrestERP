"""Purge accumulated test litter from a DEVELOPMENT database.

⚠️ AUTHORED, NOT RUN. James runs this, as with every production-adjacent write.
Dry-run is the default; `--apply` is required to delete anything.

    python -m scripts.purge_test_litter                 # report only
    python -m scripts.purge_test_litter --apply         # delete

──────────────────────────────────────────────────────────────────────────
WHY THIS EXISTS

Measured 2026-09-14: `GET /api/v1/workflows?scope=core` returned 1,608 rows on
the development database. THIRTY-SIX workflows are declared in code. The rest
were test fixtures nobody deleted, and 573 of them were created in a single day.

That matters beyond disk. Twenty-one BLOCKING latency gates are about to have
their budgets derived from measurements taken against this database. A budget
derived at 1,608 rows is wrong at 36, wrong next week, and wrong in production —
and it would look like a considered number forever.

──────────────────────────────────────────────────────────────────────────
⚠️ THE PREDICATES, AND WHY THEY ARE SAFE

Two independent classes. NEITHER uses a name pattern, deliberately: a first
attempt at this separated real rows from fixtures using `is_system` and reported
1,383 "real" rows. The fixtures set `is_system=True` too — and
`wf_fh_obituary_draft`, a REAL workflow, has `is_system=False`. The discriminator
was wrong in both directions and a count over it looked exactly like a count over
a right one.

CLASS 1 — ORPHANS. Rows whose owning company no longer exists:

    tenant_id IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM companies WHERE id = tenant_id)

  Cannot affect a live tenant BY CONSTRUCTION — the parent is already gone.
  Enumerated across all 391 tables carrying a company_id/tenant_id column:
  exactly ONE holds orphans. `purge_companies_by_slug` and the FK cascades are
  doing their job for the other 390.

  ⚠️ `tenant_health_scores` HAS NO FOREIGN KEY AT ALL on `tenant_id`. Nothing
  enforced the parent, so nothing cascaded, so it is the one table that leaked.
  It is also absent from tests/_cleanup.py and scripts/seed_staging.py. The
  absence of the constraint IS the reason it is the exception.

CLASS 2 — NON-CANONICAL GLOBAL WORKFLOWS:

    company_id IS NULL
    AND id NOT IN (the ids declared in app/data/default_workflows.py)

  The canonical set is read FROM CODE at run time, not from the table. All 36
  declared ids were verified present in the database; none is missing, so the
  predicate cannot delete a platform workflow that merely failed to seed.

  ⚠️ `company_id IS NULL` is load-bearing. 29 non-canonical workflows belong to
  LIVE companies — tenant-authored workflows, not litter. They are excluded and
  will go when their tenant goes.

──────────────────────────────────────────────────────────────────────────
⚠️ WHAT RESTORES THE PRIOR STATE

Nothing, unless a dump is taken first. These rows are not derivable:
`tenant_health_scores` is computed per tenant per day and the tenants are gone,
so the scores cannot be recomputed. The workflow fixtures were authored by tests
that will simply create new ones.

`--apply` therefore writes a restore file first — plain INSERT statements for
every row it is about to delete — and refuses to proceed if it cannot. Cost is
roughly 10-15 MB. Restoring is `psql < the file`, in the order written.

⚠️ THE FK GRAPH IS DERIVED FROM information_schema AT RUN TIME, not hardcoded.
tests/_cleanup.py hardcodes its table list and CLAUDE.md records it drifting —
58 of 387 tables covered, seven added later. A derived graph cannot drift.
Three referrers of `workflows.id` are ON DELETE NO ACTION
(workflow_enrollments, workflow_runs, workflow_schedules): those RAISE rather
than cascade, so they are deleted first. Deriving the graph is what found them.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text


CANONICAL_WORKFLOW_IDS_SQL = "id = ANY(:canonical)"

#: Class 1. Keyed on the absence of a parent, never on a name.
ORPHAN_TABLE = "tenant_health_scores"
ORPHAN_COL = "tenant_id"
ORPHAN_PREDICATE = (
    f"{ORPHAN_COL} IS NOT NULL "
    f"AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = {ORPHAN_TABLE}.{ORPHAN_COL})"
)

#: Class 2. `company_id IS NULL` excludes tenant-authored workflows.
LITTER_WORKFLOW_SQL = (
    f"SELECT id FROM workflows WHERE company_id IS NULL AND NOT ({CANONICAL_WORKFLOW_IDS_SQL})"
)


def _canonical_ids() -> list[str]:
    from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

    return sorted({w["id"] for w in ALL_DEFAULT_WORKFLOWS})


def _blocking_children(conn) -> list[tuple[str, str]]:
    """(table, column) for every referrer of workflows.id that will NOT cascade.

    Derived from the catalog. A hardcoded list is the thing that drifted.
    """
    rows = conn.execute(text("""
        SELECT tc.table_name, k.column_name, rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.referential_constraints rc
             ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.key_column_usage k
             ON k.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage u
             ON u.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND u.table_name = 'workflows' AND u.column_name = 'id'
          AND tc.table_name <> 'workflows'
          AND rc.delete_rule NOT IN ('CASCADE', 'SET NULL')
        ORDER BY tc.table_name
    """)).all()
    return [(r[0], r[1]) for r in rows]


def _survey(conn, canonical: list[str]) -> dict:
    p = {"canonical": canonical}
    out: dict = {"blocking": []}
    out["orphans"] = conn.execute(text(
        f"SELECT count(*) FROM {ORPHAN_TABLE} WHERE {ORPHAN_PREDICATE}")).scalar()
    out["orphans_kept"] = conn.execute(text(
        f"SELECT count(*) FROM {ORPHAN_TABLE} WHERE NOT ({ORPHAN_PREDICATE})")).scalar()
    out["workflows"] = conn.execute(text(
        f"SELECT count(*) FROM ({LITTER_WORKFLOW_SQL}) t"), p).scalar()
    out["workflows_kept"] = conn.execute(text(
        f"SELECT count(*) FROM workflows WHERE NOT (company_id IS NULL AND NOT ({CANONICAL_WORKFLOW_IDS_SQL}))"
    ), p).scalar()
    out["steps_cascade"] = conn.execute(text(
        f"SELECT count(*) FROM workflow_steps WHERE workflow_id IN ({LITTER_WORKFLOW_SQL})"), p).scalar()
    for tbl, col in _blocking_children(conn):
        n = conn.execute(text(
            f'SELECT count(*) FROM "{tbl}" WHERE {col} IN ({LITTER_WORKFLOW_SQL})'), p).scalar()
        out["blocking"].append((tbl, col, n))
    # The control that the predicate did not eat the real set.
    out["canonical_present"] = conn.execute(text(
        f"SELECT count(*) FROM workflows WHERE {CANONICAL_WORKFLOW_IDS_SQL}"), p).scalar()
    return out


def _restore_order(sources):
    """Parents before children, which is the reverse of the delete order."""
    parents = [x for x in sources if x[0] in ("workflows", ORPHAN_TABLE)]
    children = [x for x in sources if x[0] not in ("workflows", ORPHAN_TABLE)]
    return parents + children


def _write_restore(conn, canonical: list[str], path: str) -> int:
    """Plain INSERTs for EVERY row about to be deleted. Written BEFORE any delete.

    ⚠️ THE BLOCKING CHILDREN ARE INCLUDED, AND WERE NOT IN THE FIRST VERSION.
    That version covered workflows, workflow_steps and the orphan table while the
    docstring claimed "everything about to be deleted" — the 9 rows in
    workflow_enrollments / workflow_runs that are deleted first, to stop the
    ON DELETE NO ACTION constraints raising, would have been unrecoverable. The
    blocking tables are derived from the same catalog query the delete uses, so
    the two cannot drift apart.
    """
    p = {"canonical": canonical}
    written = 0
    sources = [
        (tbl, f'SELECT * FROM "{tbl}" WHERE {col} IN ({LITTER_WORKFLOW_SQL})')
        for tbl, col in _blocking_children(conn)
    ] + [
        ("workflows", f"SELECT * FROM workflows WHERE id IN ({LITTER_WORKFLOW_SQL})"),
        ("workflow_steps",
         f"SELECT * FROM workflow_steps WHERE workflow_id IN ({LITTER_WORKFLOW_SQL})"),
        (ORPHAN_TABLE, f"SELECT * FROM {ORPHAN_TABLE} WHERE {ORPHAN_PREDICATE}"),
    ]
    with open(path, "w") as fh:
        fh.write(f"-- purge_test_litter restore file, {datetime.now(timezone.utc).isoformat()}\n")
        fh.write("-- Apply with: psql <db> < this file.\n")
        fh.write("-- ORDER IS SIGNIFICANT and is the REVERSE of the delete order:\n")
        fh.write("-- parents (workflows) must exist before their children are re-inserted.\n")
        for label, sql in _restore_order(sources):
            res = conn.execute(text(sql), p)
            cols = list(res.keys())
            for row in res:
                vals = ", ".join("NULL" if v is None else "'" + str(v).replace("'", "''") + "'"
                                 for v in row)
                fh.write(f'INSERT INTO "{label}" ({", ".join(cols)}) VALUES ({vals});\n')
                written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually delete (default: report only)")
    ap.add_argument("--restore-file", default="/tmp/purge_test_litter_restore.sql")
    args = ap.parse_args()

    if os.environ.get("ENVIRONMENT") == "production":
        print("REFUSING: ENVIRONMENT=production. This is a development-database tool.")
        return 2

    from app.database import engine
    from urllib.parse import urlparse

    u = urlparse(str(engine.url))
    print(f"target: host={u.hostname} port={u.port} db={(u.path or '').lstrip('/')}")

    canonical = _canonical_ids()
    print(f"canonical workflow ids declared in code: {len(canonical)}\n")

    with engine.connect() as conn:
        s = _survey(conn, canonical)

        # ⚠️ CONTROL BEFORE ANY WRITE. If the canonical set is not fully present,
        # the predicate is being evaluated against a database it does not describe.
        if s["canonical_present"] != len(canonical):
            print(f"REFUSING: {s['canonical_present']} of {len(canonical)} canonical "
                  "workflows found. The predicate would delete rows it cannot vouch for.")
            return 3

        print("WOULD DELETE")
        print(f"  {ORPHAN_TABLE:<26} {s['orphans']:>8}   (orphaned: owning company is gone)")
        print(f"  {'workflows':<26} {s['workflows']:>8}   (global, non-canonical)")
        print(f"  {'workflow_steps':<26} {s['steps_cascade']:>8}   (ON DELETE CASCADE, automatic)")
        for tbl, col, n in s["blocking"]:
            print(f"  {tbl:<26} {n:>8}   (ON DELETE NO ACTION — would RAISE; removed first)")
        print("\nWOULD KEEP")
        print(f"  {ORPHAN_TABLE:<26} {s['orphans_kept']:>8}   (live tenant)")
        print(f"  {'workflows':<26} {s['workflows_kept']:>8}   "
              f"({len(canonical)} canonical + tenant-authored)")

        if not args.apply:
            print("\nDRY RUN — nothing deleted. Re-run with --apply.")
            return 0

        n = _write_restore(conn, canonical, args.restore_file)
        print(f"\nrestore file: {args.restore_file}  ({n} rows)")

        # ⚠️ THE FAIL-SAFE IS NOW BY DESIGN, NOT BY ORDERING.
        #
        # The first --apply run raised between writing the restore file and the
        # first DELETE, so nothing was lost — but that was the ACCIDENT of where
        # the error happened to land, not a property of the script. Had the
        # survey sat inside the write block, the same error arrives mid-delete
        # with a partial restore file and no way to tell what is missing.
        #
        # So the guarantee is made explicit: the restore file must account for
        # EVERY row the delete will remove, counted from the same survey the
        # delete uses. If it does not, nothing is deleted.
        expected = (
            s["orphans"] + s["workflows"] + s["steps_cascade"]
            + sum(k for _, _, k in s["blocking"])
        )
        if n != expected:
            print(f"REFUSING: restore file holds {n} rows but the delete will "
                  f"remove {expected}. Nothing deleted.")
            return 5
        print(f"  covers all {expected} rows the delete will remove — verified")

        # ⚠️ END THE READ TRANSACTION BEFORE OPENING THE WRITE ONE.
        # SQLAlchemy AUTOBEGINS a transaction on the first read, so `conn.begin()`
        # here raises InvalidRequestError — which it did, after the restore file
        # was written and before any DELETE. The script failed safe, but only by
        # luck of ordering: had the survey run inside the write block the error
        # would have come mid-delete. This is the "one statement per connection,
        # or check transaction state before believing a result" rule, biting the
        # script written under it.
        conn.rollback()

        with conn.begin():
            for tbl, col, _ in s["blocking"]:
                conn.execute(text(
                    f'DELETE FROM "{tbl}" WHERE {col} IN ({LITTER_WORKFLOW_SQL})'),
                    {"canonical": canonical})
            conn.execute(text(f"DELETE FROM workflows WHERE id IN ({LITTER_WORKFLOW_SQL})"),
                         {"canonical": canonical})
            conn.execute(text(f"DELETE FROM {ORPHAN_TABLE} WHERE {ORPHAN_PREDICATE}"))

        after = _survey(conn, canonical)
        print("\nAFTER")
        print(f"  {ORPHAN_TABLE:<26} orphans={after['orphans']:<8} kept={after['orphans_kept']}")
        print(f"  {'workflows':<26} litter={after['workflows']:<8} kept={after['workflows_kept']}")
        if after["canonical_present"] != len(canonical):
            print("⚠️ CANONICAL WORKFLOWS WERE DELETED. Restore from the file immediately.")
            return 4
        print(f"  canonical workflows still present: {after['canonical_present']}/{len(canonical)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
