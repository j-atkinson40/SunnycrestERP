"""Early payment discount service — eligibility, calculation, and application."""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceLine
from app.models.customer_payment import CustomerPayment
from app.models.user import User
from app.services.agents.period_lock import PeriodLockedError

logger = logging.getLogger(__name__)


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
    if je_id:
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
) -> str | None:
    """Create the auto-posted JE for the discount. Returns entry ID."""
    if not gl_account_id:
        logger.warning(f"No discount GL account configured for tenant {tenant_id}")
        return None

    try:
        from app.services import journal_entry_service
        from app.services.journal_entry_service import JournalLineSpec

        customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
        customer_name = customer.name if customer else "Unknown"

        ar_account_id = _find_ar_account(db, tenant_id)
        specs = [
            # Debit: Sales Discounts
            JournalLineSpec(
                gl_account_id=gl_account_id,
                description=f"Early payment discount {payment.discount_percentage}% — {customer_name}",
                debit_amount=Decimal(str(discount_amount)),
                credit_amount=Decimal("0"),
            ),
            # Credit: Accounts Receivable (find AR account; fallback)
            JournalLineSpec(
                gl_account_id=ar_account_id or gl_account_id,
                description=f"Discount applied to {customer_name} balance",
                debit_amount=Decimal("0"),
                credit_amount=Decimal(str(discount_amount)),
            ),
        ]

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
    except PeriodLockedError:
        # Do NOT swallow our own S-3 period-lock guard. This path is
        # REACHABLE today: apply_discounted_payment runs on an ALREADY
        # EXISTING payment (a separate /discount action), so the period can
        # lock (month-end close) AFTER the payment was created but BEFORE
        # the discount is applied. A locked period means the contra-revenue
        # entry can't be posted — so the discount must fail LOUDLY (409),
        # not apply silently with no JE (AR reduced, no offsetting entry =
        # books out of balance, the exact failure this arc exists to
        # prevent). The broad swallow below stays an S-6 sweep item; this
        # narrows only the case where our new guard would be eaten.
        raise
    except Exception as e:
        logger.error(f"Failed to create discount JE: {e}")
        return None


def _find_ar_account(db: Session, tenant_id: str) -> str | None:
    """Find the AR GL account for this tenant."""
    try:
        # Health Triage P2: app.models.gl_mapping never existed → AR GL lookup
        # silently fell through. TenantGLMapping lives in
        # app.models.accounting_analysis (tenant_id/platform_category, verified).
        from app.models.accounting_analysis import TenantGLMapping

        ar = (
            db.query(TenantGLMapping)
            .filter(
                TenantGLMapping.tenant_id == tenant_id,
                TenantGLMapping.platform_category.ilike("%ar%"),
            )
            .first()
        )
        return ar.id if ar else None
    except Exception:
        return None


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
