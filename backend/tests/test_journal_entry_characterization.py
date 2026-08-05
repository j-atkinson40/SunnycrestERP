"""S-2 — CHARACTERIZATION of journal-entry creation, BEFORE extraction.

These tests pin what the code does across the two divergent JE-creation
paths (the `journal_entries` route + the inline JE in
`early_payment_discount_service`) so the upcoming `journal_entry_service`
extraction can be proven behavior-preserving. They characterize, they do
not judge — several still pin behavior that is almost certainly WRONG
(unbalanced drafts permitted, reversal + EPD bypassing the closed-period
guard, EPD's broad error-swallow). Per the S-2 discipline those are
PINNED + REPORTED, NOT fixed in the extraction commit.

The ONE exception, done deliberately as its own commit BEFORE the
extraction: the GL-denormalization tenant-scope leak. `create_entry` now
scopes the GL lookup by tenant_id AND raises 400 when unresolved — this
file pins that CORRECTED behavior (see TestCreateEntryGLLookup). Wrongness
still-pinned is tagged `# WRONGNESS:` so the later fix passes can find it.

Cleans up its own companies (COMPANY-LITTER ratchet, conftest.py).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.journal_entry import (
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
)
from app.models.period_lock import PeriodLock
from app.models.role import Role
from app.models.user import User
from app.services.agents.period_lock import PeriodLockedError

from app.api.routes.journal_entries import (
    JECreate,
    JELineCreate,
    create_entry,
    post_entry,
    reverse_entry,
)
from app.services.early_payment_discount_service import (
    _create_discount_journal_entry,
)


_CREATED_COMPANY_IDS: set[str] = set()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_companies():
    """Delete every company these tests created (+ dependent rows) at
    module teardown — the handlers COMMIT, so the function-scoped
    rollback doesn't reach them. Ratchet compliance."""
    yield
    if not _CREATED_COMPANY_IDS:
        return
    ids = list(_CREATED_COMPANY_IDS)
    s = SessionLocal()
    try:
        # (model, scope-column) in FK-safe order — children before parents.
        for model, col in (
            (JournalEntryLine, "tenant_id"),
            (JournalEntry, "tenant_id"),
            (AccountingPeriod, "tenant_id"),
            (PeriodLock, "tenant_id"),
            (TenantGLMapping, "tenant_id"),
            (CustomerPayment, "company_id"),
            (Customer, "company_id"),
            (User, "company_id"),
            (Role, "company_id"),
        ):
            s.query(model).filter(
                getattr(model, col).in_(ids)
            ).delete(synchronize_session=False)
        s.query(Company).filter(Company.id.in_(ids)).delete(
            synchronize_session=False
        )
        s.commit()
    finally:
        s.close()


def _mk_company(db) -> str:
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"JES2-{suffix}",
        slug=f"jes2-{suffix}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    _CREATED_COMPANY_IDS.add(co.id)
    return co.id


def _mk_user(db, co_id) -> User:
    role = Role(id=str(uuid.uuid4()), company_id=co_id, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(
        id=str(uuid.uuid4()),
        company_id=co_id,
        role_id=role.id,
        email=f"jes2-{uuid.uuid4().hex[:6]}@test.local",
        hashed_password="x",
        first_name="J",
        last_name="E",
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def _mk_gl(db, co_id, *, num, name, cat="general") -> str:
    """Seed a real GL mapping for this tenant. Post-fix, create_entry
    REQUIRES every line's gl_account_id to resolve to one of the caller's
    own tenant's mappings — so tests must provide real ones."""
    gl = TenantGLMapping(
        id=str(uuid.uuid4()), tenant_id=co_id,
        platform_category=cat, account_number=num, account_name=name,
    )
    db.add(gl)
    db.commit()
    return gl.id


def _line(gl_id, *, debit=0.0, credit=0.0, num=None, name=None):
    return JELineCreate(
        gl_account_id=gl_id,
        gl_account_number=num,
        gl_account_name=name,
        description="test line",
        debit_amount=debit,
        credit_amount=credit,
    )


def _co_user_gls(db):
    """Common setup: a tenant, an admin, and two of its own GL accounts."""
    co = _mk_company(db)
    user = _mk_user(db, co)
    gl_d = _mk_gl(db, co, num="1000", name="Cash")
    gl_c = _mk_gl(db, co, num="4000", name="Revenue")
    return co, user, gl_d, gl_c


# ── create_entry ─────────────────────────────────────────────────────


class TestCreateEntry:
    def test_first_entry_number_status_draft_and_period_from_entry_date(
        self, db
    ):
        co, user, gl_d, gl_c = _co_user_gls(db)
        # entry_date in JANUARY — pins that period is derived from the
        # entry_date, NOT from "today".
        body = JECreate(
            entry_type="manual",
            entry_date="2026-01-15",
            description="pin: first entry",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        out = create_entry(body=body, current_user=user, db=db)
        assert out["entry_number"] == "JE-1001"  # count(0) + 1001
        assert out["status"] == "draft"          # default, not posted
        row = db.get(JournalEntry, out["id"])
        assert row.period_month == 1 and row.period_year == 2026
        assert row.total_debits == Decimal("100")
        assert row.total_credits == Decimal("100")

    def test_permits_unbalanced_draft(self, db):
        # WRONGNESS: create_entry never checks debits == credits; an
        # unbalanced entry is freely created as a draft. Balance is only
        # enforced at POST time.
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual",
            entry_date="2026-03-10",
            description="pin: unbalanced draft allowed",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=40)],
        )
        out = create_entry(body=body, current_user=user, db=db)  # no raise
        row = db.get(JournalEntry, out["id"])
        assert row.status == "draft"
        assert row.total_debits == Decimal("100")
        assert row.total_credits == Decimal("40")  # persisted unbalanced

    def test_permits_fewer_than_two_lines(self, db):
        # WRONGNESS: a single-line (or zero-line) draft is creatable; the
        # >=2-lines rule lives only in post_entry.
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual",
            entry_date="2026-03-10",
            description="pin: one line allowed",
            lines=[_line(gl_d, debit=50)],
        )
        out = create_entry(body=body, current_user=user, db=db)  # no raise
        lines = (
            db.query(JournalEntryLine)
            .filter(JournalEntryLine.journal_entry_id == out["id"])
            .all()
        )
        assert len(lines) == 1


class TestCreateEntryGLLookup:
    """The GL-scope FIX (its own commit, ahead of the extraction). The
    lookup is scoped by tenant_id and REQUIRES a match — no silent
    cross-tenant denorm, no silent-null fallback."""

    def test_same_tenant_gl_denormalizes_from_the_mapping(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        # body supplies its own number/name, but the tenant's mapping wins.
        body = JECreate(
            entry_type="manual", entry_date="2026-03-10", description="pin",
            lines=[
                _line(gl_d, debit=10, num="IGNORED", name="Ignored"),
                _line(gl_c, credit=10),
            ],
        )
        out = create_entry(body=body, current_user=user, db=db)
        line = (
            db.query(JournalEntryLine)
            .filter(
                JournalEntryLine.journal_entry_id == out["id"],
                JournalEntryLine.gl_account_id == gl_d,
            )
            .first()
        )
        assert line.gl_account_number == "1000"   # from the mapping
        assert line.gl_account_name == "Cash"     # not the body's "Ignored"

    def test_foreign_tenant_gl_id_is_rejected_not_leaked(self, db):
        # FIXED (was the cross-tenant leak): referencing another tenant's
        # GL id is a 400, not a denorm of their account_number/name.
        #
        # PIN FLIPPED L-2.2 X-1 — MESSAGE ONLY, the 400 is unchanged.
        #   prior:  assert "Unknown GL account" in str(ei.value.detail)
        #           (the route's own string, f"Unknown GL account '{id}' for
        #           this tenant" — it echoed the id the caller had supplied)
        #   now:    the shared `reconciliation_gl.require_gl_account` message.
        # The echo was never a leak (the caller supplied the id), so this is a
        # consistency change, not a security one: one check now means one
        # message, and foreign vs nonexistent stay byte-identical either way.
        other_co = _mk_company(db)
        foreign_gl = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=other_co,
            platform_category="revenue", account_number="9999",
            account_name="Foreign Tenant Account",
        )
        db.add(foreign_gl)
        db.commit()

        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual", entry_date="2026-03-10", description="pin",
            lines=[_line(foreign_gl.id, debit=10), _line(gl_c, credit=10)],
        )
        with pytest.raises(HTTPException) as ei:
            create_entry(body=body, current_user=user, db=db)
        assert ei.value.status_code == 400
        assert "not in your chart of accounts" in str(ei.value.detail)
        # Still no leak of the other tenant's data.
        assert "9999" not in str(ei.value.detail)
        assert "Foreign Tenant Account" not in str(ei.value.detail)

    def test_unknown_gl_id_is_rejected_not_silent_null(self, db):
        # FIXED (was the silent-null fallback): an id that resolves to
        # nothing is a 400, not a line with null account_number/name.
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual", entry_date="2026-03-10", description="pin",
            lines=[_line("does-not-exist", debit=10), _line(gl_c, credit=10)],
        )
        with pytest.raises(HTTPException) as ei:
            create_entry(body=body, current_user=user, db=db)
        assert ei.value.status_code == 400


# ── post_entry ───────────────────────────────────────────────────────


class TestPostEntry:
    def _draft(self, db, user, gl_d, gl_c, *, lines=None, entry_date="2026-05-12"):
        body = JECreate(
            entry_type="manual",
            entry_date=entry_date,
            description="pin",
            lines=lines,
        )
        return create_entry(body=body, current_user=user, db=db)["id"]

    def test_balanced_two_line_open_period_posts(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        eid = self._draft(
            db, user, gl_d, gl_c,
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        out = post_entry(entry_id=eid, current_user=user, db=db)
        assert out["status"] == "posted"
        assert db.get(JournalEntry, eid).status == "posted"

    def test_unbalanced_rejected_at_post(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        eid = self._draft(
            db, user, gl_d, gl_c,
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=40)],
        )
        with pytest.raises(HTTPException) as ei:
            post_entry(entry_id=eid, current_user=user, db=db)
        assert ei.value.status_code == 400
        assert "not balanced" in str(ei.value.detail)

    def test_fewer_than_two_lines_rejected_at_post(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        # balanced (0 == 0) but only one line.
        eid = self._draft(db, user, gl_d, gl_c, lines=[_line(gl_d, debit=0, credit=0)])
        with pytest.raises(HTTPException) as ei:
            post_entry(entry_id=eid, current_user=user, db=db)
        assert ei.value.status_code == 400
        assert "2 lines" in str(ei.value.detail)

    def test_closed_period_blocks_post(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        eid = self._draft(
            db, user, gl_d, gl_c,
            entry_date="2026-05-12",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        db.add(AccountingPeriod(
            id=str(uuid.uuid4()), tenant_id=co,
            period_month=5, period_year=2026, status="closed",
        ))
        db.commit()
        with pytest.raises(HTTPException) as ei:
            post_entry(entry_id=eid, current_user=user, db=db)
        assert ei.value.status_code == 400
        assert "closed" in str(ei.value.detail)


# ── reverse_entry ────────────────────────────────────────────────────


class TestReverseEntry:
    def _posted(self, db, user, co, gl_d, gl_c, *, entry_date="2026-02-12"):
        body = JECreate(
            entry_type="manual", entry_date=entry_date, description="orig",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        eid = create_entry(body=body, current_user=user, db=db)["id"]
        post_entry(entry_id=eid, current_user=user, db=db)
        return eid

    def test_only_posted_entries_reversible(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual", entry_date="2026-02-12", description="draft",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        eid = create_entry(body=body, current_user=user, db=db)["id"]  # draft
        with pytest.raises(HTTPException) as ei:
            reverse_entry(entry_id=eid, current_user=user, db=db)
        assert ei.value.status_code == 400

    def test_reversal_posts_directly_mirrors_lines_period_from_today(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        eid = self._posted(db, user, co, gl_d, gl_c)
        out = reverse_entry(entry_id=eid, current_user=user, db=db)
        rev = db.get(JournalEntry, out["id"])
        today = date.today()
        assert rev.status == "posted"          # posted directly, no draft
        assert rev.is_reversal is True
        assert rev.entry_type == "reversal"
        assert rev.reversal_of_entry_id == eid
        # period from TODAY, not the original entry's period (Feb).
        assert rev.period_month == today.month and rev.period_year == today.year
        # totals swapped; lines mirrored (debit<->credit).
        assert rev.total_debits == Decimal("100")
        assert rev.total_credits == Decimal("100")
        rl = (
            db.query(JournalEntryLine)
            .filter(JournalEntryLine.journal_entry_id == rev.id)
            .order_by(JournalEntryLine.line_number)
            .all()
        )
        assert rl[0].credit_amount == Decimal("100") and rl[0].debit_amount == Decimal("0")
        assert db.get(JournalEntry, eid).status == "reversed"

    def test_reversal_bypasses_ACCOUNTING_PERIOD_guard(self, db):
        # WRONGNESS (AccountingPeriod only): reverse_entry writes
        # status="posted" straight into TODAY's period without checking
        # AccountingPeriod — unlike post_entry. Reversing works even when
        # today's AccountingPeriod is closed. NOTE post-S-3: reverse now
        # DOES honor PeriodLock (via the shared primitive), so this is
        # specifically the AccountingPeriod-on-reverse gap; reconciling the
        # two closed-period tables is the S-6 item.
        co, user, gl_d, gl_c = _co_user_gls(db)
        # original in an OPEN past period so it can be posted first.
        eid = self._posted(db, user, co, gl_d, gl_c, entry_date="2026-02-12")
        today = date.today()
        db.add(AccountingPeriod(
            id=str(uuid.uuid4()), tenant_id=co,
            period_month=today.month, period_year=today.year, status="closed",
        ))
        db.commit()
        out = reverse_entry(entry_id=eid, current_user=user, db=db)  # no raise
        assert db.get(JournalEntry, out["id"]).status == "posted"


# ── EPD inline JE ────────────────────────────────────────────────────


class TestEpdDiscountJournalEntry:
    def _payment(self, db, co) -> CustomerPayment:
        cust = Customer(
            id=str(uuid.uuid4()), company_id=co, name="Discount Customer",
        )
        db.add(cust)
        db.flush()
        pay = CustomerPayment(
            id=str(uuid.uuid4()), company_id=co, customer_id=cust.id,
            payment_date=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
            total_amount=Decimal("500"),
        )
        db.add(pay)
        db.commit()
        # discount_percentage is NOT a column — the EPD function reads it
        # off the instance; set it so the f-string doesn't AttributeError
        # into the broad except (see the swallow note below).
        pay.discount_percentage = 2
        return pay

    def test_number_status_period_and_balance(self, db):
        co = _mk_company(db)
        user = _mk_user(db, co)
        gl = _mk_gl(db, co, num="4100", name="Sales Discounts", cat="discount")
        pay = self._payment(db, co)
        entry_id = _create_discount_journal_entry(
            db, tenant_id=co, payment=pay, discount_amount=10.0,
            gl_account_id=gl, user_id=user.id,
        )
        db.commit()
        assert entry_id is not None
        row = db.get(JournalEntry, entry_id)
        assert row.entry_number == f"DISC-{pay.id[:8]}"  # NOT the JE-#### scheme
        assert row.status == "posted"                    # auto-posted
        assert row.entry_type == "adjusting"
        assert row.period_month == 4 and row.period_year == 2026  # from payment_date
        assert row.total_debits == Decimal("10") == row.total_credits

    def test_returns_none_when_no_gl_account(self, db):
        # Pins the explicit None-GL contract (early return + warning log).
        co = _mk_company(db)
        user = _mk_user(db, co)
        pay = self._payment(db, co)
        before = db.query(JournalEntry).filter(JournalEntry.tenant_id == co).count()
        entry_id = _create_discount_journal_entry(
            db, tenant_id=co, payment=pay, discount_amount=10.0,
            gl_account_id=None, user_id=user.id,
        )
        assert entry_id is None
        after = db.query(JournalEntry).filter(JournalEntry.tenant_id == co).count()
        assert after == before  # no entry created


# ── S-3 period-lock guard ────────────────────────────────────────────


def _lock(db, co, start: date, end: date) -> PeriodLock:
    pl = PeriodLock(
        id=str(uuid.uuid4()), tenant_id=co,
        period_start=start, period_end=end, is_active=True,
    )
    db.add(pl)
    db.commit()
    return pl


class TestPeriodLockGuard:
    """S-3 — PeriodLock (the authoritative closed-period source) guards JE
    creation in the shared primitive AND posting in post_entry. Pins that
    the two 'bypass' paths (reversal, EPD) pass because of WHERE their
    entry_date lands, not by luck — 'passes trivially' is a claim, and
    claims in this arc get tests."""

    def test_manual_create_into_locked_period_is_409(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        _lock(db, co, date(2026, 3, 1), date(2026, 3, 31))
        body = JECreate(
            entry_type="manual", entry_date="2026-03-10", description="pin",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        with pytest.raises(PeriodLockedError) as ei:
            create_entry(body=body, current_user=user, db=db)
        assert ei.value.status_code == 409  # PeriodLockedError is a 409

    def test_create_into_open_period_ok_despite_lock_elsewhere(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        _lock(db, co, date(2026, 5, 1), date(2026, 5, 31))  # May locked
        body = JECreate(
            entry_type="manual", entry_date="2026-04-30", description="pin",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        out = create_entry(body=body, current_user=user, db=db)  # Apr 30 open
        assert db.get(JournalEntry, out["id"]).status == "draft"

    def test_reversal_out_of_a_locked_period_succeeds(self, db):
        # The claim under test: reversal carries TODAY's entry_date, so it
        # escapes a lock on the ORIGINAL entry's (past) period. Reverse an
        # entry whose own period is locked -> succeeds because the reversal
        # posts today (open).
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual", entry_date="2026-02-12", description="orig",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        eid = create_entry(body=body, current_user=user, db=db)["id"]
        post_entry(entry_id=eid, current_user=user, db=db)  # Feb still open
        _lock(db, co, date(2026, 2, 1), date(2026, 2, 28))  # NOW lock Feb
        out = reverse_entry(entry_id=eid, current_user=user, db=db)  # no raise
        assert db.get(JournalEntry, out["id"]).status == "posted"
        assert db.get(JournalEntry, eid).status == "reversed"

    def test_epd_discount_on_unlocked_payment_date_succeeds(self, db):
        # EPD carries payment_date; a lock on a DIFFERENT period doesn't
        # block it. (In the live flow the payment itself can't exist in a
        # locked period — create_customer_payment guards payment_date — so
        # the discount JE's date is protected upstream.)
        co = _mk_company(db)
        user = _mk_user(db, co)
        gl = _mk_gl(db, co, num="4100", name="Sales Discounts", cat="discount")
        _lock(db, co, date(2026, 5, 1), date(2026, 5, 31))  # May locked
        pay = TestEpdDiscountJournalEntry()._payment(db, co)  # payment_date Apr 20
        entry_id = _create_discount_journal_entry(
            db, tenant_id=co, payment=pay, discount_amount=10.0,
            gl_account_id=gl, user_id=user.id,
        )
        db.commit()
        assert entry_id is not None
        assert db.get(JournalEntry, entry_id).period_month == 4

    def test_epd_on_locked_payment_date_RAISES_not_swallowed(self, db):
        # The hole closed before S-4: the primitive's period-lock guard must
        # PROPAGATE through EPD's broad `except`, not be swallowed to None.
        # Reachable TODAY — apply_discounted_payment runs on an EXISTING
        # payment (separate /discount action), so the period can lock between
        # payment creation and discount application. Swallowing would leave
        # AR reduced with no contra-revenue entry (books out of balance).
        co = _mk_company(db)
        user = _mk_user(db, co)
        gl = _mk_gl(db, co, num="4100", name="Sales Discounts", cat="discount")
        pay = TestEpdDiscountJournalEntry()._payment(db, co)  # payment_date 2026-04-20
        _lock(db, co, date(2026, 4, 1), date(2026, 4, 30))    # April locked
        with pytest.raises(PeriodLockedError):
            _create_discount_journal_entry(
                db, tenant_id=co, payment=pay, discount_amount=10.0,
                gl_account_id=gl, user_id=user.id,
            )

    def test_post_into_locked_period_is_409_via_periodlock(self, db):
        # post_entry's NEW PeriodLock check (alongside the AccountingPeriod
        # one). Create while open, lock, then post -> 409.
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual", entry_date="2026-06-15", description="pin",
            lines=[_line(gl_d, debit=100), _line(gl_c, credit=100)],
        )
        eid = create_entry(body=body, current_user=user, db=db)["id"]  # open
        _lock(db, co, date(2026, 6, 1), date(2026, 6, 30))
        with pytest.raises(PeriodLockedError) as ei:
            post_entry(entry_id=eid, current_user=user, db=db)
        assert ei.value.status_code == 409


# ── L-2.2 X-1: create_entry's lookup vs. validate_gl_account ─────────
#
# CHARACTERIZATION FIRST. `create_entry` filtered on tenant_id but NOT
# is_active, so it accepted a soft-deleted mapping that
# `reconciliation_gl.validate_gl_account` — the single definition of a usable
# GL account everywhere else — refuses. Two definitions of "usable", differing
# by one predicate, is the drift L-2.1b closed on the reconciliation routes.


def _mk_inactive_gl(db, co_id, *, num, name) -> str:
    gl = TenantGLMapping(
        id=str(uuid.uuid4()), tenant_id=co_id, platform_category="general",
        account_number=num, account_name=name, is_active=False,
    )
    db.add(gl)
    db.commit()
    return gl.id


class TestCreateEntryRejectsInactiveGL:
    """X-1. Own tenant, but deactivated.

    PRIOR BEHAVIOUR, pinned before the change and now flipped: an inactive
    same-tenant mapping was ACCEPTED and its account_number/name denormalized
    onto the line, because the lookup filtered `tenant_id` only. Meanwhile
    `validate_gl_account` refused the same id, so the reconciliation posting
    path and the manual JE path disagreed about whether that account existed.

    STOP-CHECK EVIDENCE for the flip (read-only, 2026-08-04): production has
    **0 journal_entry_lines, 0 journal_entries, and 0 inactive mappings** out
    of 224 — so no existing entry references an inactive mapping and nothing
    previously writable becomes unwritable.
    """

    def test_inactive_same_tenant_gl_is_rejected(self, db):
        co, user, gl_d, gl_c = _co_user_gls(db)
        dead = _mk_inactive_gl(db, co, num="1099", name="Closed Cash")
        body = JECreate(
            entry_type="manual", entry_date="2026-03-10", description="pin",
            lines=[_line(dead, debit=10), _line(gl_c, credit=10)],
        )
        with pytest.raises(HTTPException) as ei:
            create_entry(body=body, current_user=user, db=db)
        assert ei.value.status_code == 400
        # Named, unlike foreign/nonexistent: it is the operator's own data and
        # the fix (reactivate, or pick another) is theirs to make.
        assert "inactive" in str(ei.value.detail).lower()

    def test_active_same_tenant_gl_still_accepted(self, db):
        """The other direction — tightening must not reject valid accounts."""
        co, user, gl_d, gl_c = _co_user_gls(db)
        body = JECreate(
            entry_type="manual", entry_date="2026-03-10", description="pin",
            lines=[_line(gl_d, debit=10), _line(gl_c, credit=10)],
        )
        out = create_entry(body=body, current_user=user, db=db)
        line = (
            db.query(JournalEntryLine)
            .filter(JournalEntryLine.journal_entry_id == out["id"],
                    JournalEntryLine.gl_account_id == gl_d)
            .first()
        )
        assert line.gl_account_number == "1000"

    def test_foreign_and_nonexistent_read_identically(self, db):
        """The L-2.1b existence-oracle discipline, now enforced on this route
        too: naming the foreign case as foreign would confirm that a row exists
        in another tenant."""
        other_co = _mk_company(db)
        foreign = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=other_co, platform_category="revenue",
            account_number="9999", account_name="Foreign Tenant Account",
        )
        db.add(foreign)
        db.commit()
        co, user, gl_d, gl_c = _co_user_gls(db)

        details = []
        for bad in (foreign.id, "does-not-exist"):
            body = JECreate(
                entry_type="manual", entry_date="2026-03-10", description="pin",
                lines=[_line(bad, debit=10), _line(gl_c, credit=10)],
            )
            with pytest.raises(HTTPException) as ei:
                create_entry(body=body, current_user=user, db=db)
            details.append(str(ei.value.detail))
        assert details[0] == details[1]


# ── L-2.2 X-2: parse_entry returns an UNVALIDATED gl_account_id ──────
#
# CHARACTERIZATION FIRST, and the characterization is the finding.
#
# The prompt (`accounting.parse_journal_entry`, v1 active on production,
# read-only-verified 2026-08-04) renders its chart as
#     - {account_number}: {account_name} ({category})
# and then asks the model to return `gl_account_id`. THE MODEL IS NEVER SHOWN AN
# id. It is being asked for a value it has no way to know, so the id it returns
# is always fabricated — an echoed account number, an invented UUID, or empty.
# The frontend then reads ONLY `gl_account_id` and discards `gl_account_number`,
# which is the field the model CAN get right because it is in the prompt.
#
# So account selection in the AI parse has never worked. Pre-L-2.1d the native
# <select> rendered the fabricated id as blank and submitted it anyway; the
# operator learned about it from create_entry's 400 at save.


class _FakeResult:
    def __init__(self, parsed):
        self.status = "success"
        self.response_parsed = parsed
        self.error_message = None


def _patch_intelligence(monkeypatch, parsed):
    from app.services.intelligence import intelligence_service

    monkeypatch.setattr(
        intelligence_service, "execute",
        lambda *a, **k: _FakeResult(parsed),
    )


class TestParseEntryResolvesGLAccounts:
    """X-2. Whatever the model proposes is resolved against the tenant's own
    chart before it leaves the endpoint."""

    def _parse(self, db, user, text="anything"):
        from app.api.routes.journal_entries import ParseRequest, parse_entry
        return parse_entry(body=ParseRequest(input=text), current_user=user, db=db)

    def test_a_fabricated_id_does_not_reach_the_caller(self, db, monkeypatch):
        """THE BUG. Pre-L-2.2 this id was returned verbatim and the form put it
        in state, where it sat invisibly until create_entry rejected it."""
        co, user, gl_d, gl_c = _co_user_gls(db)
        _patch_intelligence(monkeypatch, {
            "description": "pin", "entry_type": "manual", "confidence": 0.9,
            "lines": [{
                "gl_account_id": "gl-1000-fabricated",
                "gl_account_number": "1000", "gl_account_name": "Cash",
                "side": "debit", "amount": 10, "description": None,
            }],
        })
        out = self._parse(db, user)
        assert out["lines"][0]["gl_account_id"] != "gl-1000-fabricated"

    def test_the_account_NUMBER_is_what_resolves(self, db, monkeypatch):
        """The fix that makes the feature work at all: the model cannot know
        ids, but it CAN read account numbers off the prompt, so the number is
        the identifier to resolve by."""
        co, user, gl_d, gl_c = _co_user_gls(db)
        _patch_intelligence(monkeypatch, {
            "description": "pin", "entry_type": "manual", "confidence": 0.9,
            "lines": [{
                "gl_account_id": "definitely-not-a-real-id",
                "gl_account_number": "1000", "gl_account_name": "Cash",
                "side": "debit", "amount": 10, "description": None,
            }],
        })
        line = self._parse(db, user)["lines"][0]
        assert line["gl_account_id"] == gl_d          # the real mapping
        assert line["gl_account_name"] == "Cash"      # denormalized from IT
        assert line.get("gl_account_unresolved") is None

    def test_a_valid_id_is_honoured_and_re_denormalized(self, db, monkeypatch):
        """If a real id ever does arrive, it wins — and number/name come from
        the mapping, not from whatever the model asserted about it."""
        co, user, gl_d, gl_c = _co_user_gls(db)
        _patch_intelligence(monkeypatch, {
            "description": "pin", "entry_type": "manual", "confidence": 0.9,
            "lines": [{
                "gl_account_id": gl_d,
                "gl_account_number": "WRONG", "gl_account_name": "Wrong",
                "side": "debit", "amount": 10, "description": None,
            }],
        })
        line = self._parse(db, user)["lines"][0]
        assert line["gl_account_id"] == gl_d
        assert line["gl_account_number"] == "1000"
        assert line["gl_account_name"] == "Cash"

    def test_an_unresolvable_account_is_FLAGGED_not_dropped_silently(self, db, monkeypatch):
        """The chosen shape. A proposal the chart cannot match becomes a null id
        PLUS what the model proposed, so the UI can say a suggestion was made and
        rejected. Dropping it silently would discard information the model
        produced and leave the operator with an empty picker and no reason."""
        co, user, gl_d, gl_c = _co_user_gls(db)
        _patch_intelligence(monkeypatch, {
            "description": "pin", "entry_type": "manual", "confidence": 0.9,
            "lines": [{
                "gl_account_id": "nope",
                "gl_account_number": "8888", "gl_account_name": "Imagined Account",
                "side": "debit", "amount": 10, "description": None,
            }],
        })
        line = self._parse(db, user)["lines"][0]
        assert line["gl_account_id"] is None
        assert line["gl_account_unresolved"] == {
            "proposed_number": "8888", "proposed_name": "Imagined Account",
        }
        # The rest of the line survives — the amount and side were never in doubt.
        assert line["amount"] == 10
        assert line["side"] == "debit"

    def test_an_inactive_account_does_not_resolve(self, db, monkeypatch):
        """Same definition of usable as everywhere else — the prompt is built
        from ACTIVE mappings, so a number that only matches a dead one is a
        proposal the chart cannot honour."""
        co, user, gl_d, gl_c = _co_user_gls(db)
        _mk_inactive_gl(db, co, num="1099", name="Closed Cash")
        _patch_intelligence(monkeypatch, {
            "description": "pin", "entry_type": "manual", "confidence": 0.9,
            "lines": [{
                "gl_account_id": None,
                "gl_account_number": "1099", "gl_account_name": "Closed Cash",
                "side": "debit", "amount": 10, "description": None,
            }],
        })
        line = self._parse(db, user)["lines"][0]
        assert line["gl_account_id"] is None
        assert line["gl_account_unresolved"]["proposed_number"] == "1099"

    def test_another_tenants_account_number_does_not_resolve(self, db, monkeypatch):
        """A guard on the NEW number resolution, not a claim about an old leak
        — the model never saw the other tenant's chart, so nothing was read
        across tenants before. But account numbers are not globally unique, so
        resolving by number without a tenant filter WOULD create the read. This
        pins that it stays scoped."""
        other_co = _mk_company(db)
        db.add(TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=other_co, platform_category="revenue",
            account_number="7777", account_name="Their Account",
        ))
        db.commit()
        co, user, gl_d, gl_c = _co_user_gls(db)
        _patch_intelligence(monkeypatch, {
            "description": "pin", "entry_type": "manual", "confidence": 0.9,
            "lines": [{
                "gl_account_id": None, "gl_account_number": "7777",
                "gl_account_name": "Their Account",
                "side": "debit", "amount": 10, "description": None,
            }],
        })
        line = self._parse(db, user)["lines"][0]
        assert line["gl_account_id"] is None
        assert "Their Account" not in str(line.get("gl_account_name") or "")

    def test_the_error_shape_is_untouched(self, db, monkeypatch):
        """A failed parse still returns the same {error, confidence, lines}
        envelope — resolution must not change what failure looks like."""
        from app.services.intelligence import intelligence_service

        class _Failed:
            status = "errored"
            response_parsed = None
            error_message = "boom"

        co, user, gl_d, gl_c = _co_user_gls(db)
        monkeypatch.setattr(intelligence_service, "execute", lambda *a, **k: _Failed())
        out = self._parse(db, user)
        assert out["lines"] == []
        assert out["confidence"] == 0
        assert out["error"] == "boom"
