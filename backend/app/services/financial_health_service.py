"""Financial health score service — daily A-F grading across 5 dimensions."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.cross_system_intelligence import FinancialHealthScore
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "ar_health": Decimal("0.25"),
    "ap_discipline": Decimal("0.20"),
    "cash_position": Decimal("0.20"),
    "operational_integrity": Decimal("0.20"),
    "growth_trajectory": Decimal("0.15"),
}


def score_to_grade(score: float) -> str:
    if score >= 93: return "A+"
    if score >= 90: return "A"
    if score >= 87: return "A-"
    if score >= 83: return "B+"
    if score >= 80: return "B"
    if score >= 77: return "B-"
    if score >= 73: return "C+"
    if score >= 70: return "C"
    if score >= 67: return "C-"
    if score >= 60: return "D"
    return "F"


def _calculate_ar_health(db: Session, tenant_id: str) -> tuple[float, list]:
    """AR health dimension: 0-100."""
    factors = []
    score = 100.0

    # Count overdue invoices
    overdue_count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == tenant_id, Invoice.status == "overdue")
        .scalar() or 0
    )
    total_open = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == tenant_id, Invoice.status.in_(["posted", "sent", "partial", "overdue"]))
        .scalar() or 0
    )

    if overdue_count > 5:
        score -= 25
        factors.append({"factor": "many_overdue_invoices", "impact": -25})
    elif overdue_count > 2:
        score -= 10
        factors.append({"factor": "some_overdue_invoices", "impact": -10})
    elif overdue_count == 0 and total_open > 0:
        score = min(score + 5, 100)
        factors.append({"factor": "no_overdue_invoices", "impact": 5})

    return max(0, min(100, score)), factors


def _calculate_ap_discipline(db: Session, tenant_id: str) -> tuple[float, list]:
    """AP discipline dimension: 0-100."""
    factors = []
    score = 100.0

    # Check for overdue vendor bills
    try:
        from app.models.vendor_bill import VendorBill
        overdue_bills = (
            db.query(func.count(VendorBill.id))
            .filter(VendorBill.tenant_id == tenant_id, VendorBill.status == "overdue")
            .scalar() or 0
        )
        if overdue_bills > 0:
            deduction = min(40, overdue_bills * 8)
            score -= deduction
            factors.append({"factor": "overdue_vendor_bills", "impact": -deduction})
    except Exception:
        pass  # Table may not exist yet

    return max(0, min(100, score)), factors


def _calculate_cash_position(db: Session, tenant_id: str) -> tuple[float, list]:
    """Cash position dimension: 0-100.

    SESSION-1 CASH WIRE: this component now reads the REAL position —
    live depository balances from the bank feed (credit excluded)
    against AP committed in the next 30 days. Before this it scored the
    mere EXISTENCE of FinancialAccount rows (the old void). Without a
    bank feed it stays a stated-neutral 70 with the reason in factors —
    never a number it can't stand behind.
    """
    factors = []
    score = 70.0

    try:
        from datetime import date, timedelta

        from app.models.plaid import BankAccount, PlaidItem

        rows = (
            db.query(BankAccount)
            .join(PlaidItem, PlaidItem.id == BankAccount.plaid_item_id)
            .filter(BankAccount.tenant_id == tenant_id,
                    BankAccount.is_active.is_(True),
                    PlaidItem.is_active.is_(True),
                    BankAccount.account_type == "depository",
                    BankAccount.current_balance.isnot(None))
            .all()
        )
        if not rows:
            factors.append({"factor": "no_bank_feed",
                            "note": "neutral score — connect a bank for a real cash read"})
            return score, factors

        cash_on_hand = float(sum(float(a.current_balance) for a in rows))

        from app.models.vendor_bill import VendorBill
        horizon = date.today() + timedelta(days=30)
        ap_30d = float(
            db.query(func.coalesce(func.sum(VendorBill.total - VendorBill.amount_paid), 0))
            .filter(VendorBill.company_id == tenant_id,
                    VendorBill.status.in_(["pending", "approved", "partial"]),
                    func.date(VendorBill.due_date) <= horizon)
            .scalar() or 0
        )

        if ap_30d <= 0:
            score = 90.0 if cash_on_hand > 0 else 60.0
            factors.append({"factor": "cash_on_hand", "value": round(cash_on_hand, 2),
                            "note": "no AP due in 30 days"})
        else:
            ratio = cash_on_hand / ap_30d
            if ratio >= 2:
                score = 95.0
            elif ratio >= 1:
                score = 85.0
            elif ratio >= 0.5:
                score = 70.0
            else:
                score = 50.0
            factors.append({"factor": "cash_vs_ap_30d",
                            "cash_on_hand": round(cash_on_hand, 2),
                            "ap_due_30d": round(ap_30d, 2),
                            "ratio": round(ratio, 2)})
    except Exception:
        pass

    return max(0, min(100, score)), factors


def _calculate_operational_integrity(db: Session, tenant_id: str) -> tuple[float, list]:
    """Operational integrity dimension: 0-100."""
    factors = []
    score = 85.0  # Start optimistic

    try:
        from app.models.report_intelligence import AuditPreflightResult
        latest = (
            db.query(AuditPreflightResult)
            .filter(AuditPreflightResult.tenant_id == tenant_id)
            .order_by(desc(AuditPreflightResult.run_at))
            .first()
        )
        if latest:
            if latest.status == "blocked":
                score -= 25
                factors.append({"factor": "audit_health_critical", "impact": -25})
            elif latest.status == "warnings":
                score -= 10
                factors.append({"factor": "audit_health_warnings", "impact": -10})
            elif latest.status == "passed":
                score += 10
                factors.append({"factor": "audit_health_clean", "impact": 10})
    except Exception:
        pass

    return max(0, min(100, score)), factors


def _calculate_growth_trajectory(db: Session, tenant_id: str) -> tuple[float, list]:
    """Growth trajectory dimension: 0-100. Starts at 70 (neutral)."""
    factors = []
    score = 70.0

    # Count recent invoices vs prior period
    now = date.today()
    thirty_ago = now - timedelta(days=30)
    sixty_ago = now - timedelta(days=60)

    recent = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == tenant_id, Invoice.invoice_date >= thirty_ago)
        .scalar() or 0
    )
    prior = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == tenant_id, Invoice.invoice_date >= sixty_ago, Invoice.invoice_date < thirty_ago)
        .scalar() or 0
    )

    if prior > 0:
        growth = (recent - prior) / prior
        if growth > 0.10:
            score += 20
            factors.append({"factor": "strong_activity_growth", "impact": 20})
        elif growth > 0:
            score += 10
            factors.append({"factor": "moderate_activity_growth", "impact": 10})
        elif growth < -0.10:
            score -= 15
            factors.append({"factor": "activity_declining", "impact": -15})

    return max(0, min(100, score)), factors


def run_daily_score(db: Session, tenant_id: str, score_date: date | None = None) -> dict:
    """Calculate and store today's financial health score."""
    if not score_date:
        score_date = date.today()

    # Calculate all dimensions
    ar_score, ar_factors = _calculate_ar_health(db, tenant_id)
    ap_score, ap_factors = _calculate_ap_discipline(db, tenant_id)
    cash_score, cash_factors = _calculate_cash_position(db, tenant_id)
    ops_score, ops_factors = _calculate_operational_integrity(db, tenant_id)
    growth_score, growth_factors = _calculate_growth_trajectory(db, tenant_id)

    # Weighted overall
    w = DEFAULT_WEIGHTS
    overall = float(
        Decimal(str(ar_score)) * w["ar_health"]
        + Decimal(str(ap_score)) * w["ap_discipline"]
        + Decimal(str(cash_score)) * w["cash_position"]
        + Decimal(str(ops_score)) * w["operational_integrity"]
        + Decimal(str(growth_score)) * w["growth_trajectory"]
    )
    overall = round(overall, 1)
    grade = score_to_grade(overall)

    # Collect all factors
    all_factors = ar_factors + ap_factors + cash_factors + ops_factors + growth_factors
    # Session-1: informational factors (the cash numbers) carry no impact
    # delta — they inform, they don't rank.
    positive = sorted([f for f in all_factors if f.get("impact", 0) > 0], key=lambda x: -x["impact"])[:3]
    negative = sorted([f for f in all_factors if f.get("impact", 0) < 0], key=lambda x: x["impact"])[:3]

    # Prior score
    prior = (
        db.query(FinancialHealthScore)
        .filter(FinancialHealthScore.tenant_id == tenant_id, FinancialHealthScore.score_date == score_date - timedelta(days=1))
        .first()
    )
    prior_score = float(prior.overall_score) if prior else None
    change = round(overall - prior_score, 1) if prior_score is not None else None

    # 7-day trend
    week_scores = (
        db.query(FinancialHealthScore.overall_score)
        .filter(FinancialHealthScore.tenant_id == tenant_id, FinancialHealthScore.score_date >= score_date - timedelta(days=7))
        .order_by(FinancialHealthScore.score_date)
        .all()
    )
    trend_7 = None
    if len(week_scores) >= 3:
        vals = [float(s.overall_score) for s in week_scores]
        trend_7 = round((vals[-1] - vals[0]) / len(vals), 1)

    # Upsert
    existing = (
        db.query(FinancialHealthScore)
        .filter(FinancialHealthScore.tenant_id == tenant_id, FinancialHealthScore.score_date == score_date)
        .first()
    )
    if existing:
        record = existing
    else:
        record = FinancialHealthScore(id=str(uuid.uuid4()), tenant_id=tenant_id, score_date=score_date)
        db.add(record)

    record.overall_grade = grade
    record.overall_score = Decimal(str(overall))
    record.ar_health_score = Decimal(str(ar_score))
    record.ar_health_grade = score_to_grade(ar_score)
    record.ap_discipline_score = Decimal(str(ap_score))
    record.ap_discipline_grade = score_to_grade(ap_score)
    record.cash_position_score = Decimal(str(cash_score))
    record.cash_position_grade = score_to_grade(cash_score)
    record.operational_integrity_score = Decimal(str(ops_score))
    record.operational_integrity_grade = score_to_grade(ops_score)
    record.growth_trajectory_score = Decimal(str(growth_score))
    record.growth_trajectory_grade = score_to_grade(growth_score)
    record.top_positive_factors = positive
    record.top_negative_factors = negative
    record.prior_score = Decimal(str(prior_score)) if prior_score else None
    record.score_change = Decimal(str(change)) if change is not None else None
    record.trend_7_day = Decimal(str(trend_7)) if trend_7 is not None else None
    record.weights = {k: float(v) for k, v in DEFAULT_WEIGHTS.items()}
    db.commit()

    return {
        "grade": grade,
        "score": overall,
        "dimensions": {
            "ar_health": {"score": ar_score, "grade": score_to_grade(ar_score)},
            "ap_discipline": {"score": ap_score, "grade": score_to_grade(ap_score)},
            "cash_position": {"score": cash_score, "grade": score_to_grade(cash_score)},
            "operational_integrity": {"score": ops_score, "grade": score_to_grade(ops_score)},
            "growth_trajectory": {"score": growth_score, "grade": score_to_grade(growth_score)},
        },
        "change": change,
        "trend_7_day": trend_7,
        "positive_factors": positive,
        "negative_factors": negative,
    }


def get_health_score(db: Session, tenant_id: str) -> dict | None:
    """Get today's health score, calculating if needed."""
    today = date.today()
    record = (
        db.query(FinancialHealthScore)
        .filter(FinancialHealthScore.tenant_id == tenant_id, FinancialHealthScore.score_date == today)
        .first()
    )
    if not record:
        return run_daily_score(db, tenant_id, today)

    return {
        "grade": record.overall_grade,
        "score": float(record.overall_score),
        "dimensions": {
            "ar_health": {"score": float(record.ar_health_score or 0), "grade": record.ar_health_grade or "N/A"},
            "ap_discipline": {"score": float(record.ap_discipline_score or 0), "grade": record.ap_discipline_grade or "N/A"},
            "cash_position": {"score": float(record.cash_position_score or 0), "grade": record.cash_position_grade or "N/A"},
            "operational_integrity": {"score": float(record.operational_integrity_score or 0), "grade": record.operational_integrity_grade or "N/A"},
            "growth_trajectory": {"score": float(record.growth_trajectory_score or 0), "grade": record.growth_trajectory_grade or "N/A"},
        },
        "change": float(record.score_change) if record.score_change else None,
        "trend_7_day": float(record.trend_7_day) if record.trend_7_day else None,
        "positive_factors": record.top_positive_factors or [],
        "negative_factors": record.top_negative_factors or [],
    }


def get_score_history(db: Session, tenant_id: str, days: int = 30) -> list[dict]:
    """Get score history for chart display."""
    cutoff = date.today() - timedelta(days=days)
    records = (
        db.query(FinancialHealthScore)
        .filter(FinancialHealthScore.tenant_id == tenant_id, FinancialHealthScore.score_date >= cutoff)
        .order_by(FinancialHealthScore.score_date)
        .all()
    )
    return [
        {
            "date": str(r.score_date),
            "score": float(r.overall_score),
            "grade": r.overall_grade,
            "top_factor": r.top_negative_factors[0]["factor"] if r.top_negative_factors else None,
        }
        for r in records
    ]
