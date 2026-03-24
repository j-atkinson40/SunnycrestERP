"""Bank/credit card reconciliation API routes."""

import csv
import io
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationAdjustment,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──

class AccountCreate(BaseModel):
    account_type: str
    account_name: str
    institution_name: str | None = None
    last_four: str | None = None
    gl_account_id: str | None = None
    is_primary: bool = False
    credit_limit: float | None = None
    statement_closing_day: int | None = None


class StartRunRequest(BaseModel):
    account_id: str
    statement_date: str
    statement_closing_balance: float
    period_start: str | None = None


class TransactionActionRequest(BaseModel):
    action: str  # confirm, reject, create_expense, mark_payroll, mark_transfer, exclude
    matched_record_id: str | None = None
    matched_record_type: str | None = None
    notes: str | None = None


class AdjustmentCreate(BaseModel):
    adjustment_type: str
    description: str
    amount: float


# ── Financial Accounts ──

@router.get("/accounts")
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = (
        db.query(FinancialAccount)
        .filter(FinancialAccount.tenant_id == current_user.company_id, FinancialAccount.is_active == True)
        .order_by(FinancialAccount.sort_order)
        .all()
    )
    today = date.today()
    return [
        {
            "id": a.id, "account_type": a.account_type, "account_name": a.account_name,
            "institution_name": a.institution_name, "last_four": a.last_four,
            "is_primary": a.is_primary, "gl_account_id": a.gl_account_id,
            "last_reconciled_date": str(a.last_reconciled_date) if a.last_reconciled_date else None,
            "last_reconciled_balance": float(a.last_reconciled_balance) if a.last_reconciled_balance else None,
            "credit_limit": float(a.credit_limit) if a.credit_limit else None,
            "days_since_reconciled": (today - a.last_reconciled_date).days if a.last_reconciled_date else None,
            "status": (
                "current" if a.last_reconciled_date and (today - a.last_reconciled_date).days < 28 else
                "due_soon" if a.last_reconciled_date and (today - a.last_reconciled_date).days < 35 else
                "overdue" if a.last_reconciled_date else "never"
            ),
        }
        for a in accounts
    ]


@router.post("/accounts")
def create_account(
    body: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(func.count(FinancialAccount.id)).filter(
        FinancialAccount.tenant_id == current_user.company_id, FinancialAccount.is_active == True,
    ).scalar() or 0
    if count >= 5:
        raise HTTPException(400, "Maximum 5 active accounts")

    account = FinancialAccount(
        tenant_id=current_user.company_id,
        account_type=body.account_type,
        account_name=body.account_name,
        institution_name=body.institution_name,
        last_four=body.last_four,
        gl_account_id=body.gl_account_id,
        is_primary=body.is_primary,
        credit_limit=Decimal(str(body.credit_limit)) if body.credit_limit else None,
        statement_closing_day=body.statement_closing_day,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"id": account.id}


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: str, body: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id, FinancialAccount.tenant_id == current_user.company_id,
    ).first()
    if not acct:
        raise HTTPException(404, "Account not found")
    for field in ["account_type", "account_name", "institution_name", "last_four", "gl_account_id", "is_primary", "statement_closing_day"]:
        if hasattr(body, field):
            setattr(acct, field, getattr(body, field))
    if body.credit_limit is not None:
        acct.credit_limit = Decimal(str(body.credit_limit))
    db.commit()
    return {"status": "updated"}


# ── Reconciliation Runs ──

@router.post("/runs/start")
def start_run(
    body: StartRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.query(FinancialAccount).filter(
        FinancialAccount.id == body.account_id, FinancialAccount.tenant_id == current_user.company_id,
    ).first()
    if not acct:
        raise HTTPException(404, "Account not found")

    ps = date.fromisoformat(body.period_start) if body.period_start else (
        acct.last_reconciled_date + __import__("datetime").timedelta(days=1) if acct.last_reconciled_date else None
    )

    run = ReconciliationRun(
        tenant_id=current_user.company_id,
        financial_account_id=body.account_id,
        statement_date=date.fromisoformat(body.statement_date),
        statement_closing_balance=Decimal(str(body.statement_closing_balance)),
        period_start=ps,
        period_end=date.fromisoformat(body.statement_date),
        opening_balance=acct.last_reconciled_balance or Decimal(0),
        created_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"id": run.id, "status": run.status}


@router.post("/runs/{run_id}/upload-csv")
async def upload_csv(
    run_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.id == run_id, ReconciliationRun.tenant_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    rows = list(reader)

    # Detect columns using saved mapping or heuristics
    acct = db.query(FinancialAccount).filter(FinancialAccount.id == run.financial_account_id).first()
    mapping = _detect_columns(headers, rows[:5], acct)

    # Parse transactions
    transactions = []
    for i, row in enumerate(rows):
        try:
            txn_date = _parse_date(row.get(mapping["date_column"], ""), mapping.get("date_format", "MM/DD/YYYY"))
            desc = row.get(mapping["description_column"], "").strip()
            amount = _parse_amount(row, mapping)
            ref = row.get(mapping.get("reference_column", ""), "").strip() or None

            if not desc or amount == 0:
                continue

            transactions.append(ReconciliationTransaction(
                tenant_id=current_user.company_id,
                reconciliation_run_id=run_id,
                transaction_date=txn_date,
                description=desc,
                raw_description=desc,
                amount=Decimal(str(amount)),
                transaction_type="credit" if amount > 0 else "debit",
                reference_number=ref,
                sort_order=i,
            ))
        except Exception as e:
            logger.warning(f"Skipping row {i}: {e}")

    db.add_all(transactions)
    run.total_statement_transactions = len(transactions)
    run.csv_row_count = len(rows)
    run.status = "matching"
    db.commit()

    # Save column mapping for future imports
    if acct and not acct.csv_date_column:
        acct.csv_date_column = mapping.get("date_column")
        acct.csv_description_column = mapping.get("description_column")
        acct.csv_amount_column = mapping.get("amount_column")
        acct.csv_debit_column = mapping.get("debit_column")
        acct.csv_credit_column = mapping.get("credit_column")
        acct.csv_date_format = mapping.get("date_format")
        db.commit()

    return {
        "transactions_parsed": len(transactions),
        "total_rows": len(rows),
        "column_mapping": mapping,
        "preview": [
            {"date": str(t.transaction_date), "description": t.description, "amount": float(t.amount)}
            for t in transactions[:5]
        ],
    }


@router.post("/runs/{run_id}/run-matching")
def trigger_matching(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the matching engine on all parsed transactions."""
    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.id == run_id, ReconciliationRun.tenant_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    transactions = db.query(ReconciliationTransaction).filter(
        ReconciliationTransaction.reconciliation_run_id == run_id,
    ).order_by(ReconciliationTransaction.sort_order).all()

    # Load platform records for matching
    try:
        from app.models.payment import Payment
        payments = db.query(Payment).filter(
            Payment.company_id == current_user.company_id,
            Payment.payment_date >= run.period_start,
            Payment.payment_date <= run.statement_date,
        ).all()
    except Exception:
        payments = []

    try:
        from app.models.bill_payment import BillPayment
        bill_payments = db.query(BillPayment).filter(
            BillPayment.tenant_id == current_user.company_id,
        ).all()
    except Exception:
        bill_payments = []

    # Build lookup: amount → list of platform records
    payment_by_amount: dict[str, list] = {}
    for p in payments:
        key = str(round(float(p.amount), 2))
        payment_by_amount.setdefault(key, []).append(("customer_payment", p.id, p.payment_date, getattr(p, "reference_number", None)))

    auto_count = 0
    suggested_count = 0
    unmatched_count = 0
    cleared_total = Decimal(0)

    for txn in transactions:
        amt = abs(float(txn.amount))
        amt_key = str(round(amt, 2))

        # Pattern recognition first
        desc_upper = txn.description.upper()
        if any(kw in desc_upper for kw in ["SERVICE CHARGE", "MONTHLY FEE", "WIRE FEE", "OVERDRAFT", "ATM FEE"]):
            txn.match_status = "bank_fee"
            txn.match_confidence = Decimal("0.90")
            suggested_count += 1
            continue
        if any(kw in desc_upper for kw in ["PAYROLL", "ADP", "GUSTO", "PAYCHEX"]):
            txn.match_status = "payroll"
            txn.match_confidence = Decimal("0.92")
            auto_count += 1
            cleared_total += txn.amount
            continue
        if any(kw in desc_upper for kw in ["RETURNED", "NSF", "INSUFFICIENT", "REVERSAL"]):
            txn.match_status = "nsf"
            txn.match_confidence = Decimal("0.88")
            suggested_count += 1
            continue

        # Exact amount match
        candidates = payment_by_amount.get(amt_key, [])
        if len(candidates) == 1:
            rec_type, rec_id, rec_date, rec_ref = candidates[0]
            days_diff = abs((txn.transaction_date - rec_date).days) if rec_date else 999
            if days_diff <= 5:
                conf = Decimal("0.98") if days_diff == 0 else Decimal("0.95") if days_diff <= 2 else Decimal("0.90")
                txn.match_status = "auto_cleared"
                txn.match_confidence = conf
                txn.matched_record_type = rec_type
                txn.matched_record_id = rec_id
                auto_count += 1
                cleared_total += txn.amount
                candidates.clear()  # consumed
                continue

        # Reference match
        if txn.reference_number:
            for cands in payment_by_amount.values():
                for c in cands:
                    if c[3] and c[3] == txn.reference_number:
                        txn.match_status = "auto_cleared"
                        txn.match_confidence = Decimal("0.97")
                        txn.matched_record_type = c[0]
                        txn.matched_record_id = c[1]
                        auto_count += 1
                        cleared_total += txn.amount
                        cands.remove(c)
                        break
                if txn.match_status == "auto_cleared":
                    break

        if txn.match_status == "unmatched":
            unmatched_count += 1

    # Update run
    run.auto_cleared_count = auto_count
    run.suggested_count = suggested_count
    run.unmatched_count = unmatched_count
    run.platform_cleared_balance = cleared_total
    run.difference = run.statement_closing_balance - (run.opening_balance or Decimal(0)) - cleared_total
    run.status = "in_review"
    db.commit()

    return {
        "auto_cleared": auto_count,
        "suggested": suggested_count,
        "unmatched": unmatched_count,
        "status": "in_review",
    }


@router.get("/runs/{run_id}/status")
def get_run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.id == run_id, ReconciliationRun.tenant_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return {
        "id": run.id, "status": run.status,
        "total": run.total_statement_transactions,
        "auto_cleared": run.auto_cleared_count,
        "suggested": run.suggested_count,
        "unmatched": run.unmatched_count,
        "statement_closing_balance": float(run.statement_closing_balance),
        "platform_cleared_balance": float(run.platform_cleared_balance or 0),
        "outstanding_checks_total": float(run.outstanding_checks_total or 0),
        "adjustments_total": float(run.adjustments_total or 0),
        "difference": float(run.difference or 0),
    }


@router.get("/runs/{run_id}/transactions")
def get_transactions(
    run_id: str,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ReconciliationTransaction).filter(
        ReconciliationTransaction.reconciliation_run_id == run_id,
        ReconciliationTransaction.tenant_id == current_user.company_id,
    )
    if status:
        statuses = status.split(",")
        query = query.filter(ReconciliationTransaction.match_status.in_(statuses))
    txns = query.order_by(ReconciliationTransaction.sort_order).all()
    return [
        {
            "id": t.id, "date": str(t.transaction_date), "description": t.description,
            "amount": float(t.amount), "type": t.transaction_type,
            "reference": t.reference_number, "match_status": t.match_status,
            "confidence": float(t.match_confidence) if t.match_confidence else None,
            "matched_record_type": t.matched_record_type,
            "matched_record_id": t.matched_record_id,
            "match_notes": t.match_notes,
        }
        for t in txns
    ]


@router.patch("/transactions/{txn_id}/action")
def transaction_action(
    txn_id: str,
    body: TransactionActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txn = db.query(ReconciliationTransaction).filter(
        ReconciliationTransaction.id == txn_id, ReconciliationTransaction.tenant_id == current_user.company_id,
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")

    now = datetime.now(timezone.utc)
    action_map = {
        "confirm": "auto_cleared",
        "reject": "unmatched",
        "create_expense": "new_expense",
        "mark_payroll": "payroll",
        "mark_transfer": "excluded",
        "exclude": "excluded",
        "mark_outstanding": "outstanding",
    }

    txn.match_status = action_map.get(body.action, body.action)
    if body.matched_record_id:
        txn.matched_record_id = body.matched_record_id
        txn.matched_record_type = body.matched_record_type
        txn.match_status = "manually_matched"
    txn.match_notes = body.notes
    txn.reviewed_by = current_user.id
    txn.reviewed_at = now
    db.commit()
    return {"status": txn.match_status}


@router.post("/runs/{run_id}/adjustments")
def create_adjustment(
    run_id: str, body: AdjustmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adj = ReconciliationAdjustment(
        tenant_id=current_user.company_id,
        reconciliation_run_id=run_id,
        adjustment_type=body.adjustment_type,
        description=body.description,
        amount=Decimal(str(body.amount)),
        created_by=current_user.id,
    )
    db.add(adj)

    # Recalculate adjustments total and difference
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
    if run:
        all_adj = db.query(func.coalesce(func.sum(ReconciliationAdjustment.amount), 0)).filter(
            ReconciliationAdjustment.reconciliation_run_id == run_id,
        ).scalar()
        run.adjustments_total = all_adj + Decimal(str(body.amount))
        run.difference = run.statement_closing_balance - (run.opening_balance or Decimal(0)) - (run.platform_cleared_balance or Decimal(0)) - run.outstanding_checks_total + run.outstanding_deposits_total + run.adjustments_total

    db.commit()
    return {"id": adj.id}


@router.post("/runs/{run_id}/confirm")
def confirm_reconciliation(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.id == run_id, ReconciliationRun.tenant_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")
    if abs(float(run.difference)) > 0.005:
        raise HTTPException(400, f"Difference must be $0.00 to confirm. Current: ${float(run.difference):.2f}")

    now = datetime.now(timezone.utc)
    run.status = "confirmed"
    run.confirmed_by = current_user.id
    run.confirmed_at = now

    acct = db.query(FinancialAccount).filter(FinancialAccount.id == run.financial_account_id).first()
    if acct:
        acct.last_reconciled_date = run.statement_date
        acct.last_reconciled_balance = run.statement_closing_balance
        acct.last_reconciliation_id = run.id

    db.commit()
    return {"status": "confirmed"}


@router.get("/history/{account_id}")
def get_history(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.financial_account_id == account_id,
            ReconciliationRun.tenant_id == current_user.company_id,
            ReconciliationRun.status == "confirmed",
        )
        .order_by(ReconciliationRun.statement_date.desc())
        .limit(12)
        .all()
    )
    return [
        {
            "id": r.id, "statement_date": str(r.statement_date),
            "closing_balance": float(r.statement_closing_balance),
            "transactions": r.total_statement_transactions,
            "auto_cleared": r.auto_cleared_count,
            "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
        }
        for r in runs
    ]


# ── Helpers ──

def _detect_columns(headers: list[str], sample_rows: list[dict], account: FinancialAccount | None) -> dict:
    """Detect CSV column mapping from headers and sample data."""
    if account and account.csv_date_column:
        return {
            "date_column": account.csv_date_column,
            "description_column": account.csv_description_column,
            "amount_column": account.csv_amount_column,
            "debit_column": account.csv_debit_column,
            "credit_column": account.csv_credit_column,
            "date_format": account.csv_date_format or "MM/DD/YYYY",
        }

    mapping = {"date_format": "MM/DD/YYYY"}
    headers_lower = {h: h.lower() for h in headers}

    for h, hl in headers_lower.items():
        if "date" in hl and "date_column" not in mapping:
            mapping["date_column"] = h
        elif "desc" in hl or "memo" in hl or "narrative" in hl:
            mapping["description_column"] = h
        elif hl in ("amount", "amt"):
            mapping["amount_column"] = h
        elif "debit" in hl or "withdrawal" in hl:
            mapping["debit_column"] = h
        elif "credit" in hl or "deposit" in hl:
            mapping["credit_column"] = h
        elif "balance" in hl:
            mapping["balance_column"] = h
        elif "ref" in hl or "check" in hl or "number" in hl:
            mapping["reference_column"] = h

    if "date_column" not in mapping and headers:
        mapping["date_column"] = headers[0]
    if "description_column" not in mapping and len(headers) > 1:
        mapping["description_column"] = headers[1]
    if "amount_column" not in mapping and "debit_column" not in mapping and len(headers) > 2:
        mapping["amount_column"] = headers[2]

    return mapping


def _parse_date(date_str: str, fmt: str = "MM/DD/YYYY") -> date:
    """Parse a date string to a date object."""
    import re
    date_str = date_str.strip()
    for pattern, py_fmt in [
        (r"\d{1,2}/\d{1,2}/\d{4}", "%m/%d/%Y"),
        (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
        (r"\d{1,2}-\d{1,2}-\d{4}", "%m-%d-%Y"),
        (r"\d{1,2}/\d{1,2}/\d{2}", "%m/%d/%y"),
    ]:
        if re.match(pattern, date_str):
            return datetime.strptime(date_str, py_fmt).date()
    return datetime.strptime(date_str, "%m/%d/%Y").date()


def _parse_amount(row: dict, mapping: dict) -> float:
    """Parse amount from row — handles single and split column formats."""
    def clean(val: str) -> float:
        val = val.strip().replace(",", "").replace("$", "")
        if val.startswith("(") and val.endswith(")"):
            return -float(val[1:-1])
        return float(val) if val else 0

    if mapping.get("amount_column"):
        return clean(row.get(mapping["amount_column"], "0"))

    debit = clean(row.get(mapping.get("debit_column", ""), "0"))
    credit = clean(row.get(mapping.get("credit_column", ""), "0"))
    return credit - debit if (credit or debit) else 0
