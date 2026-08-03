"""Books Review Arc B B-1 — Plaid counterparty is persisted RAW, not discarded.

Pins that `_apply_fields` (via `_apply_added`) now lands the structured counterparty
signal Plaid returns — `merchant_name`, `merchant_entity_id`, and the raw
`counterparties` array — into the new r150 columns, while preserving the existing
`description = merchant_name or name` flattening for display back-compat. A txn without
the fields leaves the columns NULL (Plaid omits them freely).

No merchant→customer resolution is exercised — that is deferred; this is persistence
only. Cleans up its own `plaidcp-*` tenant via the shared FK-safe helper.
"""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.plaid import BankAccount, BankTransaction, PlaidItem
from app.services.plaid import sync as plaid_sync
from tests._cleanup import purge_companies_by_slug

_SLUG = "plaidcp-"


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"PlaidCP {suffix}", slug=f"{_SLUG}{suffix}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    item = PlaidItem(
        id=str(uuid.uuid4()), tenant_id=co.id, plaid_item_id=f"item-{suffix}",
        access_token_encrypted="placeholder-not-decrypted-in-this-test", status="active")
    s.add(item); s.flush()
    acct = BankAccount(
        id=str(uuid.uuid4()), tenant_id=co.id, plaid_item_id=item.id,
        plaid_account_id=f"acct-{suffix}", name="Operating", account_type="depository")
    s.add(acct); s.commit()
    yield type("Env", (), {"s": s, "co": co.id, "item": item,
                           "accounts": {acct.plaid_account_id: acct},
                           "acct_plaid_id": acct.plaid_account_id})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _get(env, plaid_txn_id):
    return env.s.query(BankTransaction).filter(
        BankTransaction.tenant_id == env.co,
        BankTransaction.plaid_transaction_id == plaid_txn_id).one()


def test_counterparty_structure_is_persisted_raw(env):
    txn = {
        "transaction_id": "txn-cp-1",
        "account_id": env.acct_plaid_id,
        "amount": 42.50,
        "date": "2026-07-15",
        "name": "SQ *BLUE BOTTLE",                     # Plaid `name` (raw)
        "merchant_name": "Blue Bottle Coffee",          # Plaid `merchant_name`
        "merchant_entity_id": "entity-abc123",          # Plaid stable merchant id
        "counterparties": [                              # Plaid `counterparties[]`
            {"name": "Blue Bottle Coffee", "type": "merchant",
             "entity_id": "entity-abc123", "confidence_level": "VERY_HIGH"},
            {"name": "Square", "type": "payment_app", "confidence_level": "HIGH"},
        ],
        "personal_finance_category": {"primary": "FOOD_AND_DRINK",
                                      "detailed": "FOOD_AND_DRINK.COFFEE"},
        "pending": False,
    }
    plaid_sync._apply_added(env.s, env.item, env.accounts, {}, txn, dry_run=False)
    env.s.commit()

    row = _get(env, "txn-cp-1")
    # the new structured columns
    assert row.merchant_name == "Blue Bottle Coffee"
    assert row.merchant_entity_id == "entity-abc123"
    assert isinstance(row.counterparties, list) and len(row.counterparties) == 2
    assert row.counterparties[0]["type"] == "merchant"
    assert row.counterparties[0]["entity_id"] == "entity-abc123"
    assert row.counterparties[1]["name"] == "Square"
    # display back-compat preserved: description still flattens merchant_name, and
    # raw_description keeps Plaid's `name`.
    assert row.description == "Blue Bottle Coffee"
    assert row.raw_description == "SQ *BLUE BOTTLE"


def test_missing_counterparty_fields_leave_columns_null(env):
    # Plaid omits merchant_name/counterparties on plenty of transactions (e.g. checks).
    txn = {
        "transaction_id": "txn-cp-2",
        "account_id": env.acct_plaid_id,
        "amount": 100.00,
        "date": "2026-07-16",
        "name": "CHECK 1234",
        "personal_finance_category": {},
        "pending": False,
    }
    plaid_sync._apply_added(env.s, env.item, env.accounts, {}, txn, dry_run=False)
    env.s.commit()

    row = _get(env, "txn-cp-2")
    assert row.merchant_name is None
    assert row.merchant_entity_id is None
    assert row.counterparties is None
    assert row.description == "CHECK 1234"              # falls back to `name`


def test_modified_txn_updates_counterparty_in_place(env):
    # A later /transactions/sync page can enrich counterparty data; the modified
    # path must overwrite, not leave stale values.
    base = {
        "transaction_id": "txn-cp-3", "account_id": env.acct_plaid_id,
        "amount": 5.00, "date": "2026-07-17", "name": "PENDING CHARGE",
        "personal_finance_category": {}, "pending": True,
    }
    plaid_sync._apply_added(env.s, env.item, env.accounts, {}, base, dry_run=False)
    env.s.commit()
    assert _get(env, "txn-cp-3").merchant_name is None

    enriched = {**base, "merchant_name": "Acme Supply",
                "merchant_entity_id": "entity-xyz",
                "counterparties": [{"name": "Acme Supply", "type": "merchant"}],
                "pending": False}
    plaid_sync._apply_modified(env.s, env.item, {}, enriched, dry_run=False)
    env.s.commit()

    row = _get(env, "txn-cp-3")
    assert row.merchant_name == "Acme Supply"
    assert row.merchant_entity_id == "entity-xyz"
    assert row.counterparties == [{"name": "Acme Supply", "type": "merchant"}]
