"""What Approve does downstream — and the rule this file was named for is RETIRED.

⚠️ THE FILE NAME IS NOW HISTORY, NOT A CLAIM. It was written for James's constraint
"Approve must not set off anything downstream", which was true and useful for exactly as
long as Approve produced a `draft` — a row nothing acted on. James retired it on
2026-10-16: once Approve confirms, "sets nothing in motion" is not available as a
property, because confirming IS what sets the order in motion. The replacement rule is
PARITY — an order confirmed from Opas behaves exactly like one confirmed any other way —
and it lives in `test_approve_confirms_and_the_batch_waits.py`'s
`test_the_two_confirm_paths_do_not_diverge`.

The name is left alone this time rather than renamed again: `test_approve_confirms_the_order.py`
was renamed in the same arc and a second rename in two commits makes the history harder
to follow than the stale name does. What the file still legitimately covers is below.

⚠️ WHAT SURVIVES, AND IT IS MOST OF IT. Three tests were re-pointed rather than deleted
when Approve started writing `confirmed`: the batch no longer excludes the order by
STATUS, it excludes it by the service date not having arrived. Each quotes what it used
to assert and why that stopped being true. Confirming still must not pretend a vault has
been placed — no `delivered_at`, no `driver_confirmed`, no `completed_at` — and that is
the part of the original constraint with real force left in it.

⚠️ AND THIS FILE IS WHY THE DELIVERY HOOK WAS BRIEFLY ABSENT FROM `approve`. I added it,
then backed it out on the strength of the retired rule, then re-added it on James's
ruling. The round trip is recorded because the middle state shipped: for one commit, an
Opas-confirmed order and a hand-confirmed one would have diverged the moment
`auto_create_delivery_from_order` was enabled — invisibly, since every test was green
with the flag off.

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

from datetime import date, timedelta

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


#: ⚠️ NO BURIAL CLAUSE SINCE 2026-10-13. The burial is always the service day, so a
#: "burial friday" against a thursday service is now a CONFLICT and blocks approval —
#: which is what this sentence used to say.
#: ⚠️ A VAULT THAT ACCEPTS THE NAMEPLATE, AND A DATE FORMAT. Since 2026-10-13 an
#: unavailable personalization answer is a conflict and a conflict blocks approval,
#: so a Monticello with a nameplate can no longer be approved — and choosing a
#: nameplate makes `nameplate_date_format` required, which "written" answers.
#: ⚠️ THE DAY IS DERIVED, NOT THE WORD "thursday", AND A THURSDAY IS WHY.
#: This sentence said "thursday" and the file's own control caught it on
#: 2026-10-29 — a Thursday:
#:
#:     AssertionError: the fixture's service date is not in the future
#:     (2026-10-29); this test would then prove nothing about the date gate
#:
#: A weekday name resolves to the NEXT occurrence, and on that weekday the next
#: occurrence is TODAY — so the fixture's service date stopped being in the future
#: and `test_the_END_OF_DAY_BATCH_DOES_NOT_SEE_IT` refused to pass vacuously. The
#: test was right 6 days in 7 and wrong on the seventh, latent since it was written.
#:
#: ⚠️ THE CONTROL IS WHAT FOUND IT, which is the argument for writing them. A version
#: without `assert before["scheduled_date"] > date.today()` would have gone green on
#: a Thursday while proving nothing about the date gate it is named for — and would
#: have gone green every Thursday after that too.
#:
#: Two days out is never today and never yesterday, whatever day the suite runs on.
_SERVICE_DAY = (date.today() + timedelta(days=2)).strftime("%A").lower()

ORDER = (
    "order for hopkins continental 34 Mary Smith 1948 to 2026 "
    "going to St. Mary's section 4 lot 12 "
    f"service at the church {_SERVICE_DAY} 10am full equipment nameplate only written"
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
           {"t": tenant, "n": 'Continental 34"'},
           "INSERT INTO products (id, company_id, name, sku, price, is_active) "
           "VALUES (:i, :t, :n, 'TRIGGERFIX-P1', 1850.00, true)")
    # ⚠️ ENSURED, NOT ASSUMED, FOR THE SAME REASON AS THE REST. r211 writes these on
    # a database where the sunnycrest tenant already exists; on a fresh CI database
    # the tenant arrives with the seed, AFTER migrations, so the migration correctly
    # no-ops and these rows are absent. Depending on it turned CI red.
    ensure("cemeteries", "company_id = :t AND name = :n",
           {"t": tenant, "n": "St. Mary's Cemetery"},
           "INSERT INTO cemeteries (id, company_id, name, city, state, is_active) "
           "VALUES (:i, :t, :n, 'Skaneateles', 'NY', true)")
    ensure("products", "company_id = :t AND name = :n",
           {"t": tenant, "n": "Full Equipment"},
           "INSERT INTO products (id, company_id, name, sku, price, is_active) "
           "VALUES (:i, :t, :n, 'TRIGGERFIX-CE1', 300.00, true)")

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
    """⚠️ THE JOB IS RUN, NOT ITS FILTER RESTATED. This is the test James asked for, and
    what it proves CHANGED on 2026-10-16 while the name stayed right.

    It used to move the service date into the PAST so that only `status='draft'` could
    be excluding the order — that was the point under D1, where the status was the whole
    protection. Step 3 makes Approve write `confirmed`, so the past-dated version of
    this test now asserts the opposite of the truth: a confirmed order whose service
    date has passed is exactly what the batch is FOR.

    The protection is now the DATE, so that is what is pinned: the order Approve just
    created, with its real service date in the future, comes out of a real batch run
    untouched. `test_the_batch_DOES_see_it_once_the_service_date_passes` below is the
    other half — without it this would be satisfied by a batch that never acts at all.
    """
    from datetime import date, timedelta

    from app.services.draft_invoice_service import generate_draft_invoices

    before = db.execute(
        text("SELECT status, scheduled_date, delivery_auto_confirmed, delivered_at "
             "FROM sales_orders WHERE id = :o"), {"o": approved}
    ).mappings().first()
    assert before["status"] == "confirmed"
    # ⚠️ ASSERTED, NOT ASSUMED. If the fixture's answers ever stopped carrying a future
    # service date, this test would pass for the wrong reason — the order would be
    # excluded by having no date rather than by having a later one.
    assert before["scheduled_date"] is not None, "the fixture lost its service date"
    assert before["scheduled_date"] > date.today(), (
        f"the fixture's service date is not in the future ({before['scheduled_date']}); "
        "this test would then prove nothing about the date gate"
    )

    generate_draft_invoices(db, tenant)
    db.commit()

    after = db.execute(
        text("SELECT status, delivery_auto_confirmed, delivered_at "
             "FROM sales_orders WHERE id = :o"), {"o": approved}
    ).mappings().first()
    assert after["status"] == "confirmed", after["status"]
    assert not after["delivery_auto_confirmed"]
    assert after["delivered_at"] is None

    from app.models.invoice import Invoice

    assert (
        db.query(Invoice).filter(Invoice.sales_order_id == approved).count() == 0
    ), "the batch invoiced an order whose service date has not arrived"


def test_and_the_batch_WOULD_have_taken_it_once_the_service_date_PASSES(db, tenant, approved):
    """⚠️ THE POSITIVE CONTROL, AND WITHOUT IT THE TEST ABOVE PROVES NOTHING.

    A batch that selected no orders at all — wrong tenant, mode off, a filter typo —
    would pass the exclusion test every time. This flips the one field under test, runs
    the same job, and shows the order IS taken: marked delivered and invoiced.

    ⚠️ WHAT GETS FLIPPED CHANGED ON 2026-10-16, AND THE TEST'S VALUE IS UNCHANGED. It
    was named `..._if_it_were_confirmed` and set BOTH `status='confirmed'` and a past
    service date, because under D1 the status was the thing being excluded. Approve now
    writes `confirmed`, so the status is no longer the variable — the SERVICE DATE is,
    and that is the only field this now moves. Its closing line used to read "That is
    the behaviour `draft` is protecting the office from"; the protection is the date.
    """
    from app.services.draft_invoice_service import generate_draft_invoices

    # ⚠️ ONLY THE DATE IS MOVED. Setting the status too would reintroduce two variables
    # and the test would no longer isolate the gate it is named for.
    db.execute(
        text("UPDATE sales_orders SET scheduled_date = CURRENT_DATE - 1 WHERE id = :o"),
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


def test_the_order_is_confirmed_but_NOT_delivered(db, approved):
    """⚠️ WAS `test_the_order_is_not_marked_delivered_or_confirmed` AND THE NAME CARRIED
    THE SUPERSEDED HALF. Under D1 the order was neither delivered nor confirmed; step 3
    makes it confirmed. Everything else the old test asserted still holds and is the
    part that matters — confirming is not delivering, and Approve must not pretend a
    vault has been placed.
    """
    row = db.execute(
        text("SELECT status, delivered_at, driver_confirmed, completed_at "
             "FROM sales_orders WHERE id = :o"), {"o": approved}
    ).mappings().first()
    assert row["status"] == "confirmed"
    assert row["delivered_at"] is None
    assert not row["driver_confirmed"]
    assert row["completed_at"] is None


def test_invoicing_it_directly_is_now_PERMITTED_and_that_is_the_point(db, tenant, approved):
    """⚠️ WAS `test_invoicing_it_directly_is_REFUSED_while_it_is_a_draft`, AND ITS
    SUBJECT IS GONE RATHER THAN BROKEN.

    Under D1 the order was a draft, so `create_invoice_from_order` refused it — "the
    guard below the guard". Step 3 makes it confirmed, which means an order the office
    wants to bill early CAN be billed, deliberately. That is not a weakening: the
    draft refusal still exists and still fires for an actual draft, which is asserted
    below rather than taken on trust.

    ⚠️ AND THE BATCH IS UNAFFECTED BY THIS. A hand-invoiced order drops out of the
    batch's net through `already_invoiced_order_ids`, so invoicing early cannot produce
    a second invoice on the service night — pinned in
    `tests/test_delivered_on_the_service_date.py`.
    """
    from fastapi import HTTPException

    from app.services import sales_service

    inv = sales_service.create_invoice_from_order(db, tenant, None, approved)
    db.commit()
    assert inv.number

    # the draft refusal still exists — proven against a real draft, not by reading
    db.execute(
        text("UPDATE sales_orders SET status = 'draft' WHERE id = :o"), {"o": approved}
    )
    db.execute(
        text("UPDATE invoices SET status = 'void' WHERE sales_order_id = :o"),
        {"o": approved},
    )
    db.commit()
    with pytest.raises(HTTPException) as e:
        sales_service.create_invoice_from_order(db, tenant, None, approved)
    assert e.value.status_code == 400
    assert "draft" in str(e.value.detail).lower()
