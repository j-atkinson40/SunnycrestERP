"""THE GENERALIZED DEV-RESIDUE PURGE (map-performance arc, 2026-07-20).

Test suites without teardown left hundreds of synthetic companies on dev
(sp-*, e1-*, p5-*, vaultv1*, widget-test-*, …). Each rides every
per-tenant fan-out (nightly health scores ~1,500 rows/night, the 15-min
sweeps, the fires strip) and their months of churn bloated the run
tables to GB scale.

KEEP-LIST-POSITIVE (the standing rule): companies whose slug is in
KEEP_SLUGS survive; every other company AND its whole FK tree dies.
Anything ambiguous would simply not be in the keep list — there is no
prefix guessing.

FK-ERROR-GUIDED (the Session One pattern): delete children found via
information_schema company-FK discovery; on an IntegrityError, parse the
blocking table from the error, delete its rows via ITS company-FK (or
grandchild fallback through the parent's PK), retry. Per-company commit
— a failure on one company never rolls back the fleet.

Dev-only: refuses ENVIRONMENT=production AND any DATABASE_URL that
doesn't look local unless --force-remote is passed.

Usage:  DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
        python -m scripts.purge_dev_residue [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

KEEP_SLUGS = {"testco", "hopkins-fh", "st-marys", "sunnycrest", "default"}

_BLOCK_RE = re.compile(r'referenced from table "([^"]+)"')


def _company_fk_columns(db, table: str) -> list[str]:
    rows = db.execute(text("""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = :t
          AND ccu.table_name = 'companies'
    """), {"t": table}).fetchall()
    return [r[0] for r in rows]


def _delete_tree(db, company_id: str, max_iters: int = 60) -> None:
    """Delete one company + everything that blocks it, FK-error-guided."""
    for _ in range(max_iters):
        try:
            db.execute(text("DELETE FROM companies WHERE id = :c"),
                       {"c": company_id})
            return
        except Exception as exc:
            db.rollback()
            m = _BLOCK_RE.search(str(exc))
            if not m:
                raise
            blocker = m.group(1)
            cols = _company_fk_columns(db, blocker)
            if cols:
                for col in cols:
                    try:
                        db.execute(text(
                            f"DELETE FROM {blocker} WHERE {col} = :c"),
                            {"c": company_id})
                    except Exception as exc2:
                        # The blocker has its own blocker — recurse via
                        # the same error-parse on the next outer loop.
                        db.rollback()
                        m2 = _BLOCK_RE.search(str(exc2))
                        if not m2:
                            raise
                        b2 = m2.group(1)
                        for ccol, pcol in _fks_between(db, b2, blocker):
                            db.execute(text(
                                f"DELETE FROM {b2} WHERE {ccol} IN "
                                f"(SELECT {pcol} FROM {blocker} "
                                f" WHERE {col} = :c)"), {"c": company_id})
            else:
                # Grandchild: walk one level up via ANY FK whose parent
                # table has a company FK.
                parents = db.execute(text("""
                    SELECT kcu.column_name, ccu.table_name parent,
                           ccu.column_name parent_col
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                      ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name = :t AND ccu.table_name != 'companies'
                """), {"t": blocker}).fetchall()
                handled = False
                for col, parent, parent_col in parents:
                    pcols = _company_fk_columns(db, parent)
                    for pc in pcols:
                        db.execute(text(
                            f"DELETE FROM {blocker} WHERE {col} IN "
                            f"(SELECT {parent_col} FROM {parent} "
                            f" WHERE {pc} = :c)"), {"c": company_id})
                        handled = True
                if not handled:
                    raise
    raise RuntimeError(f"company {company_id}: FK walk exceeded {max_iters} iters")


def _fks_between(db, child: str, parent: str) -> list[tuple[str, str]]:
    """(child_col, parent_col) FKs from `child` into `parent`."""
    return [tuple(r) for r in db.execute(text("""
        SELECT kcu.column_name, ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = :c AND ccu.table_name = :p
    """), {"c": child, "p": parent}).fetchall()]


def _bulk_purge(db, kill_ids: list[str]) -> None:
    """SET-BASED SWEEP (the fleet-scale path): per company-FK table,
    delete ALL residue rows at once. A blocked delete names its blocker
    (often a grandchild line-table with no company FK) — the blocker's
    rows are deleted through a subselect on the parent, then the parent
    retries. Sweeps iterate until the companies themselves delete."""
    from sqlalchemy import bindparam

    def run(sql: str) -> int:
        stmt = text(sql).bindparams(bindparam("ids", expanding=True))
        r = db.execute(stmt, {"ids": kill_ids})
        db.commit()
        return r.rowcount

    for sweep in range(40):
        tables = db.execute(text("""
            SELECT DISTINCT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'companies'
              AND tc.table_name != 'companies'
        """)).fetchall()
        progress = False
        for table, col in tables:
            for _attempt in range(15):
                try:
                    if run(f"DELETE FROM {table} WHERE {col} IN :ids"):
                        progress = True
                    break
                except Exception as exc:
                    db.rollback()
                    m = _BLOCK_RE.search(str(exc))
                    if not m:
                        break
                    blocker = m.group(1)
                    handled = False
                    for ccol, pcol in _fks_between(db, blocker, table):
                        try:
                            if run(
                                f"DELETE FROM {blocker} WHERE {ccol} IN "
                                f"(SELECT {pcol} FROM {table} "
                                f" WHERE {col} IN :ids)"
                            ):
                                progress = True
                            handled = True
                        except Exception:
                            db.rollback()  # blocker's own child — later sweep
                    if not handled:
                        break
        try:
            run("DELETE FROM companies WHERE id IN :ids")
            return
        except Exception:
            db.rollback()
        if not progress:
            break
    # Stragglers: the per-company FK walk.
    remaining = [r[0] for r in db.execute(
        text("SELECT id FROM companies WHERE id = ANY(:ids)"),
        {"ids": kill_ids}).fetchall()]
    print(f"[purge] bulk left {len(remaining)} stragglers — per-company walk")
    for cid in remaining:
        try:
            _delete_tree(db, cid)
            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"[purge] straggler FAILED {cid}: {str(exc)[:120]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-remote", action="store_true")
    args = ap.parse_args()

    if os.environ.get("ENVIRONMENT") == "production":
        print("ENVIRONMENT=production — refusing. This is a dev tool.")
        return 1
    url = os.environ.get("DATABASE_URL", "")
    if not args.force_remote and not (
        "localhost" in url or "127.0.0.1" in url
    ):
        print(f"DATABASE_URL does not look local ({url.split('@')[-1] if '@' in url else url}) "
              "— refusing without --force-remote.")
        return 1

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, slug FROM companies ORDER BY slug")).fetchall()
        keep = [(i, s) for i, s in rows if s in KEEP_SLUGS]
        kill = [(i, s) for i, s in rows if s not in KEEP_SLUGS]
        print(f"[purge] census: {len(rows)} companies — "
              f"KEEP {len(keep)} {sorted(s for _, s in keep)}, "
              f"PURGE {len(kill)}")
        if args.dry_run:
            print("[purge] dry-run — nothing deleted.")
            return 0

        _bulk_purge(db, [cid for cid, _ in kill])
        done = len(kill)
        failed = 0
        remaining = db.execute(text(
            "SELECT count(*) FROM companies WHERE slug NOT IN :k"),
            {"k": tuple(KEEP_SLUGS)}).scalar()
        print(f"[purge] done — {done} purged, {failed} failed, "
              f"remaining residue companies: {remaining}")
        return 0 if remaining == 0 else 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
