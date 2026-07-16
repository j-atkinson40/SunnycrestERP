"""Purge fixture residue (perf pass, 2026-07) — the adopt-aware dev-DB
slimming, census-witnessed.

NOT a seed (deliberately outside the seed_* naming convention — this must
never run at boot). Run it by hand:

    DATABASE_URL=... python -m scripts.purge_fixture_residue           # dry-run census
    DATABASE_URL=... python -m scripts.purge_fixture_residue --apply   # the purge

THE KEEP-LIST DISCIPLINE (positive, explicit — real content survives by
NAME, residue dies by exclusion):

    default · testco · hopkins-fh · st-marys · sunnycrest

Everything else in `companies` is fixture residue — months of leaked test
tenants (the hermetic-fixtures-leave-rows class at scale: e1-*/dispatch-*/
sp-*/cb-*/vaultv* … ~60k rows on dev at purge time). Provenance was
verified unambiguous before this script existed: filtering to human-shaped
slugs left EXACTLY the keep-list.

MECHANISM (generic, FK-complete):
  1. production refusal + census(before);
  2. disable RI triggers for the session (session_replication_role=replica)
     so tenant-scoped tables can be swept without FK ordering;
  3. delete rows from every table with a REAL FK column → companies(id)
     where that column names a purged company;
  4. delete the purged companies;
  5. THE ORPHAN FIXPOINT SWEEP: for every FK edge in the schema, delete
     child rows whose parent is gone; repeat until a full pass deletes
     zero rows — referential integrity is provably restored edge-by-edge
     (grandchild tables without their own company column die here);
  6. restore RI; census(after); print the receipt.

Prints VACUUM advice (a purge this size deserves one; VACUUM can't run
inside the script's transaction scope).
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import SessionLocal  # noqa: E402

KEEP_SLUGS = ("default", "testco", "hopkins-fh", "st-marys", "sunnycrest")

_CENSUS_TABLES = (
    "companies", "users", "roles", "workflow_runs", "workflow_run_steps",
    "sales_orders", "invoices", "customers", "company_entities",
    "moc_task_catalog", "moc_task_trigger", "deliveries",
)


def _census(db) -> dict[str, int]:
    out = {}
    for t in _CENSUS_TABLES:
        try:
            out[t] = db.execute(text(f"SELECT count(*) FROM {t}")).scalar() or 0
        except Exception:
            db.rollback()
            out[t] = -1
    return out


def _company_fk_columns(db) -> list[tuple[str, str]]:
    """(table, column) pairs with a REAL foreign key → companies(id)."""
    rows = db.execute(text("""
        SELECT c.conrelid::regclass::text AS child_table,
               a.attname AS child_col
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f'
          AND c.confrelid = 'companies'::regclass
        ORDER BY 1, 2
    """)).fetchall()
    return [(t, col) for t, col in rows if t != "companies"]


def _all_fk_edges(db) -> list[tuple[str, str, str, str]]:
    """(child_table, child_col, parent_table, parent_col) for every FK."""
    rows = db.execute(text("""
        SELECT c.conrelid::regclass::text,
               ca.attname,
               c.confrelid::regclass::text,
               pa.attname
        FROM pg_constraint c
        JOIN unnest(c.conkey) WITH ORDINALITY AS ck(attnum, ord) ON true
        JOIN unnest(c.confkey) WITH ORDINALITY AS pk(attnum, ord)
             ON pk.ord = ck.ord
        JOIN pg_attribute ca ON ca.attrelid = c.conrelid AND ca.attnum = ck.attnum
        JOIN pg_attribute pa ON pa.attrelid = c.confrelid AND pa.attnum = pk.attnum
        WHERE c.contype = 'f'
        ORDER BY 1, 2
    """)).fetchall()
    return [tuple(r) for r in rows]


def main() -> int:
    if os.environ.get("ENVIRONMENT") == "production":
        print("[purge] ENVIRONMENT=production — refusing. This script never runs there.")
        return 1
    apply = "--apply" in sys.argv

    db = SessionLocal()
    try:
        keep_ids = [r[0] for r in db.execute(
            text("SELECT id FROM companies WHERE slug = ANY(:s)"),
            {"s": list(KEEP_SLUGS)},
        )]
        purge_count = db.execute(
            text("SELECT count(*) FROM companies WHERE NOT (id = ANY(:k))"),
            {"k": keep_ids},
        ).scalar() or 0

        before = _census(db)
        print("[purge] keep-list:", ", ".join(KEEP_SLUGS))
        print(f"[purge] keeping {len(keep_ids)} companies; purging {purge_count}.")
        print("[purge] census BEFORE:")
        for t, n in before.items():
            print(f"  {t:24s} {n}")

        if not apply:
            print("[purge] dry-run (no --apply) — nothing deleted.")
            return 0
        if purge_count == 0:
            print("[purge] nothing to purge — already clean.")
            return 0

        # RI triggers off for the session: sweep order stops mattering.
        # PER-PHASE COMMITS (the first run died mid-flight holding one
        # giant transaction): each phase commits; a killed run resumes by
        # re-running — every phase is idempotent (deletes of already-
        # deleted rows are no-ops).
        db.execute(text("SET session_replication_role = replica"))

        # Pass 1 — every direct company-FK column.
        for table, col in _company_fk_columns(db):
            n = db.execute(text(
                f"DELETE FROM {table} WHERE {col} IS NOT NULL "
                f"AND NOT ({col} = ANY(:k))"
            ), {"k": keep_ids}).rowcount
            if n:
                print(f"[purge] {table}.{col}: -{n}", flush=True)
            db.commit()
            db.execute(text("SET session_replication_role = replica"))

        n = db.execute(text(
            "DELETE FROM companies WHERE NOT (id = ANY(:k))"
        ), {"k": keep_ids}).rowcount
        print(f"[purge] companies: -{n}", flush=True)
        db.commit()
        db.execute(text("SET session_replication_role = replica"))

        # Pass 2 — THE ORPHAN FIXPOINT SWEEP: restore RI edge-by-edge.
        edges = _all_fk_edges(db)
        sweep = 0
        while True:
            sweep += 1
            deleted = 0
            for child, ccol, parent, pcol in edges:
                if child == parent:
                    # self-FK (e.g. moc_task_catalog.forked_from_task_id) —
                    # ON DELETE SET NULL semantics honored manually.
                    q = (f"UPDATE {child} SET {ccol} = NULL WHERE {ccol} IS NOT NULL "
                         f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pcol} = {child}.{ccol})")
                else:
                    q = (f"DELETE FROM {child} WHERE {ccol} IS NOT NULL "
                         f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pcol} = {child}.{ccol})")
                n = db.execute(text(q)).rowcount
                if n:
                    print(f"[purge] orphan sweep {sweep}: {child}.{ccol} → {parent}: -{n}", flush=True)
                    deleted += n
            db.commit()
            db.execute(text("SET session_replication_role = replica"))
            if deleted == 0:
                break
            if sweep > 20:
                print("[purge] ERROR: orphan sweep did not converge in 20 passes — rolling back.")
                db.rollback()
                return 1

        db.execute(text("SET session_replication_role = DEFAULT"))
        db.commit()

        after = _census(db)
        print("[purge] census AFTER (the receipt):")
        for t, n in after.items():
            print(f"  {t:24s} {before.get(t)} → {n}")
        print("[purge] done. Recommended follow-up: VACUUM (ANALYZE);")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
