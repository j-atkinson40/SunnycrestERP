"""AR-2.0 E-2 — the accounting-GL authoring surface.

AR-0 shipped `resolve_ar_account` and its fail-closed refusal with NO endpoint
and no UI, so a tenant hitting "No accounts-receivable GL account is configured"
could not clear it without writing settings directly. That is the same gap
L-2.1e closed for the keyword map, one domain over, and this closes it.

A SIBLING endpoint to `/keyword-gl`, not an extension. `/keyword-gl` validates
against `KEYWORD_CLASSIFICATIONS`, a code-fixed three-value set;
`accounting_gl` keys are PURPOSES, open-ended and growing one per arc. One PUT
serving both would branch on which vocabulary applied — two functions wearing
one name, the thing `decide` vs `decide_coded` avoided. The page is shared; the
server's job is not.

THE THREE STATES ARE THE CONTRACT (L-2.1c) and the check order is load-bearing:
`null` is falsy, so presence must be tested BEFORE truthiness or a deliberate
unmapping reads as a gap nobody has closed.

Cleans up its own `age2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.reconciliation import (
    AccountingGLUpdate,
    get_accounting_gl,
    set_accounting_gl,
)
from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services.early_payment_discount_service import (
    ACCOUNTING_GL_SETTINGS_KEY,
    resolve_ar_account,
)
from tests._cleanup import purge_companies_by_slug

_SLUG = "age2-"


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
            id=str(uuid.uuid4()), name=f"AGE2 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        role = Role(id=str(uuid.uuid4()), company_id=self.co, name="Admin", slug="admin")
        s.add(role); s.flush()
        self.user = User(
            id=str(uuid.uuid4()), company_id=self.co, role_id=role.id,
            email=f"{_SLUG}{sfx}@test.local", hashed_password="x",
            first_name="A", last_name="G", is_active=True,
        )
        s.add(self.user); s.flush()
        self.ar = self.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        s.commit()

    def mapping(self, *, name, number, active=True, tenant_id=None) -> TenantGLMapping:
        m = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=tenant_id or self.co,
            platform_category="current_asset", account_number=number,
            account_name=name, is_active=active,
        )
        self.s.add(m); self.s.flush()
        return m

    def get(self) -> dict:
        return get_accounting_gl(current_user=self.user, db=self.s)

    def put(self, purpose, gl_account_id):
        return set_accounting_gl(
            body=AccountingGLUpdate(purpose=purpose, gl_account_id=gl_account_id),
            current_user=self.user, db=self.s,
        )

    def row(self, payload, purpose="ar") -> dict:
        return next(r for r in payload["purposes"] if r["purpose"] == purpose)


class TestTheThreeStates:
    def test_absent_reads_as_unmapped(self, env):
        """Nobody has decided. Distinct from having decided not to."""
        assert env.row(env.get())["state"] == "unmapped"

    def test_a_set_account_reads_as_mapped_and_denormalizes(self, env):
        env.put("ar", env.ar.id)
        row = env.row(env.get())
        assert row["state"] == "mapped"
        assert row["gl_account_id"] == env.ar.id
        assert row["account_number"] == "1200"
        assert row["account_name"] == "ACCOUNTS RECEIVABLE-TRADE"

    def test_present_and_null_reads_as_INTENTIONAL_not_unmapped(self, env):
        """THE STATE THE CHECK ORDER EXISTS FOR. `null` is falsy, so a
        truthiness test first would report a deliberate decision as a gap."""
        env.put("ar", None)
        row = env.row(env.get())
        assert row["state"] == "intentional"
        assert row["gl_account_id"] is None
        # The KEY IS PRESENT — assignment, never `pop`.
        stored = (
            env.s.query(Company).filter(Company.id == env.co).one()
            .settings[ACCOUNTING_GL_SETTINGS_KEY]
        )
        assert "ar" in stored and stored["ar"] is None

    def test_an_inactive_account_reads_as_dangling(self, env):
        env.put("ar", env.ar.id)
        env.ar.is_active = False
        env.s.commit()
        row = env.row(env.get())
        assert row["state"] == "dangling"
        assert row["gl_account_id"] is None      # not surfaced as usable

    def test_unmapping_after_mapping_round_trips(self, env):
        env.put("ar", env.ar.id)
        assert env.row(env.get())["state"] == "mapped"
        env.put("ar", None)
        assert env.row(env.get())["state"] == "intentional"
        env.put("ar", env.ar.id)
        assert env.row(env.get())["state"] == "mapped"


class TestTheWriteContract:
    def test_omitting_gl_account_id_is_a_422_not_a_null(self, env):
        """"I did not say" and "I said none" are different sentences. Plaid's
        precedent, never EPD's exclude_none."""
        with pytest.raises(Exception) as ei:
            AccountingGLUpdate(purpose="ar")
        assert "gl_account_id" in str(ei.value)

    def test_an_unknown_purpose_is_refused_with_the_vocabulary_named(self, env):
        with pytest.raises(HTTPException) as ei:
            env.put("undeposited_funds", env.ar.id)
        assert ei.value.status_code == 400
        assert "Unknown purpose" in str(ei.value.detail)

    def test_a_foreign_tenants_account_is_refused(self, env):
        other = Company(id=str(uuid.uuid4()), name="Other",
                        slug=f"{_SLUG}other-{uuid.uuid4().hex[:6]}",
                        is_active=True, vertical="manufacturing")
        env.s.add(other); env.s.flush()
        theirs = env.mapping(name="THEIR AR", number="1200", tenant_id=other.id)
        env.s.commit()

        with pytest.raises(HTTPException) as ei:
            env.put("ar", theirs.id)
        assert ei.value.status_code == 400
        assert "THEIR AR" not in str(ei.value.detail)     # existence-oracle discipline
        assert env.row(env.get())["state"] == "unmapped"  # nothing written

    def test_an_inactive_account_cannot_be_SET(self, env):
        dead = env.mapping(name="OLD AR", number="1201", active=False)
        env.s.commit()
        with pytest.raises(HTTPException) as ei:
            env.put("ar", dead.id)
        assert ei.value.status_code == 400
        assert "inactive" in str(ei.value.detail)


class TestItActuallyClearsTheAR0Refusal:
    def test_the_panel_closes_the_gap_AR0_left(self, env):
        """THE POINT OF E-2, end to end. Before: resolve_ar_account raises and
        nothing in the product can fix it. After: one PUT and it resolves."""
        with pytest.raises(HTTPException) as ei:
            resolve_ar_account(env.s, env.co)
        assert "accounting GL settings" in str(ei.value.detail)

        env.put("ar", env.ar.id)

        got = resolve_ar_account(env.s, env.co)
        assert got.id == env.ar.id
        assert got.account_number == "1200"

    def test_deliberately_unmapped_still_refuses_and_that_is_correct(self, env):
        """Permitted, because the three-state machine is the contract and a
        tenant not using EPD may leave it unset. The PANEL states the cost;
        the resolver still fails closed."""
        env.put("ar", None)
        with pytest.raises(HTTPException):
            resolve_ar_account(env.s, env.co)


class TestTheCopyIsPartOfTheContract:
    def test_the_row_ships_its_own_label_description_and_cost(self, env):
        """Server-owned copy, not a client-side table: a new purpose must not
        render blank until someone remembers to add a note in the frontend."""
        row = env.row(env.get())
        assert row["label"] == "Accounts receivable"
        assert row["description"]
        assert row["unmapped_cost"]

    def test_the_unmapped_cost_names_the_consequence_AND_the_right_answer(self, env):
        """AR-unmapped is NOT payroll-unmapped. Payroll has no single right
        account; AR does, and the cost of choosing otherwise surfaces months
        later as what looks like a bug. The copy has to say both."""
        cost = env.row(env.get())["unmapped_cost"]
        assert "will not post" in cost                    # the consequence
        assert "ACCOUNTS RECEIVABLE-TRADE" in cost        # the right answer

    def test_only_ar_ships(self, env):
        """No speculative slots. bad_debt and finance_charge_income exist on the
        real chart and are NOT here, because nothing reads them yet — three
        blanks read as an unfinished form and get filled with the nearest
        plausible account, which is the payroll lesson."""
        assert [r["purpose"] for r in env.get()["purposes"]] == ["ar"]


# ── the payment bank default (AR-2 follow-up) ───────────────────────────────


class TestPaymentBankDefault:
    """AR-2 shipped `payment_bank_financial_account_id` with NO surface — AR-0's
    gap reproduced one arc later. This is the surface.

    A THIRD endpoint rather than an /accounting-gl row, for the same reason
    /accounting-gl is not a /keyword-gl row: the value TYPE differs. This holds
    a FinancialAccount.id; every accounting_gl value is a TenantGLMapping.id.
    """

    def _bank(self, env, *, gl=None, name="Operating"):
        from app.models.financial_account import FinancialAccount

        a = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=env.co, account_type="checking",
            account_name=name, gl_account_id=gl.id if gl else None,
        )
        env.s.add(a); env.s.flush()
        return a

    def _get(self, env):
        from app.api.routes.reconciliation import get_payment_bank
        return get_payment_bank(current_user=env.user, db=env.s)

    def _put(self, env, financial_account_id):
        from app.api.routes.reconciliation import PaymentBankUpdate, set_payment_bank
        return set_payment_bank(
            body=PaymentBankUpdate(financial_account_id=financial_account_id),
            current_user=env.user, db=env.s,
        )

    def test_unset_reads_as_unmapped_and_cannot_post(self, env):
        row = self._get(env)
        assert row["state"] == "unmapped"
        assert row["can_post"] is False

    def test_choosing_an_account_WITHOUT_a_gl_is_chosen_but_NOT_ready(self, env):
        """THE STATE PRODUCTION IS IN: one FinancialAccount, gl_account_id NULL.
        `state == "mapped"` says chosen; `can_post is False` says not ready. The
        two differ exactly here, and reporting only the first would send an operator
        away thinking they were finished."""
        bank = self._bank(env, gl=None)
        env.s.commit()

        row = self._put(env, bank.id)
        assert row["state"] == "mapped"          # chosen
        assert row["can_post"] is False          # not ready
        assert row["gl_account_number"] is None

    def test_choosing_an_account_WITH_a_gl_can_post(self, env):
        cash = env.mapping(name="JANDHA LLC - CASH CHECKING", number="1030")
        bank = self._bank(env, gl=cash)
        env.s.commit()

        row = self._put(env, bank.id)
        assert row["can_post"] is True
        assert row["gl_account_number"] == "1030"

    def test_it_actually_unblocks_posting(self, env):
        """End to end: with both settings the payment legs resolve."""
        from app.services.ar_payment_posting import resolve_payment_legs

        cash = env.mapping(name="JANDHA LLC - CASH CHECKING", number="1030")
        bank = self._bank(env, gl=cash)
        env.s.commit()
        env.put("ar", env.ar.id)                 # E-2's half
        self._put(env, bank.id)                  # this half

        cash_leg, ar_leg, reason = resolve_payment_legs(env.s, env.co)
        assert reason is None
        assert cash_leg.account_number == "1030"
        assert ar_leg.account_number == "1200"

    def test_a_foreign_tenants_account_is_refused(self, env):
        other = Company(id=str(uuid.uuid4()), name="Other",
                        slug=f"{_SLUG}other-{uuid.uuid4().hex[:6]}",
                        is_active=True, vertical="manufacturing")
        env.s.add(other); env.s.flush()
        from app.models.financial_account import FinancialAccount
        theirs = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=other.id, account_type="checking",
            account_name="Theirs",
        )
        env.s.add(theirs); env.s.commit()

        with pytest.raises(HTTPException) as ei:
            self._put(env, theirs.id)
        assert ei.value.status_code == 400
        assert self._get(env)["state"] == "unmapped"      # nothing written

    def test_clearing_it_is_permitted(self, env):
        cash = env.mapping(name="Cash", number="1030")
        bank = self._bank(env, gl=cash)
        env.s.commit()
        self._put(env, bank.id)
        row = self._put(env, None)
        assert row["state"] == "unmapped"
        assert row["can_post"] is False

    def test_omitting_the_field_is_a_422(self, env):
        from app.api.routes.reconciliation import PaymentBankUpdate
        with pytest.raises(Exception) as ei:
            PaymentBankUpdate()
        assert "financial_account_id" in str(ei.value)
