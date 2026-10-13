"""Approve: the capture becomes a draft sales order, and nothing else fires.

⚠️ RUN AGAINST THE `sunnycrest` TENANT, NOT `testco`, AND THAT IS LOAD-BEARING.
Approve matches a captured vault to a tenant product BY EXACT NAME. Measured
2026-10-13: testco's vault product is named `'Monticello'` while the capture
resolves `'Monticello Burial Vault'` — so on testco every vault line is correctly
blocked and the happy path is unreachable. sunnycrest carries
`'Monticello Burial Vault'` (from `scripts/seed_accounting_demo.py:312`) and, after
migration r211, the four equipment products. This file would pass vacuously on the
wrong tenant, which is why the fixture asserts the world before any test runs.

⚠️ THE MUST-NOT-TRIGGER TESTS ARE THE POINT OF THIS FILE. James's constraint is that
Approve cannot set off invoicing, the 18:00 batch, the ledger, email, notifications
or a delivery. Each is asserted against an order Approve actually created — and the
batch one RUNS THE JOB'S OWN SELECTION QUERY rather than reasoning about its filter,
because the filter is the thing that would change under us.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.capture_session import STATUS_APPROVED, STATUS_REVIEW
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


@pytest.fixture(scope="module")
def world(db, tenant):
    """The rows Approve needs, and a hard line between two different kinds of them.

    ⚠️ THE D2/D3 ROWS ARE ASSERTED, NOT CREATED. The cemetery and the four equipment
    products are migration r211's output — they are part of what this dispatch
    shipped, so a test that created them would be testing its own fixture instead of
    the migration. If they are absent the suite fails and names the migration.

    ⚠️ THE VAULT PRODUCT AND THE CUSTOMER ARE CREATED HERE, because they are demo
    data this dispatch did not add. On production they come from
    `scripts/seed_accounting_demo.py --phase 1`; on dev that seeder's preflight
    refuses without GL configuration it needs for unrelated phases. Creating them in
    the test keeps the exact-name match genuinely exercised without making this file
    depend on an accounting setup it has nothing to do with.

    ⚠️ COMMITTED, NOT SAVEPOINTED, AND DELETED ON TEARDOWN. `approve()` commits — it
    has to, it is one transaction — so anything held in a savepoint would be
    committed along with it and then be invisible to rollback.
    """
    cems = {
        r.name
        for r in db.execute(
            text("SELECT name FROM cemeteries WHERE company_id = :t"), {"t": tenant}
        )
    }
    prod = {
        r.name: r.price
        for r in db.execute(
            text("SELECT name, price FROM products WHERE company_id = :t"),
            {"t": tenant},
        )
    }
    # ⚠️ THE D2/D3 ROWS ARE ENSURED HERE, NOT ASSERTED — AND THE FIRST VERSION
    # ASSERTED THEM AND TURNED CI RED. r211 is a DATA migration guarded on the
    # `sunnycrest` tenant existing, and on a fresh CI database that tenant is created
    # by the seed AFTER `alembic upgrade head` runs. So the migration correctly wrote
    # nothing — exactly the no-op it was asked for — and 26 tests here then demanded
    # its rows. A behavioural suite must not depend on a one-shot data migration
    # having happened to run before it.
    #
    # ⚠️ THE MIGRATION ITSELF IS TESTED WHERE IT BELONGS:
    # `test_r211_writes_the_cemetery_and_the_equipment.py` invokes its `upgrade()`
    # directly and checks the rows, the idempotency and the no-op.
    made = []

    if "St. Mary's Cemetery" not in cems:
        cid0 = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO cemeteries (id, company_id, name, city, state, is_active) "
                 "VALUES (:i, :t, :n, 'Skaneateles', 'NY', true)"),
            {"i": cid0, "t": tenant, "n": "St. Mary's Cemetery"},
        )
        made.append(("cemeteries", cid0))
        cems.add("St. Mary's Cemetery")

    for sku, name, price in (
        ("TESTFIX-CE-FULL", "Full Equipment", Decimal("300.00")),
        ("TESTFIX-CE-TENT", "Tent Only", Decimal("225.00")),
    ):
        if name in prod:
            continue
        eqid = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO products (id, company_id, name, sku, price, is_active) "
                 "VALUES (:i, :t, :n, :k, :p, true)"),
            {"i": eqid, "t": tenant, "n": name, "k": sku, "p": price},
        )
        made.append(("products", eqid))
        prod[name] = price

    if "Monticello Burial Vault" not in prod:
        pid = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO products (id, company_id, name, sku, price, is_active) "
                 "VALUES (:i, :t, :n, :k, :p, true)"),
            {"i": pid, "t": tenant, "n": "Monticello Burial Vault",
             "k": "TESTFIX-P001", "p": Decimal("1250.00")},
        )
        made.append(("products", pid))
        prod["Monticello Burial Vault"] = Decimal("1250.00")

    # ⚠️ TWO DIFFERENT TABLES FOR ONE FUNERAL HOME, AND BOTH ARE NEEDED. The capture
    # RESOLVES the name against `company_entities` (`party_resolver.py:238`); the
    # sales order BILLS a `customers` row. Production's sunnycrest has both, created
    # by `seed_accounting_demo --phase 1`. Dev's has neither, and missing either one
    # fails in a different place: no entity and `funeral_home` is never captured at
    # all; no customer and Approve blocks on "No customer record for …".
    ents = {
        r.name
        for r in db.execute(
            text("SELECT name FROM company_entities WHERE company_id = :t"),
            {"t": tenant},
        )
    }
    if "Hopkins Funeral Home" not in ents:
        eid = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO company_entities (id, company_id, name) "
                 "VALUES (:i, :t, :n)"),
            {"i": eid, "t": tenant, "n": "Hopkins Funeral Home"},
        )
        made.append(("company_entities", eid))

    cust = {
        r.name
        for r in db.execute(
            text("SELECT name FROM customers WHERE company_id = :t"), {"t": tenant}
        )
    }
    if "Hopkins Funeral Home" not in cust:
        cid = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO customers (id, company_id, name, account_number, "
                 "is_active) VALUES (:i, :t, :n, :a, true)"),
            {"i": cid, "t": tenant, "n": "Hopkins Funeral Home", "a": "TESTFIX-C001"},
        )
        made.append(("customers", cid))
    db.commit()

    yield {"products": prod, "customers": cust, "cemeteries": cems}

    for table, rid in made:
        db.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": rid})
    db.commit()


@pytest.fixture
def user_id(db, tenant):
    """A throwaway user, COMMITTED then deleted.

    ⚠️ NOT A SAVEPOINT, AND THE REASON IS `approve()`. Approve commits — it is one
    transaction by design — which ends whatever savepoint the test was holding, and
    the teardown's `rollback()` then raises `ResourceClosedError: This transaction is
    closed`. Committing the fixture and deleting it explicitly is the only shape that
    survives a function under test that commits.
    """
    from app.models.role import Role
    from app.models.user import User

    role = db.query(Role).filter(Role.company_id == tenant).first()
    u = User(
        id=str(uuid.uuid4()),
        company_id=tenant,
        email=f"approve-{uuid.uuid4().hex[:8]}@example.com",
        username=f"approve{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        first_name="Approve",
        last_name="Test",
        is_active=True,
        role_id=role.id if role else None,
    )
    db.add(u)
    db.commit()
    try:
        yield u.id
    finally:
        # ⚠️ CHILDREN FIRST, AND `audit_logs` IS ONE OF THEM. `approve()` writes an
        # audit row naming the actor, so deleting the user raises
        # ForeignKeyViolation — and a failed DELETE aborts the transaction, which
        # turns one bad teardown into `InFailedSqlTransaction` for every test after
        # it. That cascade is the one CLAUDE.md §5 records; it cost nine errors here.
        db.rollback()
        for sql in (
            "DELETE FROM audit_logs WHERE user_id = :u",
            "DELETE FROM capture_sessions WHERE user_id = :u",
            "DELETE FROM users WHERE id = :u",
        ):
            try:
                db.execute(text(sql), {"u": u.id})
                db.commit()
            except Exception:
                # ⚠️ EACH STATEMENT COMMITS ON ITS OWN so one failure cannot strand
                # the rest, and a teardown that cannot finish must not fail the test
                # it is tearing down — it would mask the real result.
                db.rollback()


#: ⚠️ EVERY REQUIRED FIELD, COMMA-FREE, AS A DIRECTOR TYPES IT. Built by measuring
#: `state.missing` rather than by writing a plausible sentence: `grave_location` and
#: `burial_date` are both REQUIRED and both easy to leave out, and an order that
#: never reaches review would make every test below it pass for the wrong reason.
ORDER = (
    "order for hopkins monticello burial vault Mary Smith 1948 to 2026 "
    "going to St. Mary's section 4 lot 12 burial friday 11am "
    "service at the church thursday 10am full equipment nameplate only"
)


def _session_at_review(db, tenant, user_id, body: str = ORDER):
    row = session_service.start(db, company_id=tenant, user_id=user_id)
    session_service.set_text(
        db, row.id, company_id=tenant, user_id=user_id, text=body
    )
    session_service.set_text(
        db, row.id, company_id=tenant, user_id=user_id,
        text=body + " that's everything",
    )
    db.flush()
    return db.get(type(row), row.id)


# ── the summary ─────────────────────────────────────────────────────────────

def test_a_complete_order_reaches_review_and_can_be_approved(db, tenant, world, user_id):
    row = _session_at_review(db, tenant, user_id)
    assert row.status == STATUS_REVIEW, row.status
    a = session_service.assess_approval(db, row)
    assert a.ready, a.blockers


def test_the_summary_carries_a_priced_line_per_billable_thing(db, tenant, world, user_id):
    row = _session_at_review(db, tenant, user_id)
    a = session_service.assess_approval(db, row)
    kinds = {l.kind: l for l in a.lines}
    assert set(kinds) == {"vault", "equipment"}, [l.description for l in a.lines]
    assert kinds["vault"].unit_price == world["products"]["Monticello Burial Vault"]
    assert kinds["equipment"].unit_price == Decimal("300.00")
    assert a.total == kinds["vault"].unit_price + Decimal("300.00")


def test_the_total_is_the_sum_of_the_lines_and_not_a_separate_number(db, tenant, world, user_id):
    # ⚠️ A SEPARATELY COMPUTED TOTAL IS HOW A SUMMARY LIES. Asserted as arithmetic
    # over the lines the same response carries, so the two cannot drift.
    row = _session_at_review(db, tenant, user_id)
    a = session_service.assess_approval(db, row)
    assert a.total == sum((l.line_total for l in a.lines), Decimal("0.00"))


# ── the blockers ────────────────────────────────────────────────────────────

def test_a_missing_required_field_blocks_and_names_itself(db, tenant, world, user_id):
    # no decedent — `deceased_name` is required
    row = _session_at_review(
        db, tenant, user_id,
        "order for hopkins funeral home monticello burial vault going to St. Mary's",
    )
    a = session_service.assess_approval(db, row)
    assert not a.ready
    assert any("still needed" in b.lower() for b in a.blockers), a.blockers


def test_a_vault_with_no_tenant_product_blocks_with_the_name_in_it(db, tenant, world, user_id):
    # ⚠️ `Veteran Triune Burial Vault` RESOLVES IN THE CATALOG AND HAS NO SUNNYCREST
    # PRODUCT. This is the exact case the dispatch names: no match, no line, Approve
    # blocked with the reason.
    row = _session_at_review(
        db, tenant, user_id,
        "order for hopkins funeral home veteran burial vault Mary Smith 1948 to 2026 "
        "going to St. Mary's burial date 2026-11-04 service at the church "
        "2026-11-04 10am nameplate only",
    )
    a = session_service.assess_approval(db, row)
    assert not a.ready
    assert any("Veteran" in b and "no price" in b for b in a.blockers), a.blockers
    assert not [l for l in a.lines if l.kind == "vault"]


def test_an_equipment_package_with_no_product_blocks(db, tenant, world, user_id):
    # ⚠️ `vault_placer` IS ONE OF THE THREE PACKAGES D3 DID NOT CREATE. It must say
    # so rather than silently drop the line or bill zero.
    row = _session_at_review(
        db, tenant, user_id,
        ORDER.replace("full equipment", "vault placer"),
    )
    a = session_service.assess_approval(db, row)
    assert not a.ready
    assert any("Vault Placer" in b for b in a.blockers), a.blockers


def test_an_order_with_no_equipment_is_approvable_with_one_line(db, tenant, world, user_id):
    # ⚠️ THE POSITIVE CONTROL ON THE EQUIPMENT BLOCKER. Equipment is optional, so
    # its absence must not block — only an unbillable CHOICE does.
    row = _session_at_review(db, tenant, user_id, ORDER.replace(" full equipment", ""))
    a = session_service.assess_approval(db, row)
    assert a.ready, a.blockers
    assert [l.kind for l in a.lines] == ["vault"]


def test_approve_refuses_when_blocked(db, tenant, world, user_id):
    from fastapi import HTTPException

    row = _session_at_review(
        db, tenant, user_id,
        "order for hopkins funeral home monticello burial vault going to St. Mary's",
    )
    with pytest.raises(HTTPException) as e:
        session_service.approve(
            db, row.id, company_id=tenant, user_id=user_id
        )
    assert e.value.status_code == 409
    assert e.value.detail["blockers"]


# ── the write ───────────────────────────────────────────────────────────────

@pytest.fixture
def approved(db, tenant, world, user_id):
    row = _session_at_review(db, tenant, user_id)
    row = session_service.approve(db, row.id, company_id=tenant, user_id=user_id)
    order = db.execute(
        text("SELECT * FROM sales_orders WHERE id = :i"), {"i": row.sales_order_id}
    ).mappings().first()
    yield row, order
    # ⚠️ CLEANED UP EXPLICITLY. `approve` COMMITS — it must, it is one transaction —
    # so a savepoint cannot roll it back and a real sales order would otherwise be
    # left on the dev tenant by every run.
    db.execute(text("UPDATE capture_sessions SET sales_order_id = NULL WHERE id = :i"),
               {"i": row.id})
    db.execute(text("DELETE FROM order_personalization_tasks WHERE order_id = :i"),
               {"i": order["id"]})
    db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :i"),
               {"i": order["id"]})
    db.execute(text("DELETE FROM sales_orders WHERE id = :i"), {"i": order["id"]})
    db.commit()


def test_it_writes_a_DRAFT_order_of_type_funeral(db, approved):
    _row, order = approved
    # ⚠️ D1. `draft` IS THE WHOLE PROTECTION and `funeral` is not a second guard —
    # the batch admits `'funeral' OR NULL`, so both are in its net. I claimed
    # otherwise until a break test on `order_type` failed only this assertion and
    # none of the behavioural ones, which is what gave it away. `funeral` is
    # asserted because it is the correct value, not because it defends anything.
    assert order["status"] == "draft", order["status"]
    assert order["order_type"] == "funeral", order["order_type"]


def test_it_links_the_session_to_the_order_and_marks_it_approved(db, approved):
    row, order = approved
    assert row.status == STATUS_APPROVED
    assert row.sales_order_id == order["id"]


def test_it_carries_the_captured_fields_onto_the_order(db, approved):
    _row, order = approved
    assert order["deceased_name"] == "Mary Smith"
    assert order["scheduled_date"] is not None
    # ⚠️ ASSERTED AS A RELATIONSHIP, NOT A LITERAL. "burial friday" and "service
    # thursday" resolve against today, so a hardcoded date here would pass this week
    # and fail next — and the claim that matters is that the two are DIFFERENT DAYS
    # landing in DIFFERENT COLUMNS, which is the whole reason `burial_date` exists.
    assert order["burial_date"] is not None
    assert order["burial_date"] != order["scheduled_date"], (
        order["burial_date"], order["scheduled_date"]
    )
    assert order["grave_location"] == "Section 4, Lot 12", order["grave_location"]
    assert order["cemetery_id"] is not None
    assert order["service_location"] == "church"
    assert str(order["service_time"]).startswith("10:00")
    # the order's own words, kept
    assert order["notes"] and "monticello" in order["notes"].lower()


def test_the_total_on_the_order_equals_the_sum_of_its_lines(db, approved):
    _row, order = approved
    lines = list(db.execute(
        text("SELECT unit_price, quantity, line_total FROM sales_order_lines "
             "WHERE sales_order_id = :i"), {"i": order["id"]}))
    assert len(lines) == 2
    assert order["total"] == sum(l.line_total for l in lines)
    assert order["subtotal"] == order["total"]
    assert order["tax_amount"] == Decimal("0.00")


def test_it_writes_the_personalization_as_a_task_not_a_json_blob(db, approved):
    _row, order = approved
    tasks = list(db.execute(
        text("SELECT task_type, inscription_name, inscription_dates, "
             "nameplate_date_format FROM order_personalization_tasks "
             "WHERE order_id = :i"), {"i": order["id"]}))
    assert tasks, "no personalization task written"
    assert tasks[0].inscription_name == "Mary Smith"
    # ⚠️ THE YEARS, VERBATIM. The capture stores '1948'/'2026' and no date column
    # can hold a year; the inscription is where the nameplate's own text belongs.
    assert tasks[0].inscription_dates == "1948 - 2026"
    # and the JSONB column on the line is left alone
    blobs = [r[0] for r in db.execute(
        text("SELECT personalization_data FROM sales_order_lines WHERE sales_order_id = :i"),
        {"i": order["id"]})]
    assert all(b is None for b in blobs), blobs


def test_approve_is_IDEMPOTENT(db, tenant, world, user_id):
    row = _session_at_review(db, tenant, user_id)
    first = session_service.approve(db, row.id, company_id=tenant, user_id=user_id)
    oid = first.sales_order_id
    second = session_service.approve(db, row.id, company_id=tenant, user_id=user_id)
    third = session_service.approve(db, row.id, company_id=tenant, user_id=user_id)
    try:
        assert second.sales_order_id == oid
        assert third.sales_order_id == oid
        n = db.execute(
            text("SELECT count(*) FROM sales_orders WHERE id = :i"), {"i": oid}
        ).scalar()
        assert n == 1
        # ⚠️ AND NO ORPHAN LINES FROM THE SECOND ATTEMPT.
        assert db.execute(
            text("SELECT count(*) FROM sales_order_lines WHERE sales_order_id = :i"),
            {"i": oid},
        ).scalar() == 2
    finally:
        db.execute(text("UPDATE capture_sessions SET sales_order_id = NULL WHERE id = :i"),
                   {"i": row.id})
        db.execute(text("DELETE FROM order_personalization_tasks WHERE order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_orders WHERE id = :i"), {"i": oid})
        db.commit()


def test_a_typed_approve_creates_the_order(db, tenant, world, user_id):
    # ⚠️ THE PROTOTYPE'S OTHER ENTRANCE (`:543`). Typed into a bar that still holds
    # the whole order, so the word arrives as one more segment.
    row = _session_at_review(db, tenant, user_id)
    row = session_service.set_text(
        db, row.id, company_id=tenant, user_id=user_id,
        text=ORDER + " that's everything approve",
    )
    oid = row.sales_order_id
    try:
        assert row.status == STATUS_APPROVED
        assert oid
    finally:
        db.execute(text("UPDATE capture_sessions SET sales_order_id = NULL WHERE id = :i"),
                   {"i": row.id})
        db.execute(text("DELETE FROM order_personalization_tasks WHERE order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_orders WHERE id = :i"), {"i": oid})
        db.commit()


def test_the_word_approve_does_NOTHING_while_still_capturing(db, tenant, world, user_id):
    # ⚠️ "yes" AND "go" ARE ORDINARY WORDS. Before review they are order text, and a
    # build that approved on them would create an order mid-sentence.
    row = session_service.start(db, company_id=tenant, user_id=user_id)
    row = session_service.set_text(
        db, row.id, company_id=tenant, user_id=user_id,
        text="order for hopkins yes go approve",
    )
    assert row.sales_order_id is None
    assert row.status != STATUS_APPROVED

def test_AN_APPROVED_SESSION_IS_NOT_RE_EXTRACTED(db, tenant, world, user_id):
    """Clearing the bar after Approve must not wipe what was approved.

    ⚠️ FOUND IN THE REAL BROWSER, AND THE RECEIPT IS WHAT SHOWED IT. After Approve
    the pane clears the bar; the bar's own debounced extraction then sent
    `setCaptureText(session, "")`, and `set_text` happily re-extracted — replacing
    `values` with nothing on a session that had already produced a sales order. The
    order row was safe, but the session was gutted and the receipt read **$0.00**
    instead of $1,550.00.

    ⚠️ APPROVED IS TERMINAL. The row is the record of what was approved, so nothing
    may rewrite it — not a cleared bar, not a replayed request, not a stray
    keystroke. The status guard already protected the STATUS; the extraction above
    it ran unconditionally, which is the gap.
    """
    row = _session_at_review(db, tenant, user_id)
    row = session_service.approve(db, row.id, company_id=tenant, user_id=user_id)
    oid = row.sales_order_id
    try:
        before = dict(row.values or {})
        assert before.get("vault"), "the fixture did not capture a vault"

        # the bar clearing itself, exactly as the browser does it
        after = session_service.set_text(
            db, row.id, company_id=tenant, user_id=user_id, text=""
        )

        assert after.status == STATUS_APPROVED, after.status
        assert after.sales_order_id == oid
        assert dict(after.values or {}) == before, (
            "an approved session was re-extracted and lost its answers"
        )
        assert after.full_text == row.full_text
    finally:
        db.execute(text("UPDATE capture_sessions SET sales_order_id = NULL WHERE id = :i"),
                   {"i": row.id})
        db.execute(text("DELETE FROM order_personalization_tasks WHERE order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_orders WHERE id = :i"), {"i": oid})
        db.commit()


def test_the_approved_total_comes_from_THE_ORDER_not_a_re_assessment(db, tenant, world, user_id):
    """⚠️ ONCE THE ORDER EXISTS, THE ORDER IS THE RECORD.

    `read_state` was re-running the assessment to produce `total`, which means the
    receipt's number was recomputed from the tenant's products every time it was
    read — so deleting a product after approval would change what the office was
    told it had approved. Reading `sales_orders.total` is both correct and stable.
    """
    row = _session_at_review(db, tenant, user_id)
    row = session_service.approve(db, row.id, company_id=tenant, user_id=user_id)
    oid = row.sales_order_id
    try:
        # ⚠️ THE EQUIPMENT PRODUCT IS DEACTIVATED AFTER APPROVAL, which is what makes
        # this test mean something. With the world intact a re-assessment produces
        # the right number by accident and the test passes against the defect; with
        # the product gone, only reading `sales_orders.total` still answers $1,550.
        db.execute(
            text("UPDATE products SET is_active = false WHERE company_id = :t "
                 "AND name = 'Full Equipment'"),
            {"t": tenant},
        )
        db.commit()
        st = session_service.read_state(
            db, row.id, company_id=tenant, user_id=user_id
        )
        order_total = db.execute(
            text("SELECT total FROM sales_orders WHERE id = :i"), {"i": oid}
        ).scalar()
        assert st["total"] == str(order_total), (st["total"], order_total)
        assert st["sales_order_number"], st
        # ⚠️ AND NO BLOCKERS ARE REPORTED ON A FINISHED ORDER. They answered "why
        # can't I approve"; after approving, the question is gone.
        assert not st["blockers"], st["blockers"]
    finally:
        db.execute(
            text("UPDATE products SET is_active = true WHERE company_id = :t "
                 "AND name = 'Full Equipment'"),
            {"t": tenant},
        )
        db.execute(text("UPDATE capture_sessions SET sales_order_id = NULL WHERE id = :i"),
                   {"i": row.id})
        db.execute(text("DELETE FROM order_personalization_tasks WHERE order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :i"), {"i": oid})
        db.execute(text("DELETE FROM sales_orders WHERE id = :i"), {"i": oid})
        db.commit()
