"""Seed Idempotency Arc P0: seed_staging cleanup recovers from partial-abort residue
+ stays tenant-scoped.

The old _run_cleanup_deletes deleted in ALPHABETICAL order with a SAVEPOINT that
SWALLOWED every failure — so `DELETE FROM cemeteries` (c) ran before
`DELETE FROM sales_orders` (s), hit the FK, was silently swallowed, and the cemetery
SURVIVED. Accumulated residue like that is the self-perpetuating 20-min-boot loop.

The new cleanup fixpoint-iterates tenant-scoped deletes (order resolves itself),
logs every clear, and fails loud on genuine residue. These tests prove:
  1. it CLEARS the exact residue the old code choked on (cemetery ← sales_order), and
  2. it is TENANT-SCOPED — cleaning tenant A never touches tenant B (catches a
     too-broad CASCADE).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from scripts.seed_staging import _run_cleanup_deletes


def _seed_tenant_graph(db, cid: str):
    """company → cemetery + customer + sales_order(cemetery_id, customer_id).
    The sales_order → cemetery FK is exactly what the old alphabetical cleanup
    could not clear (cemeteries deleted before the orders referencing them)."""
    suf = cid[:8]
    db.execute(
        text(
            "INSERT INTO companies (id, name, slug, created_at, updated_at) "
            "VALUES (:id, :name, :slug, now(), now())"
        ),
        {"id": cid, "name": f"CleanupTest-{suf}", "slug": f"cleanup-{suf}"},
    )
    cem_id, cust_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.execute(
        text("INSERT INTO cemeteries (id, company_id, name) VALUES (:id, :cid, :n)"),
        {"id": cem_id, "cid": cid, "n": "Residue Memorial"},
    )
    db.execute(
        text("INSERT INTO customers (id, company_id, name) VALUES (:id, :cid, :n)"),
        {"id": cust_id, "cid": cid, "n": "Residue FH"},
    )
    db.execute(
        text(
            "INSERT INTO sales_orders (id, company_id, number, customer_id, "
            "cemetery_id, order_date) VALUES (:id, :cid, :num, :cust, :cem, now())"
        ),
        {
            "id": str(uuid.uuid4()), "cid": cid, "num": f"SO-{suf}",
            "cust": cust_id, "cem": cem_id,
        },
    )
    db.commit()


def _counts(db, cid: str) -> dict[str, int]:
    return {
        t: db.execute(
            text(f"SELECT COUNT(*) FROM {t} WHERE company_id = :cid"), {"cid": cid}
        ).scalar()
        for t in ("cemeteries", "customers", "sales_orders")
    }


@pytest.fixture
def db_and_tenants():
    db = SessionLocal()
    ids: list[str] = []
    yield db, ids
    # teardown — clear children (cleanup preserves companies) then drop the rows
    for cid in ids:
        try:
            _run_cleanup_deletes(db, cid)
        except Exception:
            db.rollback()
        db.execute(text("DELETE FROM companies WHERE id = :cid"), {"cid": cid})
    db.commit()
    db.close()


def test_cleanup_recovers_partial_abort_residue(db_and_tenants):
    db, ids = db_and_tenants
    cid = str(uuid.uuid4())
    ids.append(cid)
    _seed_tenant_graph(db, cid)
    assert _counts(db, cid) == {"cemeteries": 1, "customers": 1, "sales_orders": 1}

    # The witness: the new cleanup completes (no raise) AND clears the cemetery the
    # old alphabetical+swallow cleanup left behind.
    _run_cleanup_deletes(db, cid)
    db.commit()
    assert _counts(db, cid) == {"cemeteries": 0, "customers": 0, "sales_orders": 0}


def test_cleanup_is_tenant_scoped(db_and_tenants):
    db, ids = db_and_tenants
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    ids.extend([a, b])
    _seed_tenant_graph(db, a)
    _seed_tenant_graph(db, b)

    # Clean ONLY tenant A.
    _run_cleanup_deletes(db, a)
    db.commit()

    # A cleared; B completely untouched (the cross-tenant-safety guard — a too-broad
    # CASCADE would have wiped B too).
    assert _counts(db, a) == {"cemeteries": 0, "customers": 0, "sales_orders": 0}
    assert _counts(db, b) == {"cemeteries": 1, "customers": 1, "sales_orders": 1}
