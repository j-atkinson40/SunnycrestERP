"""The company purge must complete, or raise — never half-finish silently.

⚠️ THE BUG THIS PINS (ruling 2026-11-04). `purge_test_companies` ran 93 DELETEs
in one transaction and committed at the end. The curated list covers 72 tables;
327 tables reference one of them without ON DELETE CASCADE. So a company tree
that touched an uncovered table hit an FK violation mid-list, which:

  * aborted the transaction, discarding the 50-odd deletes that had SUCCEEDED,
  * left the connection `idle in transaction (aborted)` — four were observed at
    once on the dev database,
  * and was swallowed by the teardown's caller, so the suite went green while
    its whole company tree stayed behind.

`quotes.customer_id -> customers.id ON DELETE NO ACTION` is the documented
instance: a company with a customer that has a quote could not be purged at all.

⚠️ EACH TEST HERE MUST FAIL IF THE FIX IS REMOVED. The savepoint, the retry and
the FK discovery are three separate mechanisms; a test that passes with any one
of them reverted is not pinning that one.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from tests._cleanup import purge_test_companies


def _company(s, slug_tag: str) -> str:
    cid = f"c-purge-{slug_tag}-{uuid.uuid4().hex[:8]}"
    s.execute(
        text(
            "INSERT INTO companies (id, name, slug, created_at, updated_at) "
            "VALUES (:i, :n, :sl, now(), now())"
        ),
        {"i": cid, "n": f"Purge Probe {slug_tag}", "sl": cid},
    )
    return cid


def _customer_with_quote(s, cid: str) -> tuple[str, str]:
    cust = f"cust-{uuid.uuid4().hex[:10]}"
    quote = f"q-{uuid.uuid4().hex[:10]}"
    s.execute(
        text("INSERT INTO customers (id, company_id, name) VALUES (:i, :c, 'Probe Customer')"),
        {"i": cust, "c": cid},
    )
    s.execute(
        text(
            "INSERT INTO quotes (id, company_id, customer_id, number, quote_date) "
            "VALUES (:i, :c, :cu, :n, now())"
        ),
        {"i": quote, "c": cid, "cu": cust, "n": f"QP-{quote[-6:]}"},
    )
    return cust, quote


@pytest.fixture()
def s():
    sess = SessionLocal()
    try:
        yield sess
    finally:
        sess.rollback()
        sess.close()


def test_a_company_whose_customer_has_a_quote_is_fully_purged(s):
    """The documented blocker. Before the fix this removed NOTHING."""
    cid = _company(s, "quote")
    cust, quote = _customer_with_quote(s, cid)
    s.commit()

    purge_test_companies(s, [cid])

    for table, ident in (("companies", cid), ("customers", cust), ("quotes", quote)):
        n = s.execute(
            text(f"SELECT count(*) FROM {table} WHERE id = :i"), {"i": ident}
        ).scalar()
        assert n == 0, f"{table} row {ident} survived the purge"


def test_the_session_is_still_usable_after_a_purge(s):
    """⚠️ The aborted-transaction half of the bug, which the row counts above
    cannot see: a purge that rolled everything back would still leave every
    count at 0 if nothing had been inserted. Here the session must execute a
    statement afterwards, which an aborted transaction cannot do."""
    cid = _company(s, "usable")
    _customer_with_quote(s, cid)
    s.commit()

    purge_test_companies(s, [cid])

    assert s.execute(text("SELECT 1")).scalar() == 1


def test_a_purge_of_one_company_leaves_another_alone(s):
    """Scoping: FK discovery composes subqueries from the doomed parents, so a
    bug there would widen the blast radius rather than narrow it."""
    doomed = _company(s, "doomed")
    keeper = _company(s, "keeper")
    _customer_with_quote(s, doomed)
    k_cust, k_quote = _customer_with_quote(s, keeper)
    s.commit()

    try:
        purge_test_companies(s, [doomed])
        assert s.execute(
            text("SELECT count(*) FROM companies WHERE id = :i"), {"i": keeper}
        ).scalar() == 1
        assert s.execute(
            text("SELECT count(*) FROM quotes WHERE id = :i"), {"i": k_quote}
        ).scalar() == 1, "the keeper's quote was deleted — scoping is too wide"
        assert s.execute(
            text("SELECT count(*) FROM customers WHERE id = :i"), {"i": k_cust}
        ).scalar() == 1
    finally:
        purge_test_companies(s, [keeper])


def test_an_empty_id_list_is_a_no_op(s):
    before = s.execute(text("SELECT count(*) FROM companies")).scalar()
    purge_test_companies(s, [])
    assert s.execute(text("SELECT count(*) FROM companies")).scalar() == before
