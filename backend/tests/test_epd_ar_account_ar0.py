"""AR-0 — the EPD AR-account resolver, CHARACTERIZATION.

Written BEFORE the fix, pinning what the code does today INCLUDING what is
wrong with it. Every wrongness is tagged. These pass against the pre-AR-0 code;
the ones that encode a defect are flipped in the same commit, with their prior
bodies quoted verbatim in the flipped test's docstring.

WHY THIS EXISTS. `_find_ar_account` matches `platform_category ILIKE '%ar%'` —
a substring match against a free-text column, `.first()`, no ORDER BY. Two
distinct failures come out of six lines:

  * it can return NOTHING when an AR account plainly exists, and
  * it can return the WRONG account, silently, when some unrelated category
    happens to contain the letters "a" and "r" in sequence.

PRODUCTION EVIDENCE (read-only check, 2026-08-05, sunnycrest, 224 active
mappings): the nine `platform_category` values in use are `other`, `expense`,
`current_liability`, `current_asset`, `fixed_asset`, `cogs`, `tax_expense`,
`other_income`, `equity`. **Not one contains "ar".** So the resolver returns
None 100% of the time on the real chart, and the caller's
`ar_account_id or gl_account_id` fallback is not an edge case — it is the only
path. Meanwhile `1200 ACCOUNTS RECEIVABLE-TRADE` sits right there, categorised
`current_asset`.

The resolver was never looking at the account. It was looking at a coarse
import-time classification and hoping.

Cleans up its own `ar0-` tenants (COMPANY-LITTER ratchet).
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
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.role import Role
from app.models.user import User
from app.services import early_payment_discount_service as epd
from app.services import journal_entry_service
from app.services.journal_entry_service import JournalLineSpec
from tests._cleanup import purge_companies_by_slug

_SLUG = "ar0-"


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    yield _Env(s)
    s.rollback()
    s.close()


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(
            id=str(uuid.uuid4()), name=f"AR0 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        role = Role(id=str(uuid.uuid4()), company_id=self.company.id,
                    name="Admin", slug="admin")
        s.add(role); s.flush()
        self.user = User(
            id=str(uuid.uuid4()), company_id=self.company.id, role_id=role.id,
            email=f"{_SLUG}{sfx}@test.local", hashed_password="x",
            first_name="A", last_name="R", is_active=True,
        )
        s.add(self.user); s.flush()
        self.co = self.company.id

    def mapping(self, *, name, number, category) -> TenantGLMapping:
        m = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=self.co, platform_category=category,
            account_number=number, account_name=name, is_active=True,
        )
        self.s.add(m); self.s.flush()
        return m

    def production_shaped_chart(self) -> dict:
        """The category vocabulary actually present on sunnycrest, with the
        accounts AR-0 cares about. NONE of these categories contains "ar"."""
        return {
            "ar": self.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200",
                               category="current_asset"),
            "cash": self.mapping(name="JANDHA LLC - CASH CHECKING", number="1030",
                                 category="current_asset"),
            "discount": self.mapping(name="DISCOUNTS ALLOWED-CASH", number="5410",
                                     category="cogs"),
        }

    def customer(self, *, balance="1000.00") -> Customer:
        c = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name="Hopkins FH",
            is_active=True, current_balance=Decimal(balance),
        )
        self.s.add(c); self.s.flush()
        return c

    def payment(self, customer, *, total="500.00") -> CustomerPayment:
        p = CustomerPayment(
            id=str(uuid.uuid4()), company_id=self.co, customer_id=customer.id,
            payment_date=datetime(2026, 7, 10, 12, tzinfo=timezone.utc),
            total_amount=Decimal(total), payment_method="check",
        )
        self.s.add(p); self.s.flush()
        return p

    def je_count(self) -> int:
        return self.s.query(JournalEntry).count()


def _lines(env, entry_id) -> list[JournalEntryLine]:
    return (
        env.s.query(JournalEntryLine)
        .filter(JournalEntryLine.journal_entry_id == entry_id)
        .order_by(JournalEntryLine.line_number)
        .all()
    )


# ── the resolver ────────────────────────────────────────────────────────────


class TestResolver:
    """DELIBERATE PIN FLIPS. The three characterizations this class replaces
    read, verbatim:

        def test_WRONGNESS_returns_none_on_the_real_production_chart(self, env):
            assert epd._find_ar_account(env.s, env.co) is None

        def test_WRONGNESS_returns_a_non_ar_account_whose_category_contains_ar(self, env):
            decoy = env.mapping(name="WARRANTY RESERVE", number="3300",
                                category="warranty_reserve")
            assert epd._find_ar_account(env.s, env.co) == decoy.id

        @pytest.mark.parametrize("category",
            ["warranty_reserve", "clearing", "salaries", "arrears", "market"])
        def test_WRONGNESS_every_one_of_these_categories_reads_as_ar(self, env, category):
            m = env.mapping(name=f"{category} account", number="9999", category=category)
            assert epd._find_ar_account(env.s, env.co) == m.id

    `_find_ar_account` no longer exists. `resolve_ar_account` reads an explicit
    configured id and validates it at use.
    """

    def test_the_configured_account_is_returned_with_its_denormalizable_fields(self, env):
        chart = env.production_shaped_chart()
        env.company.set_setting("accounting_gl", {"ar": chart["ar"].id})
        env.s.commit()

        got = epd.resolve_ar_account(env.s, env.co)
        assert got.id == chart["ar"].id
        assert got.account_number == "1200"
        assert got.account_name == "ACCOUNTS RECEIVABLE-TRADE"

    def test_the_substring_decoys_are_no_longer_reachable(self, env):
        """THE CLASS, KILLED. Every category that used to read as AR is now
        simply an unconfigured tenant — the resolver never looks at
        `platform_category` at all."""
        env.production_shaped_chart()
        for cat in ("warranty_reserve", "clearing", "salaries", "arrears", "market"):
            env.mapping(name=f"{cat} account", number=f"9{abs(hash(cat)) % 900 + 99}",
                        category=cat)
        env.s.commit()

        with pytest.raises(HTTPException) as ei:
            epd.resolve_ar_account(env.s, env.co)
        assert ei.value.status_code == 400
        assert "accounts-receivable" in str(ei.value.detail).lower()

    def test_unconfigured_refuses_with_the_configuration_action_named(self, env):
        env.production_shaped_chart()
        env.s.commit()
        with pytest.raises(HTTPException) as ei:
            epd.resolve_ar_account(env.s, env.co)
        assert "accounting GL settings" in str(ei.value.detail)

    def test_a_foreign_tenants_account_is_refused(self, env):
        """Routed through require_gl_account, so L-2.1b's existence-oracle
        discipline covers this boundary too."""
        other = Company(id=str(uuid.uuid4()), name="Other",
                        slug=f"{_SLUG}other-{uuid.uuid4().hex[:6]}",
                        is_active=True, vertical="manufacturing")
        env.s.add(other); env.s.flush()
        theirs = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=other.id, platform_category="current_asset",
            account_number="1200", account_name="THEIR AR", is_active=True)
        env.s.add(theirs); env.s.flush()
        env.company.set_setting("accounting_gl", {"ar": theirs.id})
        env.s.commit()

        with pytest.raises(HTTPException) as ei:
            epd.resolve_ar_account(env.s, env.co)
        assert "not in your chart of accounts" in str(ei.value.detail)
        assert "THEIR AR" not in str(ei.value.detail)


# ── the fallback ────────────────────────────────────────────────────────────


class TestFallback:
    """DELIBERATE PIN FLIPS. The two characterizations replaced here read:

        def test_WRONGNESS_unresolvable_ar_books_both_legs_to_the_discount_account(self, env):
            je_id = epd._create_discount_journal_entry(..., gl_account_id=chart["discount"].id, ...)
            assert je_id is not None
            lines = _lines(env, je_id)
            assert lines[0].gl_account_id == lines[1].gl_account_id == chart["discount"].id
            entry = ...
            assert entry.total_debits == entry.total_credits == Decimal("10.00")
            assert entry.status == "posted"

        def test_WRONGNESS_no_discount_account_applies_the_discount_anyway(self, env):
            je_id = epd._create_discount_journal_entry(..., gl_account_id=None, ...)
            assert je_id is None
            assert env.je_count() == before

    Both are refusals now. The second's "no entry created" half was always
    right; what was wrong was returning it as a value the caller ignored.
    """

    def test_unresolvable_ar_refuses_and_posts_nothing(self, env):
        chart = env.production_shaped_chart()
        cust = env.customer()
        pay = env.payment(cust)
        pay.discount_percentage = Decimal("2.0")
        env.s.commit()
        before = env.je_count()

        with pytest.raises(HTTPException) as ei:
            epd._create_discount_journal_entry(
                db=env.s, tenant_id=env.co, payment=pay, discount_amount=10.00,
                gl_account_id=chart["discount"].id, user_id=env.user.id,
            )
        assert ei.value.status_code == 400
        env.s.rollback()
        assert env.je_count() == before

    def test_no_discount_account_refuses_and_posts_nothing(self, env):
        env.production_shaped_chart()
        cust = env.customer()
        pay = env.payment(cust)
        env.s.commit()
        before = env.je_count()

        with pytest.raises(HTTPException) as ei:
            epd._create_discount_journal_entry(
                db=env.s, tenant_id=env.co, payment=pay, discount_amount=10.00,
                gl_account_id=None, user_id=env.user.id,
            )
        assert ei.value.status_code == 400
        env.s.rollback()
        assert env.je_count() == before

    def test_fully_configured_books_two_DIFFERENT_accounts(self, env):
        """HAND MATH — discount 10.00 on a 500.00 payment:

             debit  5410 DISCOUNTS ALLOWED-CASH   10.00
             credit 1200 ACCOUNTS RECEIVABLE-TRADE 10.00
             debits - credits = 0.00, and the two legs are NOT the same account
        """
        chart = env.production_shaped_chart()
        env.company.set_setting("accounting_gl", {"ar": chart["ar"].id})
        cust = env.customer()
        pay = env.payment(cust)
        pay.discount_percentage = Decimal("2.0")
        env.s.commit()

        je_id = epd._create_discount_journal_entry(
            db=env.s, tenant_id=env.co, payment=pay, discount_amount=10.00,
            gl_account_id=chart["discount"].id, user_id=env.user.id,
        )
        env.s.commit()

        lines = _lines(env, je_id)
        assert lines[0].gl_account_id == chart["discount"].id
        assert lines[0].debit_amount == Decimal("10.00")
        assert lines[1].gl_account_id == chart["ar"].id
        assert lines[1].credit_amount == Decimal("10.00")
        assert lines[1].gl_account_number == "1200"
        assert lines[0].gl_account_id != lines[1].gl_account_id


# ── the primitive ───────────────────────────────────────────────────────────


class TestPrimitive:
    """DELIBERATE PIN FLIPS (AR-0c). Replaced:

        def test_WRONGNESS_create_journal_entry_accepts_an_unbalanced_entry(self, env):
            entry = journal_entry_service.create_journal_entry(..., lines=[debit 100, credit 40])
            assert entry.total_debits == Decimal("100.00")
            assert entry.total_credits == Decimal("40.00")

        def test_WRONGNESS_create_journal_entry_accepts_both_legs_on_one_account(self, env):
            entry = journal_entry_service.create_journal_entry(..., lines=[ar debit 10, ar credit 10])
            assert lines[0].gl_account_id == lines[1].gl_account_id
    """

    def test_unbalanced_is_refused(self, env):
        chart = env.production_shaped_chart()
        env.s.commit()
        before = env.je_count()

        with pytest.raises(HTTPException) as ei:
            journal_entry_service.create_journal_entry(
                env.s, tenant_id=env.co, entry_number="CHAR-1", entry_type="manual",
                entry_date=date(2026, 7, 10), period_month=7, period_year=2026,
                description="unbalanced", status="draft",
                lines=[
                    JournalLineSpec(gl_account_id=chart["ar"].id, debit_amount=Decimal("100.00")),
                    JournalLineSpec(gl_account_id=chart["cash"].id, credit_amount=Decimal("40.00")),
                ],
            )
        assert "not balanced" in str(ei.value.detail)
        env.s.rollback()
        assert env.je_count() == before

    def test_both_legs_on_one_account_is_refused(self, env):
        chart = env.production_shaped_chart()
        env.s.commit()
        before = env.je_count()

        with pytest.raises(HTTPException) as ei:
            journal_entry_service.create_journal_entry(
                env.s, tenant_id=env.co, entry_number="CHAR-2", entry_type="manual",
                entry_date=date(2026, 7, 10), period_month=7, period_year=2026,
                description="same account both legs", status="draft",
                lines=[
                    JournalLineSpec(gl_account_id=chart["ar"].id, debit_amount=Decimal("10.00")),
                    JournalLineSpec(gl_account_id=chart["ar"].id, credit_amount=Decimal("10.00")),
                ],
            )
        assert "same GL account" in str(ei.value.detail)
        env.s.rollback()
        assert env.je_count() == before

    def test_a_balanced_two_account_entry_still_passes(self, env):
        """The guards reject the two bad shapes and nothing else."""
        chart = env.production_shaped_chart()
        env.s.commit()
        entry = journal_entry_service.create_journal_entry(
            env.s, tenant_id=env.co, entry_number="CHAR-3", entry_type="manual",
            entry_date=date(2026, 7, 10), period_month=7, period_year=2026,
            description="fine", status="draft",
            lines=[
                JournalLineSpec(gl_account_id=chart["ar"].id, debit_amount=Decimal("10.00")),
                JournalLineSpec(gl_account_id=chart["cash"].id, credit_amount=Decimal("10.00")),
            ],
        )
        env.s.commit()
        assert entry.total_debits == entry.total_credits == Decimal("10.00")


# ── found by the characterization, OUT of AR-0's scope ──────────────────────


class TestUnmappedDiscountColumns:
    """FOUND WHILE PINNING AR-0, NOT FIXED HERE.

    `apply_discounted_payment` writes SEVEN discount attributes onto the
    payment (`early_payment_discount_service.py:159-166`):
    `discount_applied`, `discount_amount`, `discount_percentage`,
    `discount_type`, `discount_override_by`, `discount_override_reason`, and
    later `discount_journal_entry_id`.

    **`CustomerPayment` declares none of them** (`models/customer_payment.py`
    has 14 mapped columns; not one is discount-related). Assigning an unmapped
    attribute on a SQLAlchemy instance is legal Python and silently non-
    persistent — it sets an instance attribute, the ORM ignores it, and the
    commit succeeds. So the whole discount record on the payment evaporates:
    which payments were discounted, by how much, under whose override, and
    which journal entry backed it.

    That is a separate defect from the AR resolver and it needs its own
    decision (add the columns via migration, or move the record elsewhere).
    Pinned so it cannot be lost again.
    """

    def test_WRONGNESS_customer_payment_has_no_discount_columns(self, env):
        from sqlalchemy import inspect as sa_inspect

        cols = {c.key for c in sa_inspect(CustomerPayment).mapper.column_attrs}
        for attr in (
            "discount_applied", "discount_amount", "discount_percentage",
            "discount_type", "discount_override_by", "discount_override_reason",
            "discount_journal_entry_id",
        ):
            assert attr not in cols, f"{attr} is mapped — this pin is stale, good"

    def test_WRONGNESS_assigning_them_does_not_persist(self, env):
        cust = env.customer()
        pay = env.payment(cust)
        env.s.commit()

        pay.discount_applied = True
        pay.discount_amount = Decimal("10.00")
        env.s.commit()          # succeeds — no error at any point

        # A SEPARATE session, deliberately: `expire_all()` + re-query returns
        # the SAME identity-mapped object, which still carries the in-memory
        # attribute. Only a fresh session reads what the database actually
        # holds, which is the whole question.
        other = SessionLocal()
        try:
            fresh = other.query(CustomerPayment).filter(
                CustomerPayment.id == pay.id).one()
            assert not hasattr(fresh, "discount_applied")
            assert not hasattr(fresh, "discount_amount")
        finally:
            other.close()
