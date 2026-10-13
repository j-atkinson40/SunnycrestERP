"""James's hard constraint: Approve must not set off anything downstream.

⚠️ EACH CLAIM IS TESTED AGAINST AN ORDER APPROVE ACTUALLY CREATED, not against a
hand-built row. A fixture order could differ from a real one in exactly the field
that matters — `status` and `order_type` are the two the batch selects on, and they
are the two Approve sets deliberately.

⚠️ THE BATCH TEST RUNS THE JOB'S OWN QUERY, NOT A RESTATEMENT OF ITS FILTER. Calling
`generate_draft_invoices` is what proves exclusion, because the filter is the thing
that would change under us. A test that re-implemented
`status IN ('confirmed', …)` would keep passing after someone added `draft` to the
real one — which is precisely the failure mode worth guarding, since the batch is
LIVE on production and has already rewritten 5 orders to `delivered`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture import session_service


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(
        text("SELECT id FROM companies WHERE slug = 'sunnycrest'")
    ).scalar()
    assert tid, "no sunnycrest tenant — these tests must not skip"
    return tid


ORDER = (
    "order for hopkins monticello burial vault Mary Smith 1948 to 2026 "
    "going to St. Mary's section 4 lot 12 burial friday 11am "
    "service at the church thursday 10am full equipment nameplate only"
)


@pytest.fixture
def approved(db, tenant):
    """An order Approve really created, plus every fixture row it needed."""
    from app.models.role import Role
    from app.models.user import User

    made: list[tuple[str, str]] = []

    def ensure(table: str, where: str, params: dict, insert: str):
        found = db.execute(
            text(f"SELECT id FROM {table} WHERE {where}"), params
        ).scalar()
        if found:
            return found
        rid = str(uuid.uuid4())
        db.execute(text(insert), {**params, "i": rid})
        made.append((table, rid))
        return rid

    ensure("company_entities", "company_id = :t AND name = :n",
           {"t": tenant, "n": "Hopkins Funeral Home"},
           "INSERT INTO company_entities (id, company_id, name) VALUES (:i, :t, :n)")
    ensure("customers", "company_id = :t AND name = :n",
           {"t": tenant, "n": "Hopkins Funeral Home"},
           "INSERT INTO customers (id, company_id, name, account_number, is_active) "
           "VALUES (:i, :t, :n, 'TRIGGERFIX-C1', true)")
    ensure("products", "company_id = :t AND name = :n",
           {"t": tenant, "n": "Monticello Burial Vault"},
           "INSERT INTO products (id, company_id, name, sku, price, is_active) "
           "VALUES (:i, :t, :n, 'TRIGGERFIX-P1', 1250.00, true)")

    role = db.query(Role).filter(Role.company_id == tenant).first()
    u = User(
        id=str(uuid.uuid4()), company_id=tenant,
        email=f"trig-{uuid.uuid4().hex[:8]}@example.com",
        username=f"trig{uuid.uuid4().hex[:8]}",
        hashed_password="x", first_name="Trigger", last_name="Test",
        is_active=True, role_id=role.id if role else None,
    )
    db.add(u)
    db.commit()

    row = session_service.start(db, company_id=tenant, user_id=u.id)
    session_service.set_text(
        db, row.id, company_id=tenant, user_id=u.id, text=ORDER
    )
    session_service.set_text(
        db, row.id, company_id=tenant, user_id=u.id,
        text=ORDER + " that's everything",
    )
    row = session_service.approve(db, row.id, company_id=tenant, user_id=u.id)
    oid = row.sales_order_id
    assert oid, "the fixture did not approve — every test below would be vacuous"

    yield oid

    db.rollback()
    for sql, params in (
        # ⚠️ `invoice_lines` BEFORE `invoices`, AND THE REASON IS MEASURED. The
        # positive-control test deliberately lets the batch invoice the order, so an
        # invoice really exists here — and deleting it without its lines raises, the
        # delete is swallowed, the order survives, and then the USER cannot be
        # deleted either. 33 leftover users and 12 stranded orders accumulated on dev
        # before this line existed.
        ("DELETE FROM invoice_lines WHERE invoice_id IN "
         "(SELECT id FROM invoices WHERE sales_order_id = :o)", {"o": oid}),
        ("DELETE FROM invoices WHERE sales_order_id = :o", {"o": oid}),
        ("DELETE FROM order_personalization_tasks WHERE order_id = :o", {"o": oid}),
        ("DELETE FROM sales_order_lines WHERE sales_order_id = :o", {"o": oid}),
        ("UPDATE capture_sessions SET sales_order_id = NULL WHERE sales_order_id = :o", {"o": oid}),
        ("DELETE FROM sales_orders WHERE id = :o", {"o": oid}),
        ("DELETE FROM audit_logs WHERE user_id = :u", {"u": u.id}),
        ("DELETE FROM capture_sessions WHERE user_id = :u", {"u": u.id}),
        ("DELETE FROM users WHERE id = :u", {"u": u.id}),
    ):
        try:
            db.execute(text(sql), params)
            db.commit()
        except Exception:
            db.rollback()
    for table, rid in reversed(made):
        try:
            db.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": rid})
            db.commit()
        except Exception:
            db.rollback()


# ── the 18:00 batch ─────────────────────────────────────────────────────────

def test_the_END_OF_DAY_BATCH_DOES_NOT_SEE_IT(db, tenant, approved):
    """⚠️ THE JOB IS RUN, NOT ITS FILTER RESTATED. This is the test James asked for.

    The batch is live on production in the auto-confirm branch, where it sets the
    ORDER to `delivered` and drafts an invoice against it. Running it here and
    showing the order comes out untouched is the only evidence that `status='draft'`
    actually excludes it.
    """
    from app.services.draft_invoice_service import generate_draft_invoices

    before = db.execute(
        text("SELECT status, delivery_auto_confirmed, delivered_at "
             "FROM sales_orders WHERE id = :o"), {"o": approved}
    ).mappings().first()
    assert before["status"] == "draft"

    # ⚠️ THE SERVICE DATE IS MOVED INTO THE PAST FIRST, so the date half of the
    # batch's selection is SATISFIED and only `status`/`order_type` can be doing the
    # excluding. Left in the future the order would be skipped for the wrong reason
    # and this test would prove nothing.
    db.execute(
        text("UPDATE sales_orders SET scheduled_date = CURRENT_DATE - 1 WHERE id = :o"),
        {"o": approved},
    )
    db.commit()

    generate_draft_invoices(db, tenant)
    db.commit()

    after = db.execute(
        text("SELECT status, delivery_auto_confirmed, delivered_at "
             "FROM sales_orders WHERE id = :o"), {"o": approved}
    ).mappings().first()
    assert after["status"] == "draft", after["status"]
    assert not after["delivery_auto_confirmed"]
    assert after["delivered_at"] is None
    assert db.execute(
        text("SELECT count(*) FROM invoices WHERE sales_order_id = :o"), {"o": approved}
    ).scalar() == 0


def test_and_the_batch_WOULD_have_taken_it_if_it_were_confirmed(db, tenant, approved):
    """⚠️ THE POSITIVE CONTROL, AND WITHOUT IT THE TEST ABOVE PROVES NOTHING.

    A batch that selected no orders at all — wrong tenant, mode off, a filter typo —
    would pass the exclusion test every time. This flips the one field under test to
    `confirmed`, runs the same job, and shows it IS taken: marked delivered and
    invoiced. That is the behaviour `draft` is protecting the office from.
    """
    from app.services.draft_invoice_service import generate_draft_invoices

    db.execute(
        text("UPDATE sales_orders SET status = 'confirmed', "
             "scheduled_date = CURRENT_DATE - 1 WHERE id = :o"),
        {"o": approved},
    )
    db.commit()

    generate_draft_invoices(db, tenant)
    db.commit()

    after = db.execute(
        text("SELECT status, delivery_auto_confirmed FROM sales_orders WHERE id = :o"),
        {"o": approved},
    ).mappings().first()
    invoices = db.execute(
        text("SELECT count(*) FROM invoices WHERE sales_order_id = :o"), {"o": approved}
    ).scalar()
    assert (after["status"], after["delivery_auto_confirmed"], invoices) == (
        "delivered", True, 1
    ), (after["status"], after["delivery_auto_confirmed"], invoices)


# ── everything else that must stay still ────────────────────────────────────

def test_no_invoice_is_created(db, approved):
    assert db.execute(
        text("SELECT count(*) FROM invoices WHERE sales_order_id = :o"), {"o": approved}
    ).scalar() == 0


def test_nothing_is_posted_to_the_ledger(db, tenant, approved):
    # ⚠️ ASSERTED ON THE WHOLE TENANT, NOT ON THIS ORDER. `post_invoice` writes a
    # journal entry keyed to the INVOICE, so an order-scoped query would find
    # nothing whether or not a posting had happened.
    n = db.execute(
        text("SELECT count(*) FROM journal_entries WHERE tenant_id = :t "
             "AND entry_type = 'invoice'"), {"t": tenant}
    ).scalar()
    assert n == 0, f"{n} invoice journal entries exist on this tenant"


def test_the_customer_balance_does_not_move(db, tenant, approved):
    cid = db.execute(
        text("SELECT customer_id FROM sales_orders WHERE id = :o"), {"o": approved}
    ).scalar()
    bal = db.execute(
        text("SELECT current_balance FROM customers WHERE id = :c"), {"c": cid}
    ).scalar()
    assert (bal or Decimal("0.00")) == Decimal("0.00"), bal


def test_no_delivery_is_created(db, approved):
    assert db.execute(
        text("SELECT count(*) FROM deliveries WHERE order_id = :o"), {"o": approved}
    ).scalar() == 0


def test_the_order_is_not_marked_delivered_or_confirmed(db, approved):
    row = db.execute(
        text("SELECT status, delivered_at, driver_confirmed, completed_at "
             "FROM sales_orders WHERE id = :o"), {"o": approved}
    ).mappings().first()
    assert row["status"] == "draft"
    assert row["delivered_at"] is None
    assert not row["driver_confirmed"]
    assert row["completed_at"] is None


def test_invoicing_it_directly_is_REFUSED_while_it_is_a_draft(db, tenant, approved):
    """⚠️ THE GUARD BELOW THE GUARD. Even if something tried to invoice this order on
    purpose, `create_invoice_from_order` refuses a draft (`sales_service.py:739`)."""
    from fastapi import HTTPException

    from app.services import sales_service

    with pytest.raises(HTTPException) as e:
        sales_service.create_invoice_from_order(db, tenant, None, approved)
    assert e.value.status_code == 400
    assert "draft" in str(e.value.detail).lower()
