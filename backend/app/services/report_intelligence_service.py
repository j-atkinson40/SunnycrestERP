"""Report intelligence — snapshots, commentary, trends, forecasts, preflight."""

import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.report_intelligence import (
    AuditPreflightResult,
    ReportCommentary,
    ReportForecast,
    ReportSnapshot,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PART 2 — Trend Engine: Snapshots
# ---------------------------------------------------------------------------


def extract_key_metrics(report_type: str, report_data: dict) -> dict | None:
    """Extract key metrics from report data for snapshot storage."""
    if report_type == "income_statement":
        return {
            "total_revenue": report_data.get("total_revenue", 0),
            "total_cogs": report_data.get("total_cogs", 0),
            "gross_profit": report_data.get("gross_profit", 0),
            "gross_margin_percent": report_data.get("gross_margin_percent", 0),
            "total_expenses": report_data.get("total_expenses", 0),
            "net_income": report_data.get("net_income", 0),
        }
    elif report_type == "balance_sheet":
        assets = report_data.get("assets", {})
        liabilities = report_data.get("liabilities", {})
        equity = report_data.get("equity", {})
        current_assets = assets.get("total_current", 0)
        current_liabilities = liabilities.get("total_current", 1)
        return {
            "total_assets": assets.get("total", 0),
            "total_liabilities": liabilities.get("total", 0),
            "total_equity": equity.get("total", 0),
            "current_ratio": round(current_assets / max(current_liabilities, 1), 2),
        }
    elif report_type == "ar_aging":
        totals = report_data.get("totals", {})
        total = totals.get("total", 1)
        return {
            "total_outstanding": total,
            "current_amount": totals.get("current", 0),
            "over_30_amount": totals.get("days_1_30", 0),
            "over_60_amount": totals.get("days_31_60", 0),
            "over_90_amount": totals.get("days_over_90", 0),
            "customer_count": report_data.get("customer_count", 0),
        }
    elif report_type == "ap_aging":
        totals = report_data.get("totals", {})
        return {
            "total_outstanding": totals.get("total", 0),
            "current_amount": totals.get("current", 0),
            "over_30_amount": totals.get("days_1_30", 0),
            "over_60_amount": totals.get("days_31_60", 0),
            "over_90_amount": totals.get("days_over_90", 0),
        }
    return None


def save_snapshot(db: Session, tenant_id: str, report_type: str, period_start: date, period_end: date, key_metrics: dict) -> None:
    """Save or update a report snapshot. Fire-and-forget — never throws."""
    try:
        snapshot_date = period_start
        existing = (
            db.query(ReportSnapshot)
            .filter(
                ReportSnapshot.tenant_id == tenant_id,
                ReportSnapshot.report_type == report_type,
                ReportSnapshot.snapshot_date == snapshot_date,
            )
            .first()
        )
        if existing:
            existing.key_metrics = key_metrics
            existing.period_end = period_end
        else:
            db.add(ReportSnapshot(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                report_type=report_type,
                snapshot_date=snapshot_date,
                period_start=period_start,
                period_end=period_end,
                key_metrics=key_metrics,
            ))
        db.commit()
    except Exception:
        logger.exception("Failed to save report snapshot")
        try:
            db.rollback()
        except Exception:
            pass


def get_trend_data(db: Session, tenant_id: str, report_type: str, periods: int = 6) -> list[dict]:
    """Get snapshot history for trend display / sparklines."""
    snapshots = (
        db.query(ReportSnapshot)
        .filter(ReportSnapshot.tenant_id == tenant_id, ReportSnapshot.report_type == report_type)
        .order_by(desc(ReportSnapshot.snapshot_date))
        .limit(periods)
        .all()
    )
    return [
        {
            "snapshot_date": str(s.snapshot_date),
            "period_start": str(s.period_start),
            "period_end": str(s.period_end),
            "key_metrics": s.key_metrics,
        }
        for s in reversed(snapshots)  # chronological order
    ]


# ---------------------------------------------------------------------------
# PART 3 — Commentary Service
# ---------------------------------------------------------------------------


def _compute_cache_key(report_type: str, period_start: date, period_end: date, key_metrics: dict) -> str:
    raw = f"{report_type}|{period_start}|{period_end}|{json.dumps(key_metrics, sort_keys=True, default=str)}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_commentary(db: Session, commentary_id: str, tenant_id: str) -> dict | None:
    """Get commentary by ID — used for polling.

    `tenant_id` is REQUIRED, not optional-with-default (RI-1). This filtered on
    id alone and the route never scoped it, so any authenticated user could read
    another company's executive_summary, key_findings and attention_items by id.
    A default would let a caller silently reacquire that.

    Returns None rather than raising on a foreign row: to a caller outside the
    tenant, a row that exists and a row that does not must be indistinguishable,
    or the 404 becomes an existence oracle.
    """
    c = (db.query(ReportCommentary)
         .filter(ReportCommentary.id == commentary_id,
                 ReportCommentary.tenant_id == tenant_id)
         .first())
    if not c:
        return None
    return {
        "id": c.id,
        "status": c.status,
        "executive_summary": c.executive_summary,
        "key_findings": c.key_findings,
        "trend_summary": c.trend_summary,
        "forecast_note": c.forecast_note,
        "attention_items": c.attention_items,
        "comparison_periods_used": c.comparison_periods_used,
        "generated_at": c.generated_at.isoformat() if c.generated_at else None,
    }


def start_commentary_generation(
    db: Session, tenant_id: str, report_type: str,
    period_start: date, period_end: date, key_metrics: dict,
    report_run_id: str | None = None,
) -> str:
    """Create pending commentary record and return ID for polling. Actual generation is async."""
    cache_key = _compute_cache_key(report_type, period_start, period_end, key_metrics)

    # Check cache
    cached = (
        db.query(ReportCommentary)
        .filter(
            ReportCommentary.tenant_id == tenant_id,
            ReportCommentary.cache_key == cache_key,
            ReportCommentary.status == "complete",
            ReportCommentary.created_at > datetime.now(timezone.utc) - timedelta(hours=24),
        )
        .first()
    )
    if cached:
        cached.status = "cached"
        db.commit()
        return cached.id

    # Create pending record
    commentary = ReportCommentary(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        report_run_id=report_run_id,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        status="generating",
        cache_key=cache_key,
    )
    db.add(commentary)
    db.commit()

    # TODO: Trigger async Claude API call here
    # For now, mark as complete with placeholder
    commentary.status = "complete"
    commentary.executive_summary = "Commentary generation requires Claude API integration. Run a report with sufficient historical data to see AI-generated analysis."
    commentary.key_findings = []
    commentary.generated_at = datetime.now(timezone.utc)
    commentary.comparison_periods_used = 0
    db.commit()

    return commentary.id


# ---------------------------------------------------------------------------
# PART 4 — Forecast Service
# ---------------------------------------------------------------------------


def generate_forecasts(db: Session, tenant_id: str) -> dict:
    """Generate 3-month forecasts for key metrics."""
    results = {}

    for forecast_type, report_type, metric_key in [
        ("revenue", "income_statement", "total_revenue"),
        ("net_income", "income_statement", "net_income"),
        ("ar_outstanding", "ar_aging", "total_outstanding"),
    ]:
        snapshots = (
            db.query(ReportSnapshot)
            .filter(ReportSnapshot.tenant_id == tenant_id, ReportSnapshot.report_type == report_type)
            .order_by(ReportSnapshot.snapshot_date)
            .all()
        )

        values = []
        for s in snapshots:
            v = s.key_metrics.get(metric_key)
            if v is not None:
                values.append({"date": s.snapshot_date, "value": float(v)})

        if len(values) < 3:
            results[forecast_type] = {"skipped": True, "reason": "insufficient_data", "data_points": len(values)}
            continue

        # Simple trend: average month-over-month change
        changes = []
        for i in range(1, len(values)):
            if values[i - 1]["value"] != 0:
                pct = (values[i]["value"] - values[i - 1]["value"]) / abs(values[i - 1]["value"])
                changes.append(pct)

        avg_change = sum(changes) / len(changes) if changes else 0
        last_value = values[-1]["value"]

        # Determine trend direction
        if avg_change > 0.02:
            direction = "up"
        elif avg_change < -0.02:
            direction = "down"
        else:
            direction = "flat"

        # Project 3 periods
        forecast_periods = []
        for n in range(1, 4):
            projected = last_value * ((1 + avg_change) ** n)
            confidence = min(0.90, 0.50 + (len(values) * 0.04))
            forecast_periods.append({
                "period_number": n,
                "forecast_value": round(projected, 2),
                "lower_bound": round(projected * 0.85, 2),
                "upper_bound": round(projected * 1.15, 2),
                "confidence": round(confidence, 3),
            })

        # Upsert
        today = date.today()
        existing = (
            db.query(ReportForecast)
            .filter(
                ReportForecast.tenant_id == tenant_id,
                ReportForecast.forecast_type == forecast_type,
                ReportForecast.generated_date == today,
            )
            .first()
        )
        if existing:
            existing.data_points = len(values)
            existing.current_value = Decimal(str(last_value))
            existing.forecast_periods = forecast_periods
            existing.trend_direction = direction
            existing.trend_rate_monthly = Decimal(str(round(avg_change * 100, 3)))
        else:
            db.add(ReportForecast(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                forecast_type=forecast_type,
                generated_date=today,
                data_points=len(values),
                current_value=Decimal(str(last_value)),
                forecast_periods=forecast_periods,
                trend_direction=direction,
                trend_rate_monthly=Decimal(str(round(avg_change * 100, 3))),
            ))

        db.commit()
        results[forecast_type] = {"generated": True, "data_points": len(values), "trend": direction}

    return results


def get_forecasts(db: Session, tenant_id: str, forecast_type: str | None = None) -> list[dict]:
    query = db.query(ReportForecast).filter(ReportForecast.tenant_id == tenant_id)
    if forecast_type:
        query = query.filter(ReportForecast.forecast_type == forecast_type)
    forecasts = query.order_by(desc(ReportForecast.generated_date)).limit(10).all()
    return [
        {
            "forecast_type": f.forecast_type,
            "generated_date": str(f.generated_date),
            "data_points": f.data_points,
            "current_value": float(f.current_value) if f.current_value else None,
            "forecast_periods": f.forecast_periods,
            "trend_direction": f.trend_direction,
            "trend_rate_monthly": float(f.trend_rate_monthly) if f.trend_rate_monthly else None,
            "milestone_projections": f.milestone_projections,
        }
        for f in forecasts
    ]


# ---------------------------------------------------------------------------
# PART 5 — Audit Pre-Flight Service
# ---------------------------------------------------------------------------


# ── audit pre-flight ────────────────────────────────────────────────────────
#
# WHAT THIS WAS, before LEDGER-1 A-2. Five checks that each appended
# unconditionally to `passed`, two lists that were never appended to anywhere in
# the function, and therefore a `status` that could only ever be "passed" —
# committed to a durable `AuditPreflightResult` row naming five satisfied
# checks. Not a guard that could not fail: a guard that did not exist, writing
# down that it had run. The `override_by` / `override_reason` / `override_at`
# columns show blocking was designed for; nothing could reach it.
#
# Two of the five are DELETED rather than implemented, because a check that
# cannot be honestly computed today should be absent rather than green:
#
#   * `reconciliation` ("All accounts reconciled through period") — the
#     reconciliation substrate exists (reconciliation_runs and friends), but
#     "reconciled THROUGH a period" needs a per-account statement-coverage
#     notion the schema does not carry. Asserting coverage from run rows would
#     restate the same fiction in SQL.
#   * `w9_compliance` ("All vendors over $600 have W-9 on file") — there is no
#     W-9 field on the vendor model. The check cannot read what it claims to
#     check. This is a real 1099 obligation and wants its own arc, not a line
#     that returns green because the column is missing.
#
# A deleted check is visibly absent from `passed_checks`. A stubbed one is
# indistinguishable from a satisfied one, which is how this survived.


def _check_trial_balance(db: Session, tenant_id: str, period_start, period_end):
    from app.services.financial_report_service import get_trial_balance

    tb = get_trial_balance(db, tenant_id, as_of=period_end)

    if not tb["has_postings"]:
        # An empty ledger reports balanced — 0 == 0 — which is why the old
        # string "Trial balance is balanced" was true and worthless. There is
        # nothing here to audit.
        return ("blocking",
                "No posted journal entries as of this date, so there is no trial "
                "balance to evidence. An audit package cannot be produced from an "
                "empty ledger.",
                {"as_of": tb["as_of"], "account_count": 0})

    if not tb["balanced"]:
        return ("blocking",
                f"Trial balance is out of balance by {tb['difference']}.",
                {"total_debits": str(tb["total_debits"]),
                 "total_credits": str(tb["total_credits"]),
                 "difference": str(tb["difference"])})

    return ("passed",
            f"Trial balance is balanced across {tb['account_count']} accounts "
            f"({tb['total_debits']} debits = {tb['total_credits']} credits).",
            {"account_count": tb["account_count"]})


def _check_invoice_integrity(db: Session, tenant_id: str, period_start, period_end):
    """Invoices edited after money was applied to them.

    `customer_payment_applications` carries no timestamp of its own, so the
    comparison is against `CustomerPayment.created_at` — when the payment row
    was written. Stated because it is a real limitation: an application made
    later against an older payment reads as earlier than it was, so this can
    UNDER-report. It cannot over-report.
    """
    from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
    from app.models.invoice import Invoice

    q = (
        db.query(Invoice.number, Invoice.modified_at, CustomerPayment.created_at)
        .join(CustomerPaymentApplication,
              CustomerPaymentApplication.invoice_id == Invoice.id)
        .join(CustomerPayment,
              CustomerPayment.id == CustomerPaymentApplication.payment_id)
        .filter(Invoice.company_id == tenant_id,
                Invoice.modified_at.isnot(None),
                Invoice.modified_at > CustomerPayment.created_at)
    )
    if period_start:
        q = q.filter(Invoice.invoice_date >= period_start)
    if period_end:
        q = q.filter(Invoice.invoice_date <= period_end)

    offenders = q.limit(51).all()
    if not offenders:
        return ("passed", "No invoices were modified after a payment was applied.", None)

    shown = [o.number for o in offenders[:50]]
    return ("blocking",
            f"{len(shown)}{'+' if len(offenders) > 50 else ''} invoice(s) were "
            "modified after a payment was applied to them.",
            {"invoice_numbers": shown})


def _check_ar_collectibility(db: Session, tenant_id: str, period_start, period_end):
    """More than 5% of AR sitting over 90 days is a warning, not a block.

    Old AR is a judgement about collectibility, not a defect in the books, so it
    must not stop an audit package the way an unbalanced ledger does.
    """
    from app.services.financial_report_service import get_ar_aging_report

    aging = get_ar_aging_report(db, tenant_id, as_of=period_end)
    totals = aging["totals"]
    total = Decimal(str(totals["total"] or 0))
    over_90 = Decimal(str(totals["days_over_90"] or 0))

    if total <= 0:
        return ("passed", "No outstanding AR.", None)

    pct = (over_90 / total * 100).quantize(Decimal("0.1"))
    if pct > Decimal("5.0"):
        return ("warning",
                f"{pct}% of AR is over 90 days ({over_90} of {total}), above the "
                "5% threshold.",
                {"over_90": str(over_90), "total": str(total), "percent": str(pct)})
    return ("passed", f"{pct}% of AR is over 90 days, within the 5% threshold.", None)


_PREFLIGHT_CHECKS = (
    ("trial_balance", _check_trial_balance),
    ("invoice_integrity", _check_invoice_integrity),
    ("ar_collectibility", _check_ar_collectibility),
)


def run_preflight(db: Session, tenant_id: str, audit_package_id: str | None = None,
                  period_start: date | None = None, period_end: date | None = None) -> dict:
    """Run audit pre-flight checks and return results.

    A check that RAISES becomes blocking, never passed. The failure mode this
    replaces was a safe state produced by absence; an exception swallowed into
    green would reintroduce it in a form that is harder to see.
    """
    blocking: list[dict] = []
    warnings: list[dict] = []
    passed: list[dict] = []
    buckets = {"blocking": blocking, "warning": warnings, "passed": passed}

    for code, check in _PREFLIGHT_CHECKS:
        try:
            severity, message, detail = check(db, tenant_id, period_start, period_end)
        except Exception as exc:  # noqa: BLE001 — deliberate: fail closed, and say so
            logger.exception("Pre-flight check %s failed for tenant %s", code, tenant_id)
            blocking.append({"code": code,
                             "message": f"Check could not be completed: {exc}",
                             "detail": {"error": type(exc).__name__}})
            continue
        entry = {"code": code, "message": message}
        if detail is not None:
            entry["detail"] = detail
        buckets[severity].append(entry)

    if blocking:
        status = "blocked"
    elif warnings:
        status = "warnings"
    else:
        status = "passed"

    result = AuditPreflightResult(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        audit_package_id=audit_package_id,
        status=status,
        blocking_issues=blocking,
        warning_issues=warnings,
        passed_checks=passed,
    )
    db.add(result)
    db.commit()

    return {
        "id": result.id,
        "status": status,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "passed_count": len(passed),
        "blocking_issues": blocking,
        "warning_issues": warnings,
        "passed_checks": passed,
    }


def get_preflight_result(db: Session, result_id: str, tenant_id: str) -> dict | None:
    """See `get_commentary` on why `tenant_id` is required and why a foreign row
    returns None rather than raising."""
    r = (db.query(AuditPreflightResult)
         .filter(AuditPreflightResult.id == result_id,
                 AuditPreflightResult.tenant_id == tenant_id)
         .first())
    if not r:
        return None
    return {
        "id": r.id,
        "status": r.status,
        "blocking_issues": r.blocking_issues,
        "warning_issues": r.warning_issues,
        "passed_checks": r.passed_checks,
        "override_by": r.override_by,
        "override_reason": r.override_reason,
        "run_at": r.run_at.isoformat() if r.run_at else None,
    }


def override_preflight(db: Session, result_id: str, user_id: str, reason: str,
                       tenant_id: str) -> bool:
    """Override a BLOCKED pre-flight. `tenant_id` required (RI-1) — this is a
    WRITE, and it was reachable cross-tenant by id.

    It was unreachable in practice only by accident: nothing could produce
    `blocked`, because `run_preflight` initialises `blocking` and `warnings`
    empty and never appends to either. A-2 makes blocking real, which arms this.
    Scoped before that lands rather than after.
    """
    r = (db.query(AuditPreflightResult)
         .filter(AuditPreflightResult.id == result_id,
                 AuditPreflightResult.tenant_id == tenant_id)
         .first())
    if not r or r.status != "blocked":
        return False
    r.override_by = user_id
    r.override_reason = reason
    r.override_at = datetime.now(timezone.utc)
    r.status = "passed"  # Allow generation after override
    db.commit()
    return True
