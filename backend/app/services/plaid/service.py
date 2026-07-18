"""Plaid item lifecycle service (B-1) — isolation-first, transactional.

TENANT ISOLATION AT FULL RIGOR: every read scopes tenant_id inside the
query; a wrong-tenant id raises ``PlaidNotFoundError`` indistinguishable
from absent (the existence-hint discipline — company A can never see,
count, or infer company B's banking).

EXCHANGE TRANSACTIONALITY: ``record_item_from_exchange`` performs the
Plaid calls FIRST (exchange → accounts → institution), then writes item +
accounts in one flush; any failure before commit leaves zero rows — a
failed exchange never half-records an item.

RECONNECT IDEMPOTENCY (the investigation's key strategy): reconnecting an
institution creates a NEW Plaid item with NEW plaid_account_ids. We match
the existing active item by (tenant, institution_id) and UPDATE it in
place (new item id + token, cursor RESET — a new item is a new
transaction stream), re-pointing its accounts by (mask, subtype) → name
fallback so `financial_account_id` links survive. No duplicates.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.plaid import BankAccount, PlaidItem
from app.services.plaid import client as plaid_client
from app.services.plaid.crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


class PlaidNotFoundError(Exception):
    """Absent OR other-tenant — deliberately indistinguishable."""


def list_items(db: Session, *, tenant_id: str) -> list[PlaidItem]:
    return (
        db.query(PlaidItem)
        .filter(PlaidItem.tenant_id == tenant_id, PlaidItem.is_active.is_(True))
        .order_by(PlaidItem.created_at)
        .all()
    )


def get_item(db: Session, *, tenant_id: str, item_id: str) -> PlaidItem:
    item = (
        db.query(PlaidItem)
        .filter(
            PlaidItem.id == item_id,
            PlaidItem.tenant_id == tenant_id,
            PlaidItem.is_active.is_(True),
        )
        .first()
    )
    if item is None:
        raise PlaidNotFoundError("Connection not found")
    return item


def list_accounts(db: Session, *, tenant_id: str, item_id: str) -> list[BankAccount]:
    # get_item enforces the tenant boundary first — an other-tenant item id
    # 404s before any account query runs.
    item = get_item(db, tenant_id=tenant_id, item_id=item_id)
    return (
        db.query(BankAccount)
        .filter(
            BankAccount.plaid_item_id == item.id,
            BankAccount.tenant_id == tenant_id,
            BankAccount.is_active.is_(True),
        )
        .order_by(BankAccount.name)
        .all()
    )


def access_token_for(item: PlaidItem) -> str:
    """The ONLY read path for the raw token (decrypt-for-API-call)."""
    return decrypt_token(item.access_token_encrypted)


def record_item_from_exchange(
    db: Session, *, tenant_id: str, public_token: str,
    institution_id: str | None = None, institution_name: str | None = None,
) -> PlaidItem:
    """The connect moment: exchange → accounts → one transactional write."""
    exchange = plaid_client.exchange_public_token(public_token)
    access_token = exchange["access_token"]
    plaid_item_id = exchange["item_id"]

    accounts_resp = plaid_client.get_accounts(access_token)
    inst_id = institution_id or (accounts_resp.get("item") or {}).get("institution_id")
    inst_name = institution_name
    if inst_id and not inst_name:
        try:
            inst_name = plaid_client.get_institution(inst_id)["institution"]["name"]
        except Exception:  # noqa: BLE001 — name is cosmetic; never block the link
            logger.warning("Could not resolve institution name for %s", inst_id)

    existing = (
        db.query(PlaidItem)
        .filter(
            PlaidItem.tenant_id == tenant_id,
            PlaidItem.institution_id == inst_id,
            PlaidItem.is_active.is_(True),
        )
        .first()
        if inst_id
        else None
    )

    if existing is not None:
        # RECONNECT: update in place; cursor resets (new stream).
        item = existing
        item.plaid_item_id = plaid_item_id
        item.access_token_encrypted = encrypt_token(access_token)
        item.status = "active"
        item.last_error_code = None
        item.sync_cursor = None
        if inst_name:
            item.institution_name = inst_name
    else:
        item = PlaidItem(
            tenant_id=tenant_id,
            plaid_item_id=plaid_item_id,
            institution_id=inst_id,
            institution_name=inst_name,
            access_token_encrypted=encrypt_token(access_token),
            status="active",
        )
        db.add(item)
    db.flush()

    _upsert_accounts(db, item=item, plaid_accounts=accounts_resp.get("accounts") or [])
    db.commit()
    db.refresh(item)
    return item


def _upsert_accounts(db: Session, *, item: PlaidItem, plaid_accounts: list[dict]) -> None:
    existing = (
        db.query(BankAccount)
        .filter(
            BankAccount.plaid_item_id == item.id,
            BankAccount.tenant_id == item.tenant_id,
        )
        .all()
    )
    by_plaid_id = {a.plaid_account_id: a for a in existing}
    unmatched = [a for a in existing]

    def _find_reconnect_match(acc: dict) -> BankAccount | None:
        # New item = new plaid_account_ids; match by (mask, subtype), then
        # name — keeps financial_account links intact across reconnects.
        for row in unmatched:
            if acc.get("mask") and row.mask == acc.get("mask") and \
                    row.account_subtype == (acc.get("subtype") or None):
                return row
        for row in unmatched:
            if row.name == acc.get("name"):
                return row
        return None

    for acc in plaid_accounts:
        balances = acc.get("balances") or {}
        row = by_plaid_id.get(acc["account_id"]) or _find_reconnect_match(acc)
        if row is not None:
            if row in unmatched:
                unmatched.remove(row)
            row.plaid_account_id = acc["account_id"]
            row.name = acc.get("name") or row.name
            row.official_name = acc.get("official_name")
            row.mask = acc.get("mask")
            row.account_type = acc.get("type") or row.account_type
            row.account_subtype = acc.get("subtype")
            row.current_balance = balances.get("current")
            row.available_balance = balances.get("available")
            row.is_active = True
        else:
            db.add(BankAccount(
                tenant_id=item.tenant_id,
                plaid_item_id=item.id,
                plaid_account_id=acc["account_id"],
                name=acc.get("name") or "Account",
                official_name=acc.get("official_name"),
                mask=acc.get("mask"),
                account_type=acc.get("type") or "depository",
                account_subtype=acc.get("subtype"),
                current_balance=balances.get("current"),
                available_balance=balances.get("available"),
            ))
    db.flush()


def item_summary(item: PlaidItem, accounts: list[BankAccount]) -> dict:
    """The route response shape — NO token field exists on it, by design."""
    return {
        "id": item.id,
        "institution_name": item.institution_name,
        "institution_id": item.institution_id,
        "status": item.status,
        "last_synced_at": item.last_synced_at.isoformat() if item.last_synced_at else None,
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "mask": a.mask,
                "account_type": a.account_type,
                "account_subtype": a.account_subtype,
                "is_credit": a.account_type == "credit",
                "financial_account_id": a.financial_account_id,
            }
            for a in accounts
        ],
    }
