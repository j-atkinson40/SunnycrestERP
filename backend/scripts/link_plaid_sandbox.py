"""Link a Plaid SANDBOX bank feed to a tenant — server-side, re-runnable, no
browser, no password (Path B).

The production link flow needs the interactive Plaid Link widget to mint a
public_token. This script uses ``/sandbox/public_token/create`` to mint one
server-side, then exchanges it through the EXACT same path the production flow
uses (``plaid_service.record_item_from_exchange``) — so the only new surface is
the sandbox token mint; the store/link/sync path is unchanged.

SANDBOX-ONLY: the client method refuses unless PLAID_ENV=sandbox, and this
script re-checks. It never touches the production link flow.

Full pipeline this script runs (each phase reported):
  1. mint sandbox public_token (First Platypus Bank, ins_109508)
  2. exchange → store PlaidItem + BankAccount rows (record_item_from_exchange)
  3. find-or-create a FinancialAccount + link the primary depository account
  4. run_sync_pipeline (dry_run=False, manual) → bank_transactions
  5. report: item, accounts, txn count + date range + B-1 columns

Re-running mints a fresh sandbox item; record_item_from_exchange reconnects an
existing item for the same (tenant, institution) and re-syncs.

Usage (against prod sandbox creds, from backend/):
  railway run --environment production --service SunnycrestERP \
      .venv/bin/python -m scripts.link_plaid_sandbox --tenant-slug sunnycrest

Requires CREDENTIAL_ENCRYPTION_KEY set (the exchange stores the access token
Fernet-encrypted); the script fails loudly + early if it is missing.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal
from app.models.company import Company
from app.models.financial_account import FinancialAccount
from app.models.plaid import BankAccount, BankTransaction
from app.models.user import User
from app.services.plaid import client as plaid_client
from app.services.plaid import service as plaid_service
from app.services.plaid.sync import run_sync_pipeline

_INSTITUTION_ID = "ins_109508"  # Plaid sandbox "First Platypus Bank"
_FINANCIAL_ACCOUNT_NAME = "Plaid Sandbox Operating"


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Link a Plaid sandbox feed (Path B).")
    ap.add_argument("--tenant-slug", default="sunnycrest")
    ap.add_argument("--no-sync", action="store_true", help="link only; skip sync")
    args = ap.parse_args()

    # Guard 1 — sandbox-only (defense-in-depth; the client also refuses).
    env = (settings.PLAID_ENV or "sandbox").lower()
    if env != "sandbox":
        _die(f"PLAID_ENV={env!r} — this script is sandbox-only.")
    # Guard 2 — the exchange encrypts the access token; fail early + legibly.
    if not os.environ.get("CREDENTIAL_ENCRYPTION_KEY"):
        _die(
            "CREDENTIAL_ENCRYPTION_KEY is not set — the exchange stores the "
            "access token Fernet-encrypted and will raise without it. Generate: "
            "python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())' and set it on the service."
        )

    P = lambda *a: print(">>>", *a, flush=True)  # noqa: E731
    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.slug == args.tenant_slug).first()
        if co is None:
            _die(f"tenant {args.tenant_slug!r} not found")
        user = (
            db.query(User)
            .filter(User.company_id == co.id, User.is_active.is_(True))
            .first()
        )
        P(f"tenant={co.slug} id={co.id} actor={getattr(user,'email',None)} PLAID_ENV={env}")

        # 1. mint sandbox public_token
        tok = plaid_client.create_sandbox_public_token(institution_id=_INSTITUTION_ID)
        P(f"1. sandbox public_token minted for {_INSTITUTION_ID}")

        # 2. exchange → store item + accounts (the production path)
        item = plaid_service.record_item_from_exchange(
            db, tenant_id=co.id, public_token=tok["public_token"],
            institution_id=_INSTITUTION_ID,
        )
        accounts = plaid_service.list_accounts(db, tenant_id=co.id, item_id=item.id)
        P(f"2. item stored: id={item.id} institution={item.institution_name!r} "
          f"status={item.status}; accounts={len(accounts)}")
        for a in accounts:
            P(f"     account {a.id}  {a.name!r}  type={a.account_type}  "
              f"linked_fin_acct={a.financial_account_id}")

        # 3. sync FIRST — the sandbox spreads transactions across accounts, so
        #    which accounts actually HOLD data is only knowable after a sync. A
        #    "first depository" guess before the sync linked an empty account
        #    (Cash Management had 0 txns while Checking/Credit Card held them).
        result = None
        if args.no_sync:
            P("3. --no-sync: skipping sync")
        else:
            result = run_sync_pipeline(
                db, company_id=co.id, triggered_by_user_id=getattr(user, "id", None),
                dry_run=False, trigger_source="manual",
            )
            P(f"3. sync result: {result}")

        # 4. find-or-create a FinancialAccount + link the account(s) that HOLD
        #    posted transactions (NOT a first-depository guess), so a subsequent
        #    populate_from_feed actually sees the feed.
        fa = (
            db.query(FinancialAccount)
            .filter(FinancialAccount.tenant_id == co.id,
                    FinancialAccount.account_name == _FINANCIAL_ACCOUNT_NAME)
            .first()
        )
        if fa is None:
            fa = FinancialAccount(
                id=str(uuid.uuid4()), tenant_id=co.id,
                account_type="checking", account_name=_FINANCIAL_ACCOUNT_NAME,
            )
            db.add(fa)
            db.flush()
            P(f"4. created FinancialAccount {fa.id} {_FINANCIAL_ACCOUNT_NAME!r}")
        else:
            P(f"4. reusing FinancialAccount {fa.id} {_FINANCIAL_ACCOUNT_NAME!r}")
        acct_ids = [a.id for a in accounts]
        holder_counts = (
            db.query(BankAccount.id, func.count(BankTransaction.id))
            .outerjoin(
                BankTransaction,
                (BankTransaction.bank_account_id == BankAccount.id)
                & (BankTransaction.is_pending.is_(False))
                & (BankTransaction.removed_at.is_(None)),
            )
            .filter(BankAccount.id.in_(acct_ids))
            .group_by(BankAccount.id)
            .all()
        )
        holders = [aid for aid, n in holder_counts if n > 0]
        if not holders:
            # --no-sync, or a genuinely empty feed: link one depository as a
            # placeholder so the run has something to point at.
            dep = next(
                (a.id for a in accounts if (a.account_type or "").lower() == "depository"),
                accounts[0].id if accounts else None,
            )
            if dep is None:
                _die("no bank accounts returned by the exchange")
            holders = [dep]
            P("   (no posted transactions yet — linked one depository as placeholder)")
        linked_names = []
        for aid in holders:
            ba = db.get(BankAccount, aid)
            ba.financial_account_id = fa.id
            linked_names.append(ba.name)
        db.commit()
        P(f"   linked {len(holders)} txn-holding account(s) → FinancialAccount "
          f"{fa.id}: {linked_names}")

        # 5. report what landed. NOTE on the B-1 columns: sandbox sends NO
        #    merchant enrichment — merchant_name / merchant_entity_id come back
        #    null and counterparties is an empty list. The columns are wired and
        #    store what Plaid sends; merchant→customer resolution is UNVALIDATED
        #    until production Plaid provides real enrichment.
        if args.no_sync:
            return
        q = db.query(BankTransaction).filter(BankTransaction.tenant_id == co.id)
        total = q.count()
        dmin, dmax = db.query(
            func.min(BankTransaction.transaction_date),
            func.max(BankTransaction.transaction_date),
        ).filter(BankTransaction.tenant_id == co.id).one()
        with_mn = q.filter(BankTransaction.merchant_name.isnot(None)).count()
        with_meid = q.filter(BankTransaction.merchant_entity_id.isnot(None)).count()
        with_cp = q.filter(BankTransaction.counterparties.isnot(None)).count()
        P(f"5. landed: {total} bank_transactions; date range {dmin}..{dmax}")
        P(f"   B-1 columns populated: merchant_name={with_mn}/{total} "
          f"merchant_entity_id={with_meid}/{total} counterparties={with_cp}/{total}")
        for t in q.order_by(BankTransaction.transaction_date.desc()).limit(5).all():
            P(f"     {t.transaction_date} {str(t.amount):>10} "
              f"{'pending' if t.is_pending else 'posted':<7} "
              f"cat={t.plaid_category_primary!r} desc={t.description!r} "
              f"merchant={t.merchant_name!r} meid={t.merchant_entity_id!r} "
              f"cparties={bool(t.counterparties)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
