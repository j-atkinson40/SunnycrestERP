"""Ledger Posting arc L-1 — contra config: FK + keyword/contra GL resolvers.

Pins the L-1 mechanism:
  * validate_gl_account is the single gate — active + this-tenant only;
  * resolve_keyword_gl_account reads the settings map and FAILS CLOSED on
    unmapped / dangling / foreign / unknown-classification (never a silent id);
  * resolve_contra_gl_account fails closed on unset / dangling;
  * the r153 FK refuses a dangling contra id at the DB;
  * update_account (the C-1 hasattr fix) no longer nulls an OMITTED field, but
    an EXPLICIT null is still honored.

No money math here — this is resolution + fail-closed logic (the postings that
consume it are L-2/L-3). Cleans up its own `rgl-*` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import types
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.routes.reconciliation import AccountUpdate, update_account
from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.financial_account import FinancialAccount
from app.services import reconciliation_gl
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "rgl-"


def _mapping(tenant_id, *, name, number, active=True):
    return TenantGLMapping(
        id=str(uuid.uuid4()), tenant_id=tenant_id, platform_category=name.lower(),
        account_number=number, account_name=name, is_active=active,
    )


@pytest.fixture
def substrate():
    """Two companies (to prove tenant isolation), each with GL mappings + a bank
    account. co_a carries an active + an inactive mapping; co_b carries one
    mapping used to prove foreign-tenant rejection."""
    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co_a = Company(id=str(uuid.uuid4()), name=f"RGL A {sfx}", slug=f"{_SLUG_PREFIX}a-{sfx}",
                   is_active=True, vertical="manufacturing")
    co_b = Company(id=str(uuid.uuid4()), name=f"RGL B {sfx}", slug=f"{_SLUG_PREFIX}b-{sfx}",
                   is_active=True, vertical="manufacturing")
    s.add_all([co_a, co_b]); s.flush()

    active = _mapping(co_a.id, name="Bank Charges", number="6010", active=True)
    inactive = _mapping(co_a.id, name="Old Fees", number="6011", active=False)
    cash = _mapping(co_a.id, name="Operating Cash", number="1010", active=True)
    foreign = _mapping(co_b.id, name="B Bank Charges", number="6010", active=True)
    s.add_all([active, inactive, cash, foreign]); s.flush()

    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co_a.id,
                            account_type="checking", account_name="Operating")
    s.add(acct); s.commit()
    ids = {
        "co_a": co_a.id, "co_b": co_b.id, "active": active.id, "inactive": inactive.id,
        "cash": cash.id, "foreign": foreign.id, "acct": acct.id,
    }
    s.close()
    yield ids
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG_PREFIX}%")
    finally:
        s.close()


# ── validate_gl_account: the single gate ────────────────────────────────────

def test_validate_accepts_active_this_tenant(substrate):
    s = SessionLocal()
    try:
        m = reconciliation_gl.validate_gl_account(s, substrate["co_a"], substrate["active"])
        assert m is not None and m.id == substrate["active"]
    finally:
        s.close()


def test_validate_rejects_inactive(substrate):
    s = SessionLocal()
    try:
        assert reconciliation_gl.validate_gl_account(s, substrate["co_a"], substrate["inactive"]) is None
    finally:
        s.close()


def test_validate_rejects_foreign_tenant(substrate):
    """The foreign mapping is active — but owned by co_b. Asking as co_a → None."""
    s = SessionLocal()
    try:
        assert reconciliation_gl.validate_gl_account(s, substrate["co_a"], substrate["foreign"]) is None
    finally:
        s.close()


def test_validate_rejects_missing_and_empty(substrate):
    s = SessionLocal()
    try:
        assert reconciliation_gl.validate_gl_account(s, substrate["co_a"], str(uuid.uuid4())) is None
        assert reconciliation_gl.validate_gl_account(s, substrate["co_a"], None) is None
        assert reconciliation_gl.validate_gl_account(s, substrate["co_a"], "") is None
    finally:
        s.close()


# ── resolve_keyword_gl_account: fail closed ─────────────────────────────────

def test_keyword_unmapped_returns_none(substrate):
    """No settings map at all → unmapped → None (caller will exception)."""
    s = SessionLocal()
    try:
        co = s.get(Company, substrate["co_a"])
        assert reconciliation_gl.resolve_keyword_gl_account(s, co, "bank_fee") is None
    finally:
        s.close()


def test_keyword_mapped_active_resolves(substrate):
    s = SessionLocal()
    try:
        co = s.get(Company, substrate["co_a"])
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": substrate["active"]})
        assert reconciliation_gl.resolve_keyword_gl_account(s, co, "bank_fee") == substrate["active"]
    finally:
        s.close()


def test_keyword_mapped_to_inactive_is_dangling_none(substrate):
    s = SessionLocal()
    try:
        co = s.get(Company, substrate["co_a"])
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"payroll": substrate["inactive"]})
        assert reconciliation_gl.resolve_keyword_gl_account(s, co, "payroll") is None
    finally:
        s.close()


def test_keyword_mapped_to_foreign_is_none(substrate):
    s = SessionLocal()
    try:
        co = s.get(Company, substrate["co_a"])
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"nsf": substrate["foreign"]})
        assert reconciliation_gl.resolve_keyword_gl_account(s, co, "nsf") is None
    finally:
        s.close()


def test_keyword_unknown_classification_is_none(substrate):
    """A classification outside the ladder's fixed set is never answered, even if
    someone stuffs it into settings."""
    s = SessionLocal()
    try:
        co = s.get(Company, substrate["co_a"])
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"interest": substrate["active"]})
        assert reconciliation_gl.resolve_keyword_gl_account(s, co, "interest") is None
    finally:
        s.close()


# ── resolve_contra_gl_account: fail closed ──────────────────────────────────

def test_contra_unset_returns_none(substrate):
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, substrate["acct"])
        assert fa.gl_account_id is None
        assert reconciliation_gl.resolve_contra_gl_account(s, fa) is None
    finally:
        s.close()


def test_contra_valid_resolves(substrate):
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, substrate["acct"])
        fa.gl_account_id = substrate["cash"]
        s.commit()
        assert reconciliation_gl.resolve_contra_gl_account(s, fa) == substrate["cash"]
    finally:
        s.close()


def test_contra_dangling_returns_none(substrate):
    """gl_account_id set to an inactive mapping → None (refuse booking)."""
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, substrate["acct"])
        fa.gl_account_id = substrate["inactive"]
        s.commit()
        assert reconciliation_gl.resolve_contra_gl_account(s, fa) is None
    finally:
        s.close()


# ── r153 FK: the DB refuses a dangling contra id ────────────────────────────

def test_fk_refuses_nonexistent_gl_account(substrate):
    """Setting gl_account_id to an id with no tenant_gl_mappings row must fail at
    the DB (the r153 FK) — the convention is now a constraint."""
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, substrate["acct"])
        fa.gl_account_id = str(uuid.uuid4())  # no such mapping
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
    finally:
        s.close()


# ── update_account: the C-1 hasattr fix ─────────────────────────────────────

def test_update_account_preserves_omitted_gl_account(substrate):
    """A PATCH that omits gl_account_id must NOT null it (the foot-gun). Set a
    valid contra, then PATCH only account_name — gl_account_id survives."""
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, substrate["acct"])
        fa.gl_account_id = substrate["cash"]
        s.commit()
        user = types.SimpleNamespace(company_id=substrate["co_a"])
        body = AccountUpdate(account_type="checking", account_name="Renamed")
        update_account(substrate["acct"], body, current_user=user, db=s)
        s.refresh(fa)
        assert fa.account_name == "Renamed"
        assert fa.gl_account_id == substrate["cash"]  # preserved, not nulled
    finally:
        s.close()


def test_update_account_honors_explicit_null(substrate):
    """An EXPLICIT gl_account_id=None still clears it — exclude_unset includes a
    field the client actually sent, even when the value is null."""
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, substrate["acct"])
        fa.gl_account_id = substrate["cash"]
        s.commit()
        user = types.SimpleNamespace(company_id=substrate["co_a"])
        body = AccountUpdate(account_type="checking", account_name="Operating", gl_account_id=None)
        update_account(substrate["acct"], body, current_user=user, db=s)
        s.refresh(fa)
        assert fa.gl_account_id is None
    finally:
        s.close()
