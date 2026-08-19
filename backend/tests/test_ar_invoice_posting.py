"""INV-1 A-2 — the invoice writes its journal entry.

⚠️ THE DEBIT THAT HAS NEVER EXISTED. Measured on PRODUCTION 2026-08-19:
`1200 ACCOUNTS RECEIVABLE-TRADE` carries **Dr 0.00 against Cr 33,845.00** over
14 lines. `post_payment` credits AR at receipt; `post_invoice_to_ar` moved a
denormalised customer balance and wrote no entry at all. The control account
only ever moved one way. These tests pin the missing debit.

⚠️ AND THE PERIOD-LOCK REFUSAL HAS NEVER EXECUTED ANYWHERE. `period_locks` has
ZERO rows on every production tenant (measured the same day), so the guard
`create_journal_entry` carries has never been reached from any path. It is
verified here rather than assumed — this week has three instances of a guard
that was correct and unexercised turning out to be wrong when first reached.

Bare-database safe: creates only `companies` (via the shared fixture),
`customers`, `invoices`, `tenant_gl_mappings` and `period_locks`. No products,
no users, no seeded chart.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.invoice import Invoice
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.services import ar_invoice_posting as posting
from app.services.early_payment_discount_service import ACCOUNTING_GL_SETTINGS_KEY

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID

# ⚠️ ONLY `tenant_id`-SCOPED TABLES BELONG HERE. `_tenant.drop_company` sweeps
# every child table with a hardcoded `WHERE tenant_id = :i`, so passing
# `invoices` or `customers` — which scope by `company_id` — raises
# `UndefinedColumn` in teardown. And it raises ONLY on the bare axis, because on
# a seeded machine the fixture created nothing and returns before sweeping. That
# is the seeded-vs-bare inversion for the third time this week.
#
# Those two tables are swept create-scoped by `_LEAKY` below, which runs first
# (function scope tears down before module scope), so the company delete finds
# no children either way. `_tenant.drop_company` resolving the column per table
# would fix this for everyone — recorded as a follow-up rather than folded into
# a feature commit, since it is shared test infrastructure.
canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("journal_entry_lines", "journal_entries",
                  "tenant_gl_mappings", "period_locks"),
)


#: Tables this file writes that a COMMIT makes permanent, with the column each
#: scopes by, in FK-safe deletion order.
#:
#: ⚠️ ROLLBACK IS NOT TEARDOWN HERE, BECAUSE `void_invoice` COMMITS. Most of this
#: file only flushes, but the one test that exercises the real void path commits
#: through it — and a rollback-only fixture would leak exactly the rows that test
#: creates. Create-scoped, per `tests/_tenant.py`: snapshot what exists, remove
#: only what appeared, never a blanket purge of the shared tenant.
#:
#: ORDER IS LOAD-BEARING: `invoices.journal_entry_id` references
#: `journal_entries`, and `journal_entry_lines` references it too, so both go
#: first. `invoices.customer_id` references `customers`, so customers go last.
_LEAKY = (
    # `void_invoice` writes an audit row and COMMITS it. Nothing else in this
    # file commits, and `_tenant.drop_company` does not sweep `audit_logs`, so
    # without this the company delete fails on `audit_logs_company_id_fkey` —
    # bare axis only, since a seeded machine never reaches that teardown.
    ("audit_logs", "company_id"),
    ("journal_entry_lines", "tenant_id"),
    ("invoices", "company_id"),
    ("journal_entries", "tenant_id"),
    ("customers", "company_id"),
    ("tenant_gl_mappings", "tenant_id"),
    ("period_locks", "tenant_id"),
)


def _ids(s, table: str, col: str) -> set[str]:
    return {r[0] for r in s.execute(
        text(f"SELECT id FROM {table} WHERE {col} = :c"), {"c": TENANT})}


@pytest.fixture
def db():
    """Create-scoped teardown + settings restoration."""
    from app.database import SessionLocal

    s = SessionLocal()
    before_settings = s.execute(
        text("SELECT settings_json FROM companies WHERE id = :i"), {"i": TENANT}
    ).scalar()
    before = {t: _ids(s, t, c) for t, c in _LEAKY}
    before_jobs = _ids(s, "agent_jobs", "tenant_id")
    try:
        yield s
    finally:
        s.rollback()
        new_jobs = _ids(s, "agent_jobs", "tenant_id") - before_jobs
        if new_jobs:
            s.execute(text("DELETE FROM agent_anomalies WHERE agent_job_id = ANY(:i)"),
                      {"i": list(new_jobs)})
            s.execute(text("DELETE FROM agent_jobs WHERE id = ANY(:i)"),
                      {"i": list(new_jobs)})
        for table, col in _LEAKY:
            fresh = _ids(s, table, col) - before[table]
            if fresh:
                s.execute(text(f"DELETE FROM {table} WHERE id = ANY(:i)"),
                          {"i": list(fresh)})
        s.execute(text("UPDATE companies SET settings_json = :v WHERE id = :i"),
                  {"v": before_settings, "i": TENANT})
        s.commit()
        s.close()


def _mapping(db, number: str, name: str, category: str = "current_asset") -> str:
    mid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.execute(text(
        "INSERT INTO tenant_gl_mappings (id, tenant_id, platform_category, "
        " account_number, account_name, is_active, created_at, updated_at) "
        "VALUES (:i,:t,:c,:n,:nm,true,:ts,:ts)"),
        {"i": mid, "t": TENANT, "c": category, "n": number, "nm": name, "ts": now})
    db.flush()
    return mid


def _configure(db, *, ar: str | None, revenue: str | None):
    row = db.execute(text("SELECT settings_json FROM companies WHERE id = :i"),
                     {"i": TENANT}).scalar()
    cur = json.loads(row) if row else {}
    gl = {}
    if ar:
        gl["ar"] = ar
    if revenue:
        gl["revenue"] = revenue
    cur[ACCOUNTING_GL_SETTINGS_KEY] = gl
    db.execute(text("UPDATE companies SET settings_json = :v WHERE id = :i"),
               {"v": json.dumps(cur), "i": TENANT})
    db.flush()


def _customer(db) -> str:
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.execute(text(
        "INSERT INTO customers (id, company_id, name, current_balance, "
        " created_at, updated_at) VALUES (:i,:t,'Test Customer',0,:ts,:ts)"),
        {"i": cid, "t": TENANT, "ts": now})
    db.flush()
    return cid


def _invoice(db, *, total="1000.00", when: date | None = None) -> Invoice:
    inv = Invoice(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=_customer(db),
        number=f"INV-T-{uuid.uuid4().hex[:6]}", status="draft",
        invoice_date=when or datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        subtotal=Decimal(total), tax_amount=Decimal("0.00"),
        total=Decimal(total),
    )
    db.add(inv)
    db.flush()
    return inv


def _fully_configured(db):
    ar = _mapping(db, "1200", "ACCOUNTS RECEIVABLE-TRADE", "current_asset")
    rev = _mapping(db, "5010", "PRECAST SALES", "cogs")
    _configure(db, ar=ar, revenue=rev)
    return ar, rev


def _lines(db, entry_id):
    return db.query(JournalEntryLine).filter(
        JournalEntryLine.journal_entry_id == entry_id
    ).order_by(JournalEntryLine.line_number).all()


class TestTheMissingDebit:
    def test_it_books_dr_ar_cr_revenue(self, db):
        _fully_configured(db)
        inv = _invoice(db, total="1000.00")

        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert entry is not None, "the invoice did not post"

        lines = _lines(db, entry.id)
        assert len(lines) == 2
        by_acct = {ln.gl_account_number: ln for ln in lines}

        # ⚠️ HAND-COMPUTED, NOT DERIVED FROM THE CODE UNDER TEST. A 1000.00
        # invoice debits AR 1000.00 and credits revenue 1000.00. Stated as
        # literals so the arithmetic is checkable by reading.
        assert by_acct["1200"].debit_amount == Decimal("1000.00")
        assert by_acct["1200"].credit_amount == Decimal("0.00")
        assert by_acct["5010"].credit_amount == Decimal("1000.00")
        assert by_acct["5010"].debit_amount == Decimal("0.00")
        assert entry.total_debits == entry.total_credits == Decimal("1000.00")

    def test_the_ar_leg_is_a_DEBIT_which_is_the_whole_point(self, db):
        """⚠️ THE DIRECTION IS THE DEFECT. Production's AR reads Dr 0.00 /
        Cr 33,845.00 because only payments touched it. If this leg were ever
        written as a credit the arc would have changed nothing while looking
        finished."""
        _fully_configured(db)
        inv = _invoice(db, total="500.00")
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        ar_line = next(ln for ln in _lines(db, entry.id) if ln.gl_account_number == "1200")
        assert ar_line.debit_amount > 0 and ar_line.credit_amount == 0

    def test_the_invoice_points_at_its_entry(self, db):
        """Without the link, "which invoices are unposted" is unanswerable — and
        fail-open makes that question load-bearing."""
        _fully_configured(db)
        inv = _invoice(db)
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert inv.journal_entry_id == entry.id

    def test_the_entry_carries_its_own_numbering_not_reconciliations(self, db):
        """⚠️ `post_payment` REUSES `_book_two_legged_entry` AND INHERITS
        `RECON-` NUMBERING: every payment entry on production reads
        `RECON-1001..1015` with `entry_type='reconciliation'` though no
        reconciliation produced them. Invoice revenue filed under reconciliation
        would make the register illegible the same way."""
        _fully_configured(db)
        inv = _invoice(db)
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert entry.entry_number.startswith("INV-")
        assert entry.entry_type == "invoice"

    def test_the_full_total_posts_including_tax(self, db):
        """⚠️ PINNED BECAUSE IT IS AN ASSUMPTION WITH AN EXPIRY. Measured on
        production: `tax_amount` is 0.00 on every issued invoice on every
        tenant, so total == subtotal and there is no tax leg to split. The
        moment a nonzero tax amount appears this test fails and the split has to
        be designed — which is the point of asserting it rather than leaving it
        implicit."""
        _fully_configured(db)
        inv = _invoice(db, total="1000.00")
        assert inv.tax_amount == Decimal("0.00"), "the tax assumption changed"
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert entry.total_debits == inv.total


class TestFailOpenOnTheRecord:
    def test_an_unconfigured_tenant_gets_no_entry_and_no_exception(self, db):
        _configure(db, ar=None, revenue=None)
        inv = _invoice(db)
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert entry is None
        assert inv.journal_entry_id is None

    def test_the_gap_is_REPORTED_not_swallowed(self, db):
        """Fail-open is only safe if the gap is visible; otherwise it is a
        silently incomplete ledger, which is the failure the arc exists to
        remove."""
        from app.models.agent_anomaly import AgentAnomaly

        _configure(db, ar=None, revenue=None)
        inv = _invoice(db)
        posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)

        anomaly = db.query(AgentAnomaly).filter(
            AgentAnomaly.entity_type == "invoice",
            AgentAnomaly.entity_id == inv.id,
        ).first()
        assert anomaly is not None, "an unposted invoice reported nothing"
        assert anomaly.anomaly_type == "ar_invoice_unposted"
        assert "accounts-receivable" in anomaly.description
        assert inv.number in anomaly.description

    def test_revenue_unconfigured_reports_the_revenue_reason(self, db):
        from app.models.agent_anomaly import AgentAnomaly

        ar = _mapping(db, "1200", "AR-TRADE")
        _configure(db, ar=ar, revenue=None)
        inv = _invoice(db)
        assert posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None) is None

        anomaly = db.query(AgentAnomaly).filter(
            AgentAnomaly.entity_id == inv.id).first()
        assert "sales-revenue" in anomaly.description

    def test_a_zero_total_invoice_posts_nothing_and_reports_nothing(self, db):
        """Not a refusal — there is no gap an operator could configure away."""
        from app.models.agent_anomaly import AgentAnomaly

        _fully_configured(db)
        inv = _invoice(db, total="0.00")
        assert posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None) is None
        assert db.query(AgentAnomaly).filter(
            AgentAnomaly.entity_id == inv.id).first() is None


class TestThePeriodLockRefusal:
    """⚠️ THIS GUARD HAS NEVER RUN. `period_locks` is empty on every production
    tenant, so `create_journal_entry`'s lock check has never been reached from
    any path. Verified rather than assumed."""

    def _lock(self, db, start: date, end: date):
        db.execute(text(
            "INSERT INTO period_locks (id, tenant_id, period_start, period_end, "
            " locked_at, is_active, created_at) "
            "VALUES (:i,:t,:s,:e,:ts,true,:ts)"),
            {"i": str(uuid.uuid4()), "t": TENANT, "s": start, "e": end,
             "ts": datetime.now(timezone.utc)})
        db.flush()

    def test_the_lock_actually_refuses(self, db):
        _fully_configured(db)
        when = date(2026, 3, 15)
        self._lock(db, date(2026, 3, 1), date(2026, 3, 31))
        inv = _invoice(db, when=when)

        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert entry is None, "an invoice posted into a LOCKED period"
        assert inv.journal_entry_id is None

    def test_the_refusal_is_reported_as_a_locked_period_not_a_config_gap(self, db):
        """The operator's fix differs: a config gap is fixed on the panel, a
        closed period is fixed by unlocking or re-dating. One reason for both
        would send them to the wrong place."""
        from app.models.agent_anomaly import AgentAnomaly

        _fully_configured(db)
        self._lock(db, date(2026, 3, 1), date(2026, 3, 31))
        inv = _invoice(db, when=date(2026, 3, 15))
        posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)

        anomaly = db.query(AgentAnomaly).filter(
            AgentAnomaly.entity_id == inv.id).first()
        assert anomaly is not None
        assert "closed accounting period" in anomaly.description

    def test_the_invoice_still_stands(self, db):
        """Fail-open on the RECORD. A period closed after the fact must not
        block issuing."""
        _fully_configured(db)
        self._lock(db, date(2026, 3, 1), date(2026, 3, 31))
        inv = _invoice(db, when=date(2026, 3, 15))
        posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert db.query(Invoice).filter(Invoice.id == inv.id).first() is not None

    def test_an_unlocked_period_still_posts(self, db):
        """The control. A guard that refused everything would satisfy the tests
        above and break the feature."""
        _fully_configured(db)
        self._lock(db, date(2026, 3, 1), date(2026, 3, 31))
        inv = _invoice(db, when=date(2026, 6, 15))   # outside the lock
        assert posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None) is not None


class TestVoidingReversesTheEntry:
    """⚠️ AR-2's VOID BUG IS THE PRECEDENT. `_undo_entry` was written for the
    payment path and MISSED `discount_journal_entry_id`, leaving a posted entry
    standing behind a voided payment. An invoice points at one entry, so the
    equivalent mistake is forgetting it entirely."""

    def test_voiding_a_posted_invoice_reverses_its_entry(self, db):
        from app.services import sales_service

        _fully_configured(db)
        inv = _invoice(db)
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        entry.status = "posted"
        db.flush()

        sales_service._undo_invoice_entry(db, TENANT, inv, None)
        db.flush()
        reversal = db.query(JournalEntry).filter(
            JournalEntry.reversal_of_entry_id == entry.id).first()
        assert reversal is not None, "a posted entry was left standing"

    def test_voiding_a_draft_entry_marks_it_voided_rather_than_reversing(self, db):
        """Reversing a draft would create a correcting entry for something that
        never counted."""
        from app.services import sales_service

        _fully_configured(db)
        inv = _invoice(db)
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert entry.status == "draft", "fixture assumption broke"

        sales_service._undo_invoice_entry(db, TENANT, inv, None)
        db.flush()
        assert entry.status == "voided"
        assert db.query(JournalEntry).filter(
            JournalEntry.reversal_of_entry_id == entry.id).first() is None

    def test_an_invoice_with_no_entry_is_a_no_op(self, db):
        from app.services import sales_service

        _configure(db, ar=None, revenue=None)
        inv = _invoice(db)
        posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        assert inv.journal_entry_id is None
        sales_service._undo_invoice_entry(db, TENANT, inv, None)   # must not raise

    def test_another_tenants_entry_is_not_touched(self, db):
        from app.services import sales_service

        _fully_configured(db)
        inv = _invoice(db)
        entry = posting.post_invoice(db, company_id=TENANT, invoice=inv, user_id=None)
        entry.status = "posted"
        db.flush()

        sales_service._undo_invoice_entry(db, "some-other-tenant", inv, None)
        db.flush()
        assert entry.status == "posted", "a foreign tenant reversed our entry"


class TestTheChokepointIsWired:
    def test_post_invoice_to_ar_now_writes_the_ledger_too(self, db):
        """⚠️ THE WIRING IS THE DELIVERABLE. `post_invoice` existing and nothing
        calling it is the built-and-unreachable failure this arc has found five
        times. `post_invoice_to_ar` is the one chokepoint every issuance path
        funnels through, so this asserts the ledger moves when it is called —
        not merely that the function exists."""
        from app.services import sales_service

        _fully_configured(db)
        inv = _invoice(db, total="750.00")
        before = db.query(JournalEntry).filter(JournalEntry.tenant_id == TENANT).count()

        sales_service.post_invoice_to_ar(db, TENANT, inv)
        db.flush()

        after = db.query(JournalEntry).filter(JournalEntry.tenant_id == TENANT).count()
        assert after == before + 1, "the chokepoint moved AR and not the ledger"
        assert inv.journal_entry_id is not None

    def test_it_still_moves_the_customer_balance(self, db):
        """The subledger half must not regress — it is what AR aging and the
        financials board read."""
        from app.models.customer import Customer
        from app.services import sales_service

        _fully_configured(db)
        inv = _invoice(db, total="250.00")
        cust = db.query(Customer).filter(Customer.id == inv.customer_id).first()
        assert cust.current_balance == Decimal("0.00")

        sales_service.post_invoice_to_ar(db, TENANT, inv)
        assert cust.current_balance == Decimal("250.00")


class TestTheVoidWiringNotJustTheHelper:
    """⚠️ THE HELPER BEING RIGHT IS NOT THE DELIVERABLE. Removing the
    `_undo_invoice_entry(...)` CALL from `void_invoice` left every test in
    `TestVoidingReversesTheEntry` green, because they all invoke the helper
    directly. That is the built-and-unreachable shape one level down: correct
    code nothing calls. Verified by deleting the call and watching nothing go
    red — so this exercises the real void path end to end.

    `void_invoice` COMMITS, which is why this file's fixture is create-scoped.
    """

    def test_voiding_through_the_real_path_reverses_the_entry(self, db):
        from app.services import sales_service

        _fully_configured(db)
        inv = _invoice(db, total="400.00")
        sales_service.post_invoice_to_ar(db, TENANT, inv)
        db.flush()
        entry_id = inv.journal_entry_id
        assert entry_id, "fixture assumption broke — nothing posted"

        # Issued, unpaid: the two conditions `void_invoice` requires.
        inv.status = "sent"
        inv.amount_paid = Decimal("0.00")
        db.flush()

        # NULL actor, not a literal: `audit_logs.user_id` is FK'd to `users`
        # and `void_invoice` writes an audit row, so a made-up id raises a
        # ForeignKeyViolation from the audit write rather than testing the void.
        # Seeding a user would make this file depend on rows a bare database
        # does not have.
        sales_service.void_invoice(db, TENANT, None, inv.id)

        entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        assert entry is not None, "the entry vanished instead of being reversed"
        reversed_or_voided = (
            entry.status in ("voided", "reversed")
            or db.query(JournalEntry).filter(
                JournalEntry.reversal_of_entry_id == entry_id).first() is not None
        )
        assert reversed_or_voided, (
            "voiding the invoice left its journal entry standing — AR-2's "
            "`_undo_entry` bug, reproduced on the invoice side"
        )
