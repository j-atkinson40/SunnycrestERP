"""The governed Plaid sync (B-2) — cursor-honest, crash-safe, trio-proven.

THE SIGN MAPPING (money math — stated ONCE, here):
    platform_amount = -1 × plaid_amount
Plaid: positive = money OUT of the account (a debit/charge); negative =
money IN (a deposit/refund). Platform (`ReconciliationTransaction` /
`BankTransaction`): positive = credit/deposit; negative = debit. Credit
cards follow the SAME negation: a card charge arrives Plaid-positive →
platform-negative debit; a payment TO the card arrives Plaid-negative →
platform-positive credit. Hand-computed cases pinned in test_plaid_b2.py.

THE CURSOR CONTRACT: one transaction per page — rows AND the advanced
cursor commit together. A crash between pages replays the last
uncommitted page idempotently (unique (tenant, plaid_transaction_id)
upsert), never skips it. Plaid's TRANSACTIONS_SYNC_MUTATION_DURING_
PAGINATION restarts from the last COMMITTED cursor — loudly logged,
bounded retries, never a silent loop.

THE TRIO:
  PENDING  — recorded as pending; the posted arrival UPDATES the pending
             row IN PLACE via pending_transaction_id (no duplicate; the
             posted truth wins).
  REMOVED  — `removed_at` stamped (idempotent). REMOVED-WHILE-MATCHED:
             a matched statement line in an UNCONFIRMED run flips back to
             unmatched with the retraction noted; in a CONFIRMED run the
             closed statement is NOT silently edited — a WorkflowReviewItem
             (review_focus_id="bank_retraction") lands in Decision Triage,
             decision-worthy, never silent.
  SIGNS    — the one negation above; nowhere else.

DRY-RUN = a REAL cursor peek: pages fetched read-only from the stored
cursor, counts computed, NOTHING persisted (rows, cursor, statuses).
The preview's numbers are real, never fake.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.financial_account import ReconciliationRun, ReconciliationTransaction
from app.models.plaid import BankAccount, BankTransaction, PlaidItem
from app.services.plaid import client as plaid_client
from app.services.plaid import categories as cat
from app.services.plaid.client import PlaidApiError
from app.services.plaid.service import access_token_for

logger = logging.getLogger(__name__)

_MUTATION_ERROR = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"
_MUTATION_RETRIES = 3
# The statuses that mean "this money was matched" for the retraction hook.
MATCHED_STATUSES = ("auto_cleared", "manually_matched", "suggested")


def to_platform_amount(plaid_amount) -> Decimal:
    """THE sign mapping — platform = -plaid. The only negation in the
    pipeline; everything downstream trusts platform sign."""
    return -Decimal(str(plaid_amount))


def _parse_date(v) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def run_sync_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None = None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
    workflow_run_id: str | None = None,
) -> dict:
    """Sync every active item for the tenant. The workflow-registry entry
    (`plaid_sync.run_sync_pipeline`) is dry_run-capable: under an
    unpromoted MoC trigger the engine invokes this WITH dry_run=True and
    the preview carries real counts."""
    items = (
        db.query(PlaidItem)
        .filter(PlaidItem.tenant_id == company_id, PlaidItem.is_active.is_(True))
        .order_by(PlaidItem.created_at)
        .all()
    )
    if not items:
        return {
            "dry_run": dry_run, "items_synced": 0, "message": "No bank connections",
            "ingested": 0, "updated": 0, "removed": 0, "uncategorized": 0,
        }

    mapping = cat.load_map(db, company_id)
    summary = {
        "dry_run": dry_run, "items_synced": 0, "items_errored": 0,
        "ingested": 0, "updated": 0, "removed": 0, "uncategorized": 0,
        "retractions_surfaced": 0, "items": [],
    }

    errors: list[str] = []
    for item in items:
        try:
            item_counts = _sync_item(
                db, item, mapping,
                dry_run=dry_run, workflow_run_id=workflow_run_id,
            )
            summary["items_synced"] += 1
            for k in ("ingested", "updated", "removed", "uncategorized",
                      "retractions_surfaced"):
                summary[k] += item_counts.get(k, 0)
            summary["items"].append(item_counts)
        except PlaidApiError as exc:
            summary["items_errored"] += 1
            errors.append(f"{item.institution_name}: {exc.error_code}")
            if not dry_run:
                # HONEST DEGRADATION — the B-1 card's degraded state + the
                # update-mode re-auth path read this status.
                if exc.error_code in ("ITEM_LOGIN_REQUIRED", "PENDING_EXPIRATION"):
                    item.status = "login_required" if exc.error_code == "ITEM_LOGIN_REQUIRED" else "pending_expiration"
                else:
                    item.status = "error"
                item.last_error_code = exc.error_code
                db.commit()
            logger.warning(
                "Plaid sync degraded item %s: %s (request %s)",
                item.id, exc.error_code, exc.request_id,
            )
            summary["items"].append({
                "item_id": item.id, "institution": item.institution_name,
                "status": "errored", "error_code": exc.error_code,
            })

    if summary["items_errored"] and summary["items_synced"] == 0:
        # EVERY item failed — the run itself fails so _fail_run routes it
        # into Decision Triage (H1). Partial failure stays a degradation.
        raise RuntimeError(
            "Plaid sync failed for all items: " + "; ".join(errors)
        )

    # The dry-run would-shape (real counts, the confirm's evidence).
    if dry_run:
        summary["would"] = (
            f"would ingest {summary['ingested']}, update {summary['updated']}, "
            f"remove {summary['removed']} "
            f"({summary['uncategorized']} would be uncategorized)"
        )
    return summary


def _sync_item(
    db: Session, item: PlaidItem, mapping: dict[str, str],
    *, dry_run: bool, workflow_run_id: str | None,
) -> dict:
    counts = {
        "item_id": item.id, "institution": item.institution_name,
        "status": "synced", "ingested": 0, "updated": 0, "removed": 0,
        "uncategorized": 0, "retractions_surfaced": 0, "pages": 0,
    }
    accounts = {
        a.plaid_account_id: a
        for a in db.query(BankAccount)
        .filter(BankAccount.plaid_item_id == item.id,
                BankAccount.tenant_id == item.tenant_id)
        .all()
    }
    access_token = access_token_for(item)

    mutation_restarts = 0
    cursor = item.sync_cursor
    while True:
        try:
            page = plaid_client.sync_transactions(access_token, cursor)
        except PlaidApiError as exc:
            if exc.error_code == _MUTATION_ERROR and mutation_restarts < _MUTATION_RETRIES:
                mutation_restarts += 1
                db.expire(item)
                cursor = item.sync_cursor  # last COMMITTED cursor
                logger.warning(
                    "Plaid pagination mutated mid-sync for item %s — "
                    "restarting from the last committed cursor (attempt %d/%d)",
                    item.id, mutation_restarts, _MUTATION_RETRIES,
                )
                continue
            raise

        counts["pages"] += 1
        for txn in page.get("added", []):
            uncat = _apply_added(db, item, accounts, mapping, txn, dry_run=dry_run)
            counts["ingested"] += 1
            counts["uncategorized"] += uncat
        for txn in page.get("modified", []):
            counts["updated"] += _apply_modified(db, item, mapping, txn, dry_run=dry_run)
        for rem in page.get("removed", []):
            r, surfaced = _apply_removed(
                db, item, rem, dry_run=dry_run, workflow_run_id=workflow_run_id,
            )
            counts["removed"] += r
            counts["retractions_surfaced"] += surfaced

        cursor = page.get("next_cursor")
        if not dry_run:
            # THE CURSOR CONTRACT: this page's rows + the cursor, one commit.
            item.sync_cursor = cursor
            item.last_synced_at = datetime.now(timezone.utc)
            if item.status != "active":
                item.status = "active"
                item.last_error_code = None
            db.commit()

        if not page.get("has_more"):
            break
    return counts


def _find_row(db: Session, tenant_id: str, plaid_txn_id: str) -> BankTransaction | None:
    return (
        db.query(BankTransaction)
        .filter(
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.plaid_transaction_id == plaid_txn_id,
        )
        .first()
    )


def _apply_fields(row: BankTransaction, txn: dict, mapping: dict[str, str]) -> int:
    """Shared field mapping for added/modified. Returns 1 if uncategorized."""
    pfc = txn.get("personal_finance_category") or {}
    row.amount = to_platform_amount(txn["amount"])
    row.transaction_date = _parse_date(txn.get("date")) or row.transaction_date
    row.authorized_date = _parse_date(txn.get("authorized_date"))
    row.description = txn.get("merchant_name") or txn.get("name") or row.description or "Transaction"
    row.raw_description = txn.get("name")
    row.plaid_category_primary = pfc.get("primary")
    row.plaid_category_detailed = pfc.get("detailed")
    row.expense_category = cat.resolve(mapping, pfc.get("primary"), pfc.get("detailed"))
    row.is_pending = bool(txn.get("pending"))
    return 0 if row.expense_category else 1


def _apply_added(
    db: Session, item: PlaidItem, accounts: dict[str, BankAccount],
    mapping: dict[str, str], txn: dict, *, dry_run: bool,
) -> int:
    """Upsert one added transaction. Returns 1 if it lands uncategorized."""
    pfc = txn.get("personal_finance_category") or {}
    if dry_run:
        return 0 if cat.resolve(mapping, pfc.get("primary"), pfc.get("detailed")) else 1

    existing = _find_row(db, item.tenant_id, txn["transaction_id"])
    if existing is not None:
        # Crash-replay idempotency: the page re-applies cleanly.
        return _apply_fields(existing, txn, mapping)

    # PENDING→POSTED: the posted arrival adopts the pending row in place.
    pending_id = txn.get("pending_transaction_id")
    if pending_id:
        pending_row = _find_row(db, item.tenant_id, pending_id)
        if pending_row is not None:
            pending_row.plaid_transaction_id = txn["transaction_id"]
            pending_row.pending_plaid_transaction_id = pending_id
            uncat = _apply_fields(pending_row, txn, mapping)
            pending_row.is_pending = False
            return uncat

    account = accounts.get(txn.get("account_id"))
    if account is None:
        # An account we never recorded (filtered at Link) — skip loudly.
        logger.warning("Plaid txn %s references unknown account — skipped",
                       txn["transaction_id"])
        return 0
    row = BankTransaction(
        tenant_id=item.tenant_id,
        bank_account_id=account.id,
        plaid_transaction_id=txn["transaction_id"],
        pending_plaid_transaction_id=txn.get("pending_transaction_id"),
        amount=Decimal("0"),
        transaction_date=_parse_date(txn.get("date")) or date.today(),
        description="Transaction",
    )
    uncat = _apply_fields(row, txn, mapping)
    db.add(row)
    return uncat


def _apply_modified(
    db: Session, item: PlaidItem, mapping: dict[str, str], txn: dict,
    *, dry_run: bool,
) -> int:
    if dry_run:
        return 1
    row = _find_row(db, item.tenant_id, txn["transaction_id"])
    if row is None:
        return 0
    _apply_fields(row, txn, mapping)
    return 1


def _apply_removed(
    db: Session, item: PlaidItem, rem: dict, *,
    dry_run: bool, workflow_run_id: str | None,
) -> tuple[int, int]:
    """Honor a retraction. Returns (removed_count, surfaced_count)."""
    txn_id = rem.get("transaction_id") if isinstance(rem, dict) else rem
    if dry_run:
        return (1, 0)
    row = _find_row(db, item.tenant_id, txn_id)
    if row is None:
        return (0, 0)
    if row.plaid_transaction_id != txn_id:
        # The row already ADOPTED its posted identity this page (the
        # pending→posted transition); this removal is Plaid's echo of the
        # retired pending id — never a retraction of the posted truth.
        return (0, 0)
    already = row.removed_at is not None
    row.removed_at = row.removed_at or datetime.now(timezone.utc)

    surfaced = 0
    # THE REMOVED-WHILE-MATCHED HOOK — retracted matched money is
    # decision-worthy, never silent.
    linked = (
        db.query(ReconciliationTransaction)
        .filter(ReconciliationTransaction.bank_transaction_id == row.id,
                ReconciliationTransaction.tenant_id == item.tenant_id)
        .all()
    )
    for line in linked:
        if line.match_status not in MATCHED_STATUSES:
            continue
        run = db.get(ReconciliationRun, line.reconciliation_run_id)
        if run is not None and run.status == "confirmed":
            # A CLOSED statement is never silently edited — surface the
            # decision into Decision Triage (workflow_review_triage reads
            # every undecided item regardless of focus id).
            if workflow_run_id:
                from app.models.workflow_review_item import WorkflowReviewItem
                db.add(WorkflowReviewItem(
                    run_id=workflow_run_id,
                    company_id=item.tenant_id,
                    review_focus_id="bank_retraction",
                    input_data={
                        "kind": "bank_retraction_on_confirmed_run",
                        "bank_transaction_id": row.id,
                        "reconciliation_run_id": run.id,
                        "reconciliation_transaction_id": line.id,
                        "description": line.description,
                        "amount": str(line.amount),
                        "note": "The bank retracted a transaction that was "
                                "matched on a confirmed reconciliation.",
                    },
                ))
                surfaced += 1
            else:
                # Manual/dev-scope sync outside a workflow run: no triage
                # anchor exists — loud log + the summary carries it.
                logger.warning(
                    "Bank retraction hit a CONFIRMED reconciliation "
                    "(line %s, run %s) during a runless sync — review manually.",
                    line.id, run.id,
                )
                surfaced += 1
        else:
            line.match_status = "unmatched"
            line.matched_record_type = None
            line.matched_record_id = None
            line.match_notes = ((line.match_notes or "") +
                                " [bank retracted this transaction]").strip()
    return (0 if already else 1, surfaced)
