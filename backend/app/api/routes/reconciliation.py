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

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationAdjustment,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.user import User
from app.services import (
    early_payment_discount_service,
    reconciliation_gl,
    reconciliation_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_valid_gl_account(db: Session, tenant_id: str, gl_account_id: str) -> None:
    """Refuse a contra that is not an ACTIVE mapping owned by this tenant.

    The r153 FK gives EXISTENCE only — not tenant ownership, not ``is_active`` —
    so a mapping id belonging to another tenant satisfied the constraint and was
    written, then failed far away at resolve as ``contra_gl_dangling``. That is
    the right copy for a mapping which drifted and the wrong copy for one that
    was never valid, and it surfaces long after the mistake. (L-2.1b.)

    L-2.2 moved the body to ``reconciliation_gl.require_gl_account`` so the
    journal-entry route could share it verbatim rather than grow a second check.
    This stays as the local name the routes below read by.
    """
    reconciliation_gl.require_gl_account(db, tenant_id, gl_account_id)


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


class AccountUpdate(AccountCreate):
    is_active: bool | None = None


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

@router.get("/flag-recipients")
def flag_recipients(
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Books Review B-4.5 — internal users a reconciliation exception can be
    flagged to ("Ask someone"), each with their current open-ask load
    ("N already waiting") so the picker can show it. Tenant-scoped, active users,
    internal only (external recipients are deferred — the cross-tenant channel
    does not exist)."""
    from app.models.financial_account import ReconciliationFlag

    query = db.query(User).filter(
        User.company_id == current_user.company_id, User.is_active.is_(True)
    )
    term = q.strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            User.first_name.ilike(like)
            | User.last_name.ilike(like)
            | User.email.ilike(like)
        )
    users = query.order_by(User.first_name, User.last_name).limit(20).all()

    # Open-ask load per recipient — one grouped count (cheap).
    counts = dict(
        db.query(ReconciliationFlag.owner_user_id, func.count(ReconciliationFlag.id))
        .filter(
            ReconciliationFlag.tenant_id == current_user.company_id,
            ReconciliationFlag.destination == "ask_someone",
            ReconciliationFlag.returned_at.is_(None),
        )
        .group_by(ReconciliationFlag.owner_user_id)
        .all()
    )
    return {
        "recipients": [
            {
                "id": u.id,
                "name": (f"{u.first_name} {u.last_name}".strip() or u.email),
                "email": u.email,
                "waiting_count": int(counts.get(u.id, 0)),
            }
            for u in users
        ]
    }


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
            # The client hydrates its edit form from this response, and every
            # field it CANNOT hydrate it sends back as an explicit null — which
            # `update_account`'s exclude_unset reads as a deliberate clear. So an
            # editable column missing here is a silent wipe on the next save, not
            # merely an absent readout. statement_closing_day was exactly that.
            # (Ledger Posting L-2.1a.)
            "statement_closing_day": a.statement_closing_day,
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

    # An account can be born mis-pointed, so the create path takes the same gate.
    if body.gl_account_id:
        _require_valid_gl_account(db, current_user.company_id, body.gl_account_id)

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
    account_id: str, body: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id, FinancialAccount.tenant_id == current_user.company_id,
    ).first()
    if not acct:
        raise HTTPException(404, "Account not found")
    # exclude_unset: apply ONLY the fields the client actually sent. hasattr on a
    # Pydantic model is always true, so the prior fixed-field loop silently nulled
    # every OMITTED optional field (the C-1 signature: a silent write of the wrong
    # value, no error). gl_account_id now carries the bank contra account — a
    # partial PATCH that nulled it would unmap the account and every subsequent
    # reconciliation JE would refuse to book. (Ledger Posting arc L-1.)
    changes = body.model_dump(exclude_unset=True)
    # Gate VALUES, not the deliberate clear: an explicit null stays legal (it is
    # the contra picker's clear path, pinned in test_reconciliation_gl_l1).
    if changes.get("gl_account_id"):
        _require_valid_gl_account(db, current_user.company_id, changes["gl_account_id"])
    for field in ("account_type", "account_name", "institution_name", "last_four",
                  "gl_account_id", "is_primary", "statement_closing_day", "is_active"):
        if field in changes:
            setattr(acct, field, changes[field])
    if "credit_limit" in changes:
        acct.credit_limit = (
            Decimal(str(changes["credit_limit"])) if changes["credit_limit"] is not None else None
        )
    db.commit()
    return {"status": "updated"}


# ── Keyword → GL map (Ledger Posting L-2.1e) ──
#
# The tenant-wide half of reconciliation GL config; the per-account half is the
# contra on `financial_accounts` above. Both legs of the same journal entry, so
# both live on one settings page.
#
# PUT rather than PATCH, and an explicit null ACTS rather than being dropped —
# the Plaid category-map precedent (`plaid.py::set_category_override`), not the
# EPD one (`discount.py::update_settings`, which uses exclude_none and therefore
# cannot clear its GL account at all). Here a null is the whole point: it is how
# an operator says "this kind does not post automatically", which for payroll and
# nsf is the correct answer on a real chart rather than an unfinished one.
#
# require_admin, matching the structural sibling (plaid.py) and all of Vault
# Accounting — including the flow that CREATES the TenantGLMapping rows this maps
# to. NOTE THE ASYMMETRY, deliberately left rather than silently widened: the
# other leg, PATCH /accounts/{id}, is still get_current_user like the rest of this
# router, so a non-admin can set a bank account's contra through the accounts form
# but cannot touch the keyword map. Re-gating 14 routes is its own decision.

_KEYWORD_STATE_MAPPED = "mapped"
_BLOCK_TO_STATE = {
    reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED: "unmapped",
    reconciliation_gl.BLOCK_KEYWORD_GL_INTENTIONAL: "intentional",
    reconciliation_gl.BLOCK_KEYWORD_GL_DANGLING: "dangling",
}


class KeywordGLUpdate(BaseModel):
    classification: str
    # NO DEFAULT — the field is required, so omitting it is a 422 rather than
    # silently meaning null. "I did not say" and "I said none" are different
    # sentences and this endpoint must not conflate them.
    gl_account_id: str | None


def _keyword_gl_payload(db: Session, company) -> dict:
    """State per classification, derived from the RUNTIME resolver.

    Never re-inferred from the settings dict. The configure script inferred it
    and started lying the moment a third state existed — a deliberate null read
    as "unmapped", so it told an operator to configure what they had just chosen
    not to configure.
    """
    out = []
    for c in reconciliation_gl.KEYWORD_CLASSIFICATIONS:
        mapping, reason = reconciliation_gl.keyword_gl_with_reason(db, company, c)
        out.append({
            "classification": c,
            "state": _KEYWORD_STATE_MAPPED if mapping else _BLOCK_TO_STATE.get(reason, "unmapped"),
            "gl_account_id": mapping.id if mapping else None,
            "account_number": mapping.account_number if mapping else None,
            "account_name": mapping.account_name if mapping else None,
        })
    return {"classifications": out}


@router.get("/keyword-gl")
def get_keyword_gl(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Readable by anyone — the panel shows state to everyone and only lets an
    admin change it, the BankCategoriesSettings idiom."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")
    return _keyword_gl_payload(db, company)


@router.put("/keyword-gl")
def set_keyword_gl(
    body: KeywordGLUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Map a classification to a GL account, or mark it as deliberately not
    posting (`gl_account_id: null` — PRESENT and null, never a removed key)."""
    from app.models.company import Company

    if body.classification not in reconciliation_gl.KEYWORD_CLASSIFICATIONS:
        raise HTTPException(
            400,
            f"Unknown classification {body.classification!r} — expected one of "
            f"{', '.join(reconciliation_gl.KEYWORD_CLASSIFICATIONS)}.",
        )
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")

    if body.gl_account_id is not None:
        _require_valid_gl_account(db, current_user.company_id, body.gl_account_id)

    current = dict(
        (company.settings or {}).get(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY) or {}
    )
    # Assignment, never `pop` on null: key PRESENT and null is a decision, an
    # absent key means nobody has decided, and the Books Review card says
    # different things for the two.
    current[body.classification] = body.gl_account_id
    company.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, current)
    db.commit()
    return _keyword_gl_payload(db, company)


# ── Accounting GL purposes (AR-2.0 E-2) ──
#
# A SIBLING endpoint to /keyword-gl, not an extension of it, and the reason is
# the validation vocabulary. `/keyword-gl` validates against
# KEYWORD_CLASSIFICATIONS — a code-fixed three-value set. `accounting_gl` keys
# are PURPOSES, open-ended and growing one per arc that needs one. A single PUT
# serving both would branch on which vocabulary applied, which is two functions
# wearing one name — the thing `decide` vs `decide_coded` avoided.
#
# The FRONTEND does extend: /settings/accounts renders both sections from one
# chart fetch, because the operator's job is the same job even though the
# server's is not.
#
# ONE KEY SHIPS: "ar". `bad_debt` (8650 BAD DEBTS) and `finance_charge_income`
# (9200 FINANCE CHARGE INCOME) both exist on the chart and are both needed
# eventually — by write-offs and by finance-charge posting, neither of which is
# built. Shipping empty slots for them is the payroll lesson exactly: three
# blanks read as an unfinished form and get filled with the nearest plausible
# account. `undeposited_funds` would be worse still — it names an account that
# does not exist on the chart at all (AR-2 is blocked on precisely that), so the
# slot would be unfillable and would read as the platform's bug. Each key
# arrives with the arc that reads it.

# NOTE ON WHERE THE KEY LIVES: `ACCOUNTING_GL_SETTINGS_KEY` is defined in
# `early_payment_discount_service` because AR-0 put it there alongside its first
# consumer, `resolve_ar_account`. It is now read from two modules and it is not
# really EPD's concept — an accounting-GL settings key belongs somewhere
# neutral. Left where it is rather than moved as a side effect of building a
# panel; worth relocating when a THIRD consumer appears, which is the point at
# which the current home stops being defensible.

# Purpose → what the operator is choosing, and what it costs to leave unmapped.
# The COPY IS PART OF THE CONTRACT (L-2.1e): a panel that presents a neutral
# blank invites the nearest plausible answer.
_ACCOUNTING_GL_PURPOSES: dict[str, dict[str, str]] = {
    "ar": {
        "label": "Accounts receivable",
        "description": (
            "The control account customer balances post against. Early-payment "
            "discounts credit it."
        ),
        # UNLIKE PAYROLL, THERE IS A RIGHT ANSWER HERE, and the copy says so.
        # Payroll-unmapped is correct — no single account fits a net ACH draw.
        # AR-unmapped is a CHOICE WITH A CONSEQUENCE, and the consequence
        # surfaces months later as what looks like a bug.
        "unmapped_cost": (
            "Marking this unmapped means early-payment discounts will not post. "
            "An account named ACCOUNTS RECEIVABLE-TRADE is almost certainly what "
            "you want."
        ),
    },
}


class AccountingGLUpdate(BaseModel):
    purpose: str
    # NO DEFAULT, same reason as KeywordGLUpdate: omitting it is a 422, because
    # "I did not say" and "I said none" are different sentences.
    gl_account_id: str | None


def _accounting_gl_payload(db: Session, company) -> dict:
    """State per purpose, derived from the SETTINGS + the runtime validator.

    Three states, per L-2.1c, and the order of the checks is load-bearing —
    `null` is falsy, so testing presence BEFORE truthiness is what keeps a
    deliberate unmapping from reading as a gap nobody has closed yet.
    """
    from app.services.reconciliation_gl import validate_gl_account

    stored = (company.settings or {}).get(
        early_payment_discount_service.ACCOUNTING_GL_SETTINGS_KEY
    ) or {}
    out = []
    for purpose, meta in _ACCOUNTING_GL_PURPOSES.items():
        present = isinstance(stored, dict) and purpose in stored
        gl_id = stored.get(purpose) if present else None

        if present and gl_id is None:
            state, mapping = "intentional", None
        elif not gl_id:
            state, mapping = "unmapped", None
        else:
            mapping = validate_gl_account(db, company.id, gl_id)
            state = "mapped" if mapping is not None else "dangling"

        out.append({
            "purpose": purpose,
            "label": meta["label"],
            "description": meta["description"],
            "unmapped_cost": meta["unmapped_cost"],
            "state": state,
            "gl_account_id": mapping.id if mapping else None,
            "account_number": mapping.account_number if mapping else None,
            "account_name": mapping.account_name if mapping else None,
        })
    return {"purposes": out}


@router.get("/accounting-gl")
def get_accounting_gl(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Readable by anyone; only an admin may change it. Same idiom as
    /keyword-gl — the panel shows state to everyone."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")
    return _accounting_gl_payload(db, company)


@router.put("/accounting-gl")
def set_accounting_gl(
    body: AccountingGLUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Map a purpose to a GL account, or mark it deliberately unmapped
    (`gl_account_id: null` — PRESENT and null, never a removed key).

    AR-0 shipped the resolver and its fail-closed refusal with NO authoring
    surface, so a tenant hitting that refusal could not clear it without direct
    settings access. This is that surface.
    """
    from app.models.company import Company

    if body.purpose not in _ACCOUNTING_GL_PURPOSES:
        raise HTTPException(
            400,
            f"Unknown purpose {body.purpose!r} — expected one of "
            f"{', '.join(_ACCOUNTING_GL_PURPOSES)}.",
        )
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")

    if body.gl_account_id is not None:
        _require_valid_gl_account(db, current_user.company_id, body.gl_account_id)

    current = dict(
        (company.settings or {}).get(
            early_payment_discount_service.ACCOUNTING_GL_SETTINGS_KEY
        ) or {}
    )
    # Assignment, never `pop` on null — key PRESENT and null is a decision.
    current[body.purpose] = body.gl_account_id
    company.set_setting(
        early_payment_discount_service.ACCOUNTING_GL_SETTINGS_KEY, current
    )
    db.commit()
    return _accounting_gl_payload(db, company)


# ── The payment bank default (AR-2.0 follow-up) ──
#
# AR-2 shipped `payment_bank_financial_account_id` with NO surface, which is
# AR-0's gap reproduced one arc later: a tenant who needs to configure it has no
# way to. This closes it, using E-2 as the template.
#
# A THIRD endpoint rather than a row on /accounting-gl, for the reason that kept
# /accounting-gl separate from /keyword-gl: the value TYPE differs. Every
# accounting_gl value is a TenantGLMapping.id and its panel row renders a
# GLAccountPicker; this holds a FinancialAccount.id and renders a bank picker.
# Folding it in would make one endpoint validate two id types and one picker
# wrong for one row.
#
# The two are shown in the SAME card, because the operator's question — "where
# does the platform post when it books for me" — is one question even though the
# server answers it from two vocabularies.


class PaymentBankUpdate(BaseModel):
    # NO DEFAULT, same contract as the other two: omitting it is a 422, and an
    # explicit null is "we have not chosen one", not "I forgot to say".
    financial_account_id: str | None


def _payment_bank_payload(db: Session, company) -> dict:
    """The chosen bank account and whether it can actually post.

    TWO SETTINGS IN TWO PLACES have to line up before a payment posts: this
    choice, and the chosen account's own `gl_account_id` (set on the account
    edit form, L-2.1e's other half). Production today has this unset AND the
    contra unset on its only account, so reporting only the first would send an
    operator away thinking they were done.
    """
    from app.models.financial_account import FinancialAccount
    from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY
    from app.services.reconciliation_gl import contra_gl_with_reason

    settings = company.settings or {}
    chosen_id = settings.get(PAYMENT_BANK_SETTINGS_KEY)
    account = None
    if chosen_id:
        account = (
            db.query(FinancialAccount)
            .filter(
                FinancialAccount.id == chosen_id,
                FinancialAccount.tenant_id == company.id,
            )
            .first()
        )

    if account is None:
        return {
            "financial_account_id": None,
            "account_name": None,
            "state": "unmapped" if chosen_id is None else "dangling",
            "gl_account_number": None,
            "gl_account_name": None,
            "can_post": False,
        }

    cash, _reason = contra_gl_with_reason(db, account)
    return {
        "financial_account_id": account.id,
        "account_name": account.account_name,
        # "mapped" means CHOSEN; `can_post` is the one that means ready, and
        # they differ exactly when the account's own GL account is missing.
        "state": "mapped",
        "gl_account_number": cash.account_number if cash else None,
        "gl_account_name": cash.account_name if cash else None,
        "can_post": cash is not None,
    }


@router.get("/payment-bank")
def get_payment_bank(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")
    return _payment_bank_payload(db, company)


@router.put("/payment-bank")
def set_payment_bank(
    body: PaymentBankUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Choose the bank account customer payments are recorded into."""
    from app.models.company import Company
    from app.models.financial_account import FinancialAccount
    from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")

    if body.financial_account_id is not None:
        # Tenant-scoped, always. An id from another tenant must not be storable
        # even though nothing downstream would resolve it — the same
        # existence-oracle discipline the GL boundaries use.
        exists = (
            db.query(FinancialAccount)
            .filter(
                FinancialAccount.id == body.financial_account_id,
                FinancialAccount.tenant_id == current_user.company_id,
            )
            .first()
        )
        if exists is None:
            raise HTTPException(400, "That bank account is not one of yours.")

    company.set_setting(PAYMENT_BANK_SETTINGS_KEY, body.financial_account_id)
    db.commit()
    return _payment_bank_payload(db, company)


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


@router.post("/runs/{run_id}/populate-from-feed")
def populate_from_feed(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Plaid B-3 — materialize statement lines FROM THE FEED for a linked
    account. POSTED-only (pending money isn't reconcilable money), not-
    removed, within [period_start, statement_date]. Idempotent per run via
    the bank_transaction_id back-ref. THE MATCHER IS UNTOUCHED — these rows
    flow through run-matching exactly as CSV rows do; CSV stays first-class
    for unlinked accounts."""
    from app.models.plaid import BankAccount, BankTransaction

    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.id == run_id,
        ReconciliationRun.tenant_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status not in ("importing", "matching"):
        raise HTTPException(409, f"Run is {run.status} — populate applies to open runs")

    linked = db.query(BankAccount).filter(
        BankAccount.financial_account_id == run.financial_account_id,
        BankAccount.tenant_id == current_user.company_id,
        BankAccount.is_active.is_(True),
    ).all()
    if not linked:
        raise HTTPException(
            409,
            "This platform account has no linked bank account — link one on "
            "the bank connection card, or upload a CSV.",
        )

    already = {
        r[0] for r in db.query(ReconciliationTransaction.bank_transaction_id)
        .filter(ReconciliationTransaction.reconciliation_run_id == run.id,
                ReconciliationTransaction.bank_transaction_id.isnot(None))
    }
    q = db.query(BankTransaction).filter(
        BankTransaction.tenant_id == current_user.company_id,
        BankTransaction.bank_account_id.in_([a.id for a in linked]),
        BankTransaction.is_pending.is_(False),   # POSTED-only
        BankTransaction.removed_at.is_(None),    # retractions honored
        BankTransaction.transaction_date <= run.statement_date,
    )
    if run.period_start:
        q = q.filter(BankTransaction.transaction_date >= run.period_start)
    feed_rows = q.order_by(BankTransaction.transaction_date).all()

    created = 0
    for i, bt in enumerate(feed_rows):
        if bt.id in already:
            continue
        db.add(ReconciliationTransaction(
            tenant_id=current_user.company_id,
            reconciliation_run_id=run.id,
            transaction_date=bt.transaction_date,
            description=bt.description,
            raw_description=bt.raw_description,
            amount=bt.amount,  # platform sign already — the one negation lives at ingest
            transaction_type="credit" if bt.amount and bt.amount > 0 else "debit",
            sort_order=i,
            bank_transaction_id=bt.id,
        ))
        created += 1
    run.total_statement_transactions = (run.total_statement_transactions or 0) + created
    run.status = "matching"
    db.commit()
    return {"populated": created, "skipped_existing": len(feed_rows) - created,
            "source": "bank_feed"}


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

    # S-4: the matching engine now lives in reconciliation_service. Pure
    # move — behavior (incl. the greedy consumption + non-idempotence) is
    # unchanged. The route owns the HTTP concerns (run load + 404) and the
    # transaction boundary (commit); the service owns the engine.
    result = reconciliation_service.run_matching(db, run, current_user.company_id)
    db.commit()
    return result


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
    adj_id = reconciliation_service.create_adjustment(
        db,
        run_id=run_id,
        company_id=current_user.company_id,
        created_by=current_user.id,
        adjustment_type=body.adjustment_type,
        description=body.description,
        amount=body.amount,
    )
    db.commit()
    return {"id": adj_id}


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
