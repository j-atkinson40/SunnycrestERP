"""Plaid routes (B-1) — the connect moment, tenant-admin gated.

ISOLATION FIRST: every handler scopes by current_user.company_id inside
the service query; wrong-tenant ids return 404 indistinguishable from
absent. NO response shape carries a token — ``item_summary`` is the only
serializer, and it has no token field by design.

Gating: reads = any tenant user (the setup card's connected state is
visible to everyone; non-admins see who to ask before connecting).
Mutations (link-token, exchange) = tenant admin.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services.plaid import service as plaid_service
from app.services.plaid.client import PlaidApiError, PlaidNotConfiguredError
from app.services.plaid.crypto import PlaidCredentialEncryptionError
from app.services.plaid.service import PlaidNotFoundError

router = APIRouter()


class ExchangeRequest(BaseModel):
    public_token: str
    institution_id: str | None = None
    institution_name: str | None = None


class LinkTokenRequest(BaseModel):
    # UPDATE MODE (re-auth): pass the degraded item's id — the server
    # decrypts its token; the raw token never leaves the backend.
    item_id: str | None = None


def _http_from_plaid_error(exc: PlaidApiError) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "code": "plaid_error",
            "error_type": exc.error_type,
            "error_code": exc.error_code,
            "message": exc.display_message
            or "The bank connection service returned an error.",
            "request_id": exc.request_id,
        },
    )


@router.get("/items")
def list_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tenant's connections + accounts — the setup card's read."""
    items = plaid_service.list_items(db, tenant_id=current_user.company_id)
    return [
        plaid_service.item_summary(
            item,
            plaid_service.list_accounts(
                db, tenant_id=current_user.company_id, item_id=item.id
            ),
        )
        for item in items
    ]


@router.get("/items/{item_id}")
def get_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        item = plaid_service.get_item(
            db, tenant_id=current_user.company_id, item_id=item_id
        )
        accounts = plaid_service.list_accounts(
            db, tenant_id=current_user.company_id, item_id=item_id
        )
    except PlaidNotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")
    return plaid_service.item_summary(item, accounts)


@router.post("/link-token")
def create_link_token(
    body: LinkTokenRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.services.plaid import client as plaid_client

    access_token = None
    if body and body.item_id:
        try:
            item = plaid_service.get_item(
                db, tenant_id=current_user.company_id, item_id=body.item_id
            )
        except PlaidNotFoundError:
            raise HTTPException(status_code=404, detail="Connection not found")
        try:
            access_token = plaid_service.access_token_for(item)
        except PlaidCredentialEncryptionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    try:
        resp = plaid_client.create_link_token(
            client_user_id=current_user.id, access_token=access_token,
        )
    except PlaidNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PlaidApiError as exc:
        raise _http_from_plaid_error(exc)
    return {"link_token": resp["link_token"], "expiration": resp.get("expiration")}


@router.post("/exchange")
def exchange_public_token(
    body: ExchangeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        item = plaid_service.record_item_from_exchange(
            db,
            tenant_id=current_user.company_id,
            public_token=body.public_token,
            institution_id=body.institution_id,
            institution_name=body.institution_name,
        )
    except PlaidNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PlaidCredentialEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PlaidApiError as exc:
        raise _http_from_plaid_error(exc)
    accounts = plaid_service.list_accounts(
        db, tenant_id=current_user.company_id, item_id=item.id
    )
    return plaid_service.item_summary(item, accounts)


class LinkAccountRequest(BaseModel):
    financial_account_id: str | None = None  # None = unlink (honest)


@router.patch("/accounts/{account_id}/link")
def link_bank_account(
    account_id: str,
    body: LinkAccountRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """B-3 linking management: which bank account feeds which platform
    account. Tenant-scoped with 404 indistinguishable rigor."""
    from app.models.financial_account import FinancialAccount
    from app.models.plaid import BankAccount

    acct = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id,
                BankAccount.tenant_id == current_user.company_id,
                BankAccount.is_active.is_(True))
        .first()
    )
    if acct is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if body.financial_account_id is not None:
        fa = (
            db.query(FinancialAccount)
            .filter(FinancialAccount.id == body.financial_account_id,
                    FinancialAccount.tenant_id == current_user.company_id)
            .first()
        )
        if fa is None:
            raise HTTPException(status_code=404, detail="Platform account not found")
    acct.financial_account_id = body.financial_account_id
    db.commit()
    return {"id": acct.id, "financial_account_id": acct.financial_account_id}


@router.post("/items/{item_id}/disconnect")
def disconnect_item(
    item_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """DISCONNECT with honest consequences: the feed stops; history and
    matches remain (removal is not retraction — the B-2 canon)."""
    try:
        item = plaid_service.get_item(
            db, tenant_id=current_user.company_id, item_id=item_id
        )
    except PlaidNotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")
    item.status = "disconnected"
    item.is_active = False
    db.commit()
    return {"id": item.id, "status": "disconnected",
            "message": "The feed stops; history and matches remain."}


# ── B-3: the category-map settings surface ──────────────────────────────

class CategoryOverrideRequest(BaseModel):
    plaid_category: str
    expense_category: str | None = None  # None clears the tenant override


@router.get("/category-mappings")
def list_category_mappings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Platform rows + the tenant's overlays, source-badged; plus the
    honest uncategorized count."""
    from app.models.plaid import BankTransaction, PlaidCategoryMapping

    rows = (
        db.query(PlaidCategoryMapping)
        .filter(
            PlaidCategoryMapping.is_active.is_(True),
            (PlaidCategoryMapping.tenant_id.is_(None))
            | (PlaidCategoryMapping.tenant_id == current_user.company_id),
        )
        .order_by(PlaidCategoryMapping.plaid_category)
        .all()
    )
    merged: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: r.tenant_id is not None):
        merged[r.plaid_category] = {
            "plaid_category": r.plaid_category,
            "expense_category": r.expense_category,
            "source": "yours" if r.tenant_id else "seeded",
        }
    uncategorized = (
        db.query(BankTransaction)
        .filter(BankTransaction.tenant_id == current_user.company_id,
                BankTransaction.expense_category.is_(None),
                BankTransaction.removed_at.is_(None))
        .count()
    )
    from app.services.plaid.categories import PLATFORM_EXPENSE_CATEGORIES
    return {
        "mappings": sorted(merged.values(), key=lambda m: m["plaid_category"]),
        "uncategorized_count": uncategorized,
        "expense_categories": list(PLATFORM_EXPENSE_CATEGORIES),
    }


@router.put("/category-mappings")
def set_category_override(
    body: CategoryOverrideRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Tenant override upsert (FORWARD-ONLY: applies to new transactions;
    history is never silently rewritten). None clears the override —
    the seeded row shines through again."""
    from app.models.plaid import PlaidCategoryMapping
    from app.services.plaid.categories import PLATFORM_EXPENSE_CATEGORIES

    if body.expense_category is not None and             body.expense_category not in PLATFORM_EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown expense category")
    row = (
        db.query(PlaidCategoryMapping)
        .filter(PlaidCategoryMapping.tenant_id == current_user.company_id,
                PlaidCategoryMapping.plaid_category == body.plaid_category)
        .first()
    )
    if body.expense_category is None:
        if row is not None:
            db.delete(row)
        db.commit()
        return {"cleared": True}
    if row is None:
        row = PlaidCategoryMapping(
            tenant_id=current_user.company_id,
            plaid_category=body.plaid_category,
            expense_category=body.expense_category,
        )
        db.add(row)
    else:
        row.expense_category = body.expense_category
        row.is_active = True
    db.commit()
    return {"plaid_category": row.plaid_category,
            "expense_category": row.expense_category, "source": "yours"}


@router.get("/transactions/uncategorized")
def list_uncategorized(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The uncategorized rows, reachable (the honest count's detail)."""
    from app.models.plaid import BankTransaction

    rows = (
        db.query(BankTransaction)
        .filter(BankTransaction.tenant_id == current_user.company_id,
                BankTransaction.expense_category.is_(None),
                BankTransaction.removed_at.is_(None))
        .order_by(BankTransaction.transaction_date.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [
        {
            "id": r.id, "date": r.transaction_date.isoformat(),
            "description": r.description, "amount": str(r.amount),
            "plaid_category_primary": r.plaid_category_primary,
            "plaid_category_detailed": r.plaid_category_detailed,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Session-1 cash wire — the cash position + the browse view
# ---------------------------------------------------------------------------


@router.get("/cash-position")
def cash_position(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The tenant's real cash, per account, with as-of honesty.

    THE DEFINITION (stated on every surface that renders this):
    cash on hand = sum of DEPOSITORY current balances. Credit accounts
    are listed as OWED — they never join cash on hand (standard
    practice; a credit line is not money you have).
    """
    from app.models.plaid import BankAccount, PlaidItem

    rows = (
        db.query(BankAccount, PlaidItem.institution_name, PlaidItem.status)
        .join(PlaidItem, PlaidItem.id == BankAccount.plaid_item_id)
        .filter(BankAccount.tenant_id == current_user.company_id,
                BankAccount.is_active.is_(True),
                PlaidItem.is_active.is_(True))
        .all()
    )
    accounts = []
    cash_on_hand = 0.0
    credit_owed = 0.0
    as_ofs = []
    for acc, inst, item_status in rows:
        # SIGN HONESTY: cash on hand = DEPOSITORY only. Credit and loans
        # are OWED. Investments are assets but not cash — they join
        # neither aggregate (listed per-account with their type).
        is_credit = acc.account_type in ("credit", "loan")
        is_cash = acc.account_type == "depository"
        cur = float(acc.current_balance) if acc.current_balance is not None else None
        if cur is not None:
            if is_credit:
                credit_owed += cur
            elif is_cash:
                cash_on_hand += cur
        if acc.balance_as_of:
            as_ofs.append(acc.balance_as_of)
        accounts.append({
            "id": acc.id,
            "institution": inst,
            "item_status": item_status,
            "name": acc.name,
            "mask": acc.mask,
            "account_type": acc.account_type,
            "account_subtype": acc.account_subtype,
            "is_credit": is_credit,
            "current_balance": cur,
            "available_balance": float(acc.available_balance)
            if acc.available_balance is not None else None,
            "balance_as_of": acc.balance_as_of.isoformat() if acc.balance_as_of else None,
        })
    return {
        "connected": bool(rows),
        "accounts": accounts,
        "cash_on_hand": round(cash_on_hand, 2),
        "credit_owed": round(credit_owed, 2),
        "as_of": min(as_ofs).isoformat() if as_ofs else None,
        "definition": (
            "Cash on hand = depository account balances only. Credit and "
            "loan balances are owed, not owned; investments are assets, "
            "not cash — all excluded."
        ),
    }


@router.get("/transactions")
def browse_transactions(
    account_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    per_page: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The bank-activity browse view — READ-ONLY (transactions get WORKED
    in reconciliation; this is where they get read). Pending badged;
    removed/superseded rows excluded per the B-2 canon (a retraction is
    surfaced through its own review path, never re-shown as activity)."""
    from datetime import date as _date

    from app.models.plaid import BankAccount, BankTransaction, PlaidItem

    # LIVE ITEMS ONLY — a disconnected/retired item's history does not
    # masquerade as current activity (the same rule cash-position keeps).
    q = (
        db.query(BankTransaction, BankAccount.name, BankAccount.mask)
        .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
        .join(PlaidItem, PlaidItem.id == BankAccount.plaid_item_id)
        .filter(BankTransaction.tenant_id == current_user.company_id,
                BankTransaction.removed_at.is_(None),
                PlaidItem.is_active.is_(True))
    )
    if account_id:
        q = q.filter(BankTransaction.bank_account_id == account_id)
    if start:
        q = q.filter(BankTransaction.transaction_date >= _date.fromisoformat(start))
    if end:
        q = q.filter(BankTransaction.transaction_date <= _date.fromisoformat(end))
    total = q.count()
    per_page = min(max(per_page, 1), 200)
    rows = (
        q.order_by(BankTransaction.transaction_date.desc(),
                   BankTransaction.id)
        .offset((max(page, 1) - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": t.id,
                "date": t.transaction_date.isoformat(),
                "account_name": name,
                "account_mask": mask,
                "description": t.description,
                "amount": str(t.amount),
                "pending": t.is_pending,
                "expense_category": t.expense_category,
                "plaid_category_primary": t.plaid_category_primary,
            }
            for t, name, mask in rows
        ],
    }
