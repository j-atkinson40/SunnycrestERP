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
