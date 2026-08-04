"""The financial-accounts form's round-trip contract (Ledger Posting L-2.1a).

The settings form at `frontend/src/pages/settings/financial-accounts.tsx` is about
to gain a GL-account picker for the bank contra. Before it does, the round trip it
already performs has to be trustworthy — because the form's idiom for optional
fields is ``form.x || null``, which sends an EXPLICIT null, and ``update_account``
uses ``model_dump(exclude_unset=True)``, under which an explicitly-sent null is a
deliberate clear. Any field the form fails to hydrate on open is therefore sent
back as null and silently lost on save.

``statement_closing_day`` was exactly that: never returned by ``list_accounts``,
never declared on the client's ``Account`` interface, hardcoded to ``""`` in
``openEdit`` — so every edit-save wiped it. Pinned here at the two layers where it
broke: the API must SURFACE the field (or the client cannot hydrate it), and the
API must PRESERVE it when omitted (the L-1 exclude_unset contract, re-asserted for
this field).

L-2.1b extends this to the other half of the same routes' write contract: what
they ACCEPT into ``gl_account_id``. The r153 FK gives existence only — not tenant
ownership and not ``is_active`` — so a mapping id belonging to ANOTHER TENANT
satisfied the constraint and was written. It failed later, at resolve, as
``contra_gl_dangling``: copy that is right for a mapping which drifted and
misleading for one that was never valid. Validated at the boundary now, through
the same ``validate_gl_account`` gate the resolvers use, so there is one
definition of a usable GL account rather than two.

Cleans up its own ``raf-`` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import types
import uuid

import pytest

from app.api.routes.reconciliation import AccountUpdate, list_accounts, update_account
from app.database import SessionLocal
from app.models.company import Company
from app.models.financial_account import FinancialAccount

_SLUG_PREFIX = "raf-"

# The body `payload()` builds in financial-accounts.tsx, verbatim in shape: every
# optional field present, empty ones as explicit null. This is what the server
# actually receives on a save — not a hypothetical.
def _form_payload(**overrides) -> dict:
    body = {
        "account_type": "checking",
        "account_name": "Operating",
        "institution_name": None,
        "last_four": None,
        "is_primary": False,
        "credit_limit": None,
        "statement_closing_day": None,
    }
    body.update(overrides)
    return body


@pytest.fixture
def substrate():
    from tests._cleanup import purge_companies_by_slug

    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"RAF {sfx}", slug=f"{_SLUG_PREFIX}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co)
    s.flush()
    acct = FinancialAccount(
        id=str(uuid.uuid4()), tenant_id=co.id, account_type="checking",
        account_name="Operating", statement_closing_day=15,
    )
    s.add(acct)
    s.commit()
    ids = {"co": co.id, "acct": acct.id}
    s.close()
    yield ids
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG_PREFIX}%")
    finally:
        s.close()


def test_list_accounts_surfaces_statement_closing_day(substrate):
    """The client cannot hydrate what the API does not return.

    This is the ROOT of the wipe: `list_accounts` omitted the field, so the form's
    `Account` interface could not declare it, so `openEdit` hardcoded "", so
    `payload()` sent null. Fixing only the client would leave it re-breakable by
    anyone who trusts the response shape.
    """
    s = SessionLocal()
    try:
        user = types.SimpleNamespace(company_id=substrate["co"])
        rows = list_accounts(current_user=user, db=s)
        row = next(r for r in rows if r["id"] == substrate["acct"])
        assert "statement_closing_day" in row, (
            "list_accounts must return statement_closing_day — the client hydrates "
            "its edit form from this response"
        )
        assert row["statement_closing_day"] == 15
    finally:
        s.close()


def test_edit_save_that_does_not_touch_closing_day_preserves_it(substrate):
    """THE BUG, from the client's side.

    A hydrated form sends the value back unchanged, so the save is a no-op for
    this field. Pre-fix the form sent null here (openEdit hardcoded "") and the
    15 was lost on an edit that only renamed the account.
    """
    s = SessionLocal()
    try:
        user = types.SimpleNamespace(company_id=substrate["co"])
        body = AccountUpdate(**_form_payload(account_name="Renamed",
                                             statement_closing_day=15))
        update_account(substrate["acct"], body, current_user=user, db=s)
        fa = s.get(FinancialAccount, substrate["acct"])
        s.refresh(fa)
        assert fa.account_name == "Renamed"
        assert fa.statement_closing_day == 15
    finally:
        s.close()


def test_omitted_closing_day_is_preserved(substrate):
    """The L-1 exclude_unset contract, re-asserted for this field: a PATCH that
    OMITS statement_closing_day leaves it alone. Guards the other direction of
    the fix — surfacing the field must not make the server start requiring it."""
    s = SessionLocal()
    try:
        user = types.SimpleNamespace(company_id=substrate["co"])
        body = AccountUpdate(account_type="checking", account_name="Renamed")
        update_account(substrate["acct"], body, current_user=user, db=s)
        fa = s.get(FinancialAccount, substrate["acct"])
        s.refresh(fa)
        assert fa.statement_closing_day == 15
    finally:
        s.close()


def test_explicit_null_closing_day_still_clears(substrate):
    """Clearing must stay possible. An EXPLICIT null is a deliberate clear — the
    same semantics gl_account_id relies on (test_reconciliation_gl_l1.py). The fix
    for the wipe is that the client stops sending null by accident, NOT that the
    server stops honoring it."""
    s = SessionLocal()
    try:
        user = types.SimpleNamespace(company_id=substrate["co"])
        body = AccountUpdate(**_form_payload(statement_closing_day=None))
        update_account(substrate["acct"], body, current_user=user, db=s)
        fa = s.get(FinancialAccount, substrate["acct"])
        s.refresh(fa)
        assert fa.statement_closing_day is None
    finally:
        s.close()


# ── L-2.1b: what the routes ACCEPT into gl_account_id ───────────────────────

@pytest.fixture
def gl_substrate():
    """Two tenants. `mine` carries an active + an inactive mapping; `theirs`
    carries an active one, to prove the foreign-tenant case — the r153 FK is
    satisfied by it, so only an explicit check can refuse it."""
    from app.models.accounting_analysis import TenantGLMapping
    from tests._cleanup import purge_companies_by_slug

    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    mine = Company(id=str(uuid.uuid4()), name=f"RAF M {sfx}",
                   slug=f"{_SLUG_PREFIX}m-{sfx}", is_active=True,
                   vertical="manufacturing")
    theirs = Company(id=str(uuid.uuid4()), name=f"RAF T {sfx}",
                     slug=f"{_SLUG_PREFIX}t-{sfx}", is_active=True,
                     vertical="manufacturing")
    s.add_all([mine, theirs])
    s.flush()

    def _m(tenant_id, name, number, active):
        m = TenantGLMapping(id=str(uuid.uuid4()), tenant_id=tenant_id,
                            platform_category="current_asset", account_number=number,
                            account_name=name, is_active=active)
        s.add(m)
        return m

    active = _m(mine.id, "Operating Cash", "1010", True)
    inactive = _m(mine.id, "Closed Cash", "1011", False)
    foreign = _m(theirs.id, "Their Cash", "1010", True)
    s.flush()

    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=mine.id,
                            account_type="checking", account_name="Operating")
    s.add(acct)
    s.commit()
    ids = {"mine": mine.id, "acct": acct.id, "active": active.id,
           "inactive": inactive.id, "foreign": foreign.id}
    s.close()
    yield ids
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG_PREFIX}%")
    finally:
        s.close()


def _patch(s, ids, **fields):
    user = types.SimpleNamespace(company_id=ids["mine"])
    body = AccountUpdate(account_type="checking", account_name="Operating", **fields)
    return update_account(ids["acct"], body, current_user=user, db=s)


def test_update_rejects_foreign_tenant_gl_account(gl_substrate):
    """THE ONE THAT MATTERS. The FK is satisfied — the row exists — so nothing
    below the route refuses it, and the write succeeded pre-L-2.1b. A contra
    pointing into another tenant's chart is the GL-leak shape."""
    from fastapi import HTTPException

    s = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            _patch(s, gl_substrate, gl_account_id=gl_substrate["foreign"])
        assert exc.value.status_code == 400
        s.rollback()
        fa = s.get(FinancialAccount, gl_substrate["acct"])
        s.refresh(fa)
        assert fa.gl_account_id is None  # nothing written
    finally:
        s.close()


def test_update_rejects_inactive_gl_account(gl_substrate):
    """Own tenant, but deactivated. `validate_gl_account` refuses it at resolve;
    refusing it at write means the operator learns at the moment of the mistake."""
    from fastapi import HTTPException

    s = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            _patch(s, gl_substrate, gl_account_id=gl_substrate["inactive"])
        assert exc.value.status_code == 400
        # The message distinguishes inactive from absent — different fixes.
        assert "inactive" in str(exc.value.detail).lower()
        s.rollback()
    finally:
        s.close()


def test_update_rejects_nonexistent_gl_account(gl_substrate):
    """No such mapping anywhere. Pre-L-2.1b this reached the DB and raised an
    opaque IntegrityError from the r153 FK; now it is a legible 400."""
    from fastapi import HTTPException

    s = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            _patch(s, gl_substrate, gl_account_id=str(uuid.uuid4()))
        assert exc.value.status_code == 400
        s.rollback()
    finally:
        s.close()


def test_foreign_and_nonexistent_read_the_same(gl_substrate):
    """Both say 'not in your chart of accounts'. Naming the foreign case as
    foreign would confirm that a row exists in another tenant — the error message
    must not be a cross-tenant existence oracle."""
    from fastapi import HTTPException

    s = SessionLocal()
    try:
        with pytest.raises(HTTPException) as a:
            _patch(s, gl_substrate, gl_account_id=gl_substrate["foreign"])
        s.rollback()
        with pytest.raises(HTTPException) as b:
            _patch(s, gl_substrate, gl_account_id=str(uuid.uuid4()))
        s.rollback()
        assert str(a.value.detail) == str(b.value.detail)
    finally:
        s.close()


def test_update_accepts_active_own_tenant_gl_account(gl_substrate):
    """The happy path still writes."""
    s = SessionLocal()
    try:
        _patch(s, gl_substrate, gl_account_id=gl_substrate["active"])
        fa = s.get(FinancialAccount, gl_substrate["acct"])
        s.refresh(fa)
        assert fa.gl_account_id == gl_substrate["active"]
    finally:
        s.close()


def test_update_accepts_explicit_null_gl_account(gl_substrate):
    """Clearing stays legal — validation gates VALUES, not the deliberate clear.
    This is the path the contra picker's clear control depends on."""
    s = SessionLocal()
    try:
        fa = s.get(FinancialAccount, gl_substrate["acct"])
        fa.gl_account_id = gl_substrate["active"]
        s.commit()
        _patch(s, gl_substrate, gl_account_id=None)
        s.refresh(fa)
        assert fa.gl_account_id is None
    finally:
        s.close()


def test_create_rejects_foreign_tenant_gl_account(gl_substrate):
    """Same gate on the create path — an account can be born mis-pointed."""
    from fastapi import HTTPException

    from app.api.routes.reconciliation import AccountCreate, create_account

    s = SessionLocal()
    try:
        user = types.SimpleNamespace(company_id=gl_substrate["mine"])
        body = AccountCreate(account_type="checking", account_name="Second",
                             gl_account_id=gl_substrate["foreign"])
        with pytest.raises(HTTPException) as exc:
            create_account(body, current_user=user, db=s)
        assert exc.value.status_code == 400
        s.rollback()
    finally:
        s.close()


def test_create_accepts_active_own_tenant_gl_account(gl_substrate):
    """The create happy path."""
    from app.api.routes.reconciliation import AccountCreate, create_account

    s = SessionLocal()
    try:
        user = types.SimpleNamespace(company_id=gl_substrate["mine"])
        body = AccountCreate(account_type="checking", account_name="Second",
                             gl_account_id=gl_substrate["active"])
        out = create_account(body, current_user=user, db=s)
        fa = s.get(FinancialAccount, out["id"])
        assert fa.gl_account_id == gl_substrate["active"]
    finally:
        s.close()
