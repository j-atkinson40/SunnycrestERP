"""Early payment discount service — eligibility, calculation, and application."""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceLine
from app.models.customer_payment import CustomerPayment
from app.models.user import User
from app.services.agents.period_lock import PeriodLockedError

logger = logging.getLogger(__name__)

# AR-0. The tenant's GL choices for accounting purposes, NESTED so the
# siblings this arc already knows it needs — bad_debt (8650 BAD DEBTS),
# finance_charge_income (9200 FINANCE CHARGE INCOME), and the AR arc's revenue
# accounts — land here instead of proliferating flat keys beside
# `early_payment_discount_gl_account_id`. That existing flat key is left alone:
# it works, and churning it buys nothing.
#
#   company.settings["accounting_gl"] = {"ar": "<TenantGLMapping.id>"}
#
# Key absent or None ⇒ NOT configured ⇒ the posting refuses. Same fail-closed
# rule as the reconciliation keyword map, resolved and validated at use.
ACCOUNTING_GL_SETTINGS_KEY = "accounting_gl"


def get_discount_settings(db: Session, tenant_id: str) -> dict:
    """Get tenant discount configuration."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company or not company.settings:
        return {"enabled": False}

    settings = company.settings if isinstance(company.settings, dict) else {}
    enabled = settings.get("early_payment_discount_enabled", False)

    return {
        "enabled": enabled,
        "percentage": float(settings.get("early_payment_discount_percentage", 2.0)),
        "cutoff_day": int(settings.get("early_payment_discount_cutoff_day", 15)),
        "gl_account_id": settings.get("early_payment_discount_gl_account_id"),
    }


def is_discount_eligible(
    db: Session,
    tenant_id: str,
    customer_id: str,
    payment_date: date,
    override_approved: bool = False,
) -> dict:
    """Check whether a payment qualifies for early payment discount."""
    settings = get_discount_settings(db, tenant_id)

    if not settings["enabled"]:
        return {"eligible": False, "reason": "discount_not_enabled"}

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {"eligible": False, "reason": "customer_not_found"}

    if not getattr(customer, "early_payment_discount_eligible", True):
        return {
            "eligible": False,
            "reason": "customer_excluded",
            "exclusion_reason": getattr(customer, "early_payment_discount_excluded_reason", None),
        }

    billing_profile = getattr(customer, "billing_profile", "cod")
    if billing_profile != "monthly_statement":
        return {"eligible": False, "reason": "not_monthly_statement"}

    cutoff_day = settings["cutoff_day"]
    payment_day = payment_date.day

    if payment_day <= cutoff_day:
        return {
            "eligible": True,
            "discount_type": "early_payment",
            "days_before_cutoff": cutoff_day - payment_day,
            "percentage": settings["percentage"],
            "cutoff_day": cutoff_day,
        }
    elif override_approved:
        return {
            "eligible": True,
            "discount_type": "manager_override",
            "days_after_cutoff": payment_day - cutoff_day,
            "percentage": settings["percentage"],
            "cutoff_day": cutoff_day,
        }
    else:
        return {
            "eligible": False,
            "reason": "after_cutoff",
            "cutoff_day": cutoff_day,
            "days_after_cutoff": payment_day - cutoff_day,
            "override_available": True,
            "percentage": settings["percentage"],
        }


def calculate_discount(
    db: Session,
    tenant_id: str,
    payment_amount: float,
    invoice_ids: list[str] | None = None,
) -> dict:
    """Calculate discount amount for a payment."""
    settings = get_discount_settings(db, tenant_id)
    if not settings["enabled"]:
        return {"discount_amount": 0, "discountable_amount": 0}

    percentage = Decimal(str(settings["percentage"]))

    # Get discountable amount from invoice lines
    if invoice_ids:
        discountable_total = (
            db.query(func.coalesce(func.sum(InvoiceLine.amount), 0))
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
            .filter(
                Invoice.id.in_(invoice_ids),
                Invoice.company_id == tenant_id,
                InvoiceLine.discountable.is_(True),
            )
            .scalar()
        ) or Decimal("0")
    else:
        discountable_total = Decimal(str(payment_amount))

    # Cap at payment amount
    payment_dec = Decimal(str(payment_amount))
    discountable_amount = min(Decimal(str(discountable_total)), payment_dec)

    discount_amount = (discountable_amount * percentage / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return {
        "payment_amount": float(payment_dec),
        "discountable_amount": float(discountable_amount),
        "discount_percentage": float(percentage),
        "discount_amount": float(discount_amount),
        "amount_after_discount": float(payment_dec - discount_amount),
        "gl_account_id": settings["gl_account_id"],
    }


def apply_discounted_payment(
    db: Session,
    payment_id: str,
    tenant_id: str,
    discount_data: dict,
    discount_type: str,
    user_id: str,
    override_by: str | None = None,
    override_reason: str | None = None,
) -> dict:
    """Apply discount to an existing payment and create the journal entry."""
    payment = db.query(CustomerPayment).filter(CustomerPayment.id == payment_id, CustomerPayment.company_id == tenant_id).first()
    if not payment:
        return {"error": "Payment not found"}

    # AR-0 PRE-FLIGHT. Resolve the accounts BEFORE touching the payment, so a
    # refusal leaves nothing half-done. The order used to be mutate → post →
    # commit-regardless, which is how a discount reached the customer's balance
    # with no entry behind it. Booking is the licence to apply.
    resolve_ar_account(db, tenant_id)
    if not discount_data.get("gl_account_id"):
        raise HTTPException(
            400,
            "No early-payment-discount GL account is configured, so this "
            "discount has nothing to debit. Set it in the discount settings, "
            "then apply the discount.",
        )

    # Update payment record
    payment.discount_applied = True
    payment.discount_amount = Decimal(str(discount_data["discount_amount"]))
    payment.discount_percentage = Decimal(str(discount_data["discount_percentage"]))
    payment.discount_type = discount_type
    if override_by:
        payment.discount_override_by = override_by
    if override_reason:
        payment.discount_override_reason = override_reason

    # Create journal entry for the discount
    je_id = _create_discount_journal_entry(
        db=db,
        tenant_id=tenant_id,
        payment=payment,
        discount_amount=discount_data["discount_amount"],
        gl_account_id=discount_data["gl_account_id"],
        user_id=user_id,
    )
    # Unconditional now: `_create_discount_journal_entry` either returns an id
    # or raises. The old `if je_id:` guarded against a None it could no longer
    # receive, and reading it as optional is what made a null id look routine.
    payment.discount_journal_entry_id = je_id

    db.commit()

    return {
        "payment_id": payment_id,
        "discount_applied": True,
        "discount_amount": discount_data["discount_amount"],
        "journal_entry_id": je_id,
    }


def _create_discount_journal_entry(
    db: Session,
    tenant_id: str,
    payment: CustomerPayment,
    discount_amount: float,
    gl_account_id: str | None,
    user_id: str,
) -> str:
    """Create the auto-posted JE for the discount. Returns the entry ID.

    AR-0: RAISES rather than returning None. Every former `None` return was a
    discount that applied to the customer's balance with nothing behind it —
    the caller committed regardless and answered 200 with
    `journal_entry_id: null`. Booking is the licence to clear here too.
    """
    if not gl_account_id:
        # Was: log a warning and return None, which the caller ignored.
        raise HTTPException(
            400,
            "No early-payment-discount GL account is configured, so this "
            "discount has nothing to debit. Set it in the discount settings, "
            "then apply the discount.",
        )

    from app.services import journal_entry_service
    from app.services.journal_entry_service import JournalLineSpec

    customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
    customer_name = customer.name if customer else "Unknown"

    # Raises a legible 400 when unconfigured / inactive / foreign / unknown.
    # No fallback: the old `ar_account_id or gl_account_id` put BOTH legs on
    # the discount account, which balances, posts, and records nothing.
    ar_account = resolve_ar_account(db, tenant_id)
    specs = [
        # Debit: Sales Discounts
        JournalLineSpec(
            gl_account_id=gl_account_id,
            description=f"Early payment discount {payment.discount_percentage}% — {customer_name}",
            debit_amount=Decimal(str(discount_amount)),
            credit_amount=Decimal("0"),
        ),
        # Credit: Accounts Receivable — denormalized from the validated
        # mapping, per JournalLineSpec's contract that the caller resolves.
        JournalLineSpec(
            gl_account_id=ar_account.id,
            gl_account_number=ar_account.account_number,
            gl_account_name=ar_account.account_name,
            description=f"Discount applied to {customer_name} balance",
            debit_amount=Decimal("0"),
            credit_amount=Decimal(str(discount_amount)),
        ),
    ]

    # NO try/except. AR-0 removes the broad `except Exception: logger.error(...);
    # return None` that used to wrap this whole body.
    #
    # It had to go in THIS commit, not a later sweep: the new AR guard raises,
    # and a guard a caller can swallow is not a guard on that path
    # (DECISIONS.md 2026-07-29). The swallow would have eaten the very refusal
    # AR-0 exists to add — and it was already eating an AttributeError on
    # `payment.discount_percentage` for any caller that did not pre-set that
    # unmapped attribute, which is how a whole posting path can fail silently
    # and look configured.
    #
    # The S-3 `except PeriodLockedError: raise` re-raise is gone with it,
    # redundant once nothing is caught. Its reasoning still holds and is why
    # nothing is caught: a locked period means the contra-revenue entry cannot
    # post, so the discount must fail LOUDLY rather than reduce AR with no
    # offsetting entry.
    entry = journal_entry_service.create_journal_entry(
        db,
        tenant_id=tenant_id,
        entry_id=str(uuid.uuid4()),
        entry_number=f"DISC-{payment.id[:8]}",
        entry_type="adjusting",
        status="posted",
        entry_date=payment.payment_date or date.today(),
        period_month=(payment.payment_date or date.today()).month,
        period_year=(payment.payment_date or date.today()).year,
        description=f"Early payment discount — {customer_name}",
        reference_number=getattr(payment, "reference_number", None),
        created_by=user_id,
        posted_by=user_id,
        posted_at=datetime.now(timezone.utc),
        lines=specs,
    )

    return entry.id


def resolve_ar_account(db: Session, tenant_id: str):
    """The tenant's AR control account, or a legible 400. NEVER a guess.

    REPLACES `_find_ar_account` (AR-0), which matched
    ``platform_category ILIKE '%ar%'`` — a substring match against a free-text
    column, ``.first()``, no ORDER BY, wrapped in a bare
    ``except Exception: return None``. Two failures came out of six lines: it
    returned NOTHING when an AR account plainly existed, and it could return
    the WRONG account when an unrelated category happened to contain the
    letters "a" and "r" in sequence (warranty, clearing, salaries, arrears).

    PRODUCTION EVIDENCE (read-only, 2026-08-05): sunnycrest's 224 active
    mappings use nine categories — other, expense, current_liability,
    current_asset, fixed_asset, cogs, tax_expense, other_income, equity. NOT
    ONE contains "ar", so the old resolver returned None on every call, and the
    caller's `ar_account_id or gl_account_id` fallback was the ONLY path.
    Meanwhile `1200 ACCOUNTS RECEIVABLE-TRADE` sits on that chart categorised
    `current_asset`. The resolver was never looking at the account; it was
    interrogating a coarse import-time classification and hoping.

    `platform_category` cannot be repaired into a signal, either — on the same
    chart every revenue account is categorised `cogs`. RE-DERIVED ON PRODUCTION
    2026-08-19 (INV-1 A-1) and it is worse than this docstring said: not two
    accounts but THIRTEEN, the entire 5xxx block, including `5000 REVENUE`
    itself — 5000 · 5010 PRECAST SALES · 5012 REDI-ROCK SALES · 5014 ROSETTA
    SALES · 5020 PRECAST-RESALE · 5110 FUNERAL SALES · 5120 FUNERAL-RESALE ·
    5150/5160 REFUNDS-RETURNS · 5165 FUNERAL REBATES · 5170 DAMAGE OR DEFECTIVE
    RESALE · 5210 FREIGHT · 5410 DISCOUNTS ALLOWED-CASH. The original two were
    the ones someone happened to look at. So the answer is an EXPLICIT
    configured account, per
    the keyword-map precedent: a tenant's GL choice for a purpose lives in
    settings as a `TenantGLMapping.id`, resolved and validated AT USE through
    `require_gl_account` — the same single definition of "usable GL account"
    L-2.2 consolidated to. No third check.
    """
    from app.models.company import Company
    from app.services.reconciliation_gl import require_gl_account

    company = db.query(Company).filter(Company.id == tenant_id).first()
    settings = (company.settings if company else None) or {}
    accounting_gl = settings.get(ACCOUNTING_GL_SETTINGS_KEY) or {}
    ar_id = accounting_gl.get("ar") if isinstance(accounting_gl, dict) else None

    if not ar_id:
        # Fail closed with the CONFIGURATION action named. The old code
        # returned None here and the caller quietly booked both legs to the
        # discount account.
        raise HTTPException(
            400,
            "No accounts-receivable GL account is configured, so this discount "
            "has nothing to credit. Set it in the accounting GL settings, then "
            "apply the discount.",
        )
    # Raises its own legible 400 for inactive / foreign-tenant / nonexistent,
    # with the existence-oracle discipline L-2.1b established.
    return require_gl_account(db, tenant_id, ar_id)


def calculate_statement_discount(
    db: Session,
    tenant_id: str,
    customer_id: str,
    closing_balance: float,
    invoice_ids: list[str] | None = None,
) -> dict | None:
    """Pre-calculate discount for statement display."""
    settings = get_discount_settings(db, tenant_id)
    if not settings["enabled"]:
        return None

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer or not getattr(customer, "early_payment_discount_eligible", True):
        return None

    if getattr(customer, "billing_profile", "cod") != "monthly_statement":
        return None

    discount_data = calculate_discount(db, tenant_id, closing_balance, invoice_ids)

    # Calculate cutoff date (cutoff_day of next month from statement)
    today = date.today()
    cutoff_month = today.month + 1 if today.month < 12 else 1
    cutoff_year = today.year if today.month < 12 else today.year + 1
    cutoff_date = date(cutoff_year, cutoff_month, settings["cutoff_day"])

    return {
        "discount_amount": discount_data["discount_amount"],
        "discounted_total": closing_balance - discount_data["discount_amount"],
        "discount_percentage": settings["percentage"],
        "cutoff_date": cutoff_date.isoformat(),
        "standard_balance": closing_balance,
    }
