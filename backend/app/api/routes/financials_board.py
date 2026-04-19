"""Financials Board API — aggregated AR/AP data, briefing, cash flow, agent feed."""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.agent import AgentActivityLog, AgentAlert, AgentCollectionSequence
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.user import User
from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill

logger = logging.getLogger(__name__)
router = APIRouter()

BRIEFING_MODEL = "claude-haiku-4-5-20250514"

# Simple in-memory cache for briefings (per tenant, 30 min TTL)
_briefing_cache: dict[str, tuple[str, datetime]] = {}


# ---------------------------------------------------------------------------
# Board summary — daily briefing data
# ---------------------------------------------------------------------------


@router.get("/summary")
def get_board_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate key financials for the daily briefing zone."""
    tid = current_user.company_id
    today = date.today()
    week_end = today + timedelta(days=7)

    # AR outstanding
    ar_total = db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).filter(
        Invoice.company_id == tid, Invoice.status.in_(["sent", "open", "partial", "overdue"]),
    ).scalar() or 0

    # AR overdue count + total
    overdue_invoices = db.query(Invoice).filter(
        Invoice.company_id == tid, Invoice.status.in_(["sent", "open", "partial", "overdue"]),
        Invoice.due_date < today,
    ).all()
    overdue_count = len(overdue_invoices)
    overdue_total = sum(float(i.total - (i.amount_paid or 0)) for i in overdue_invoices)

    # AP due this week
    try:
        ap_week = db.query(func.coalesce(func.sum(VendorBill.total - VendorBill.amount_paid), 0)).filter(
            VendorBill.company_id == tid, VendorBill.status.in_(["pending", "approved", "partial"]),
            func.date(VendorBill.due_date) <= week_end,
        ).scalar() or 0
        ap_due_today = db.query(func.coalesce(func.sum(VendorBill.total - VendorBill.amount_paid), 0)).filter(
            VendorBill.company_id == tid, VendorBill.status.in_(["pending", "approved", "partial"]),
            func.date(VendorBill.due_date) <= today,
        ).scalar() or 0
    except Exception:
        ap_week = 0
        ap_due_today = 0

    # Payments received today
    try:
        from app.models.payment import Payment
        payments_today = db.query(Payment).filter(
            Payment.company_id == tid,
            func.date(Payment.payment_date) == today,
        ).all()
        payments_today_total = sum(float(p.amount) for p in payments_today)
        payments_today_count = len(payments_today)
    except Exception:
        payments_today_total = 0
        payments_today_count = 0

    # Alert counts
    alert_counts = {}
    for sev in ["action_required", "warning", "info"]:
        alert_counts[sev] = db.query(func.count(AgentAlert.id)).filter(
            AgentAlert.tenant_id == tid, AgentAlert.severity == sev, AgentAlert.resolved == False,
        ).scalar() or 0

    return {
        "ar_outstanding": float(ar_total),
        "ar_overdue_count": overdue_count,
        "ar_overdue_total": overdue_total,
        "ap_due_this_week": float(ap_week),
        "ap_due_today": float(ap_due_today),
        "payments_today_total": payments_today_total,
        "payments_today_count": payments_today_count,
        "alert_counts": alert_counts,
    }


# ---------------------------------------------------------------------------
# AI Briefing — cached 30 min
# ---------------------------------------------------------------------------


@router.get("/briefing")
def get_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate or return cached Claude financial briefing."""
    tid = current_user.company_id
    now = datetime.now(timezone.utc)

    # Check cache
    if tid in _briefing_cache:
        text, cached_at = _briefing_cache[tid]
        if (now - cached_at).total_seconds() < 1800:
            return {"briefing": text, "cached": True, "generated_at": cached_at.isoformat()}

    # Build context
    summary = get_board_summary.__wrapped__(current_user=current_user, db=db) if hasattr(get_board_summary, '__wrapped__') else None
    if summary is None:
        # Fallback — call the logic directly
        today = date.today()
        overdue_invoices = db.query(Invoice).filter(
            Invoice.company_id == tid, Invoice.status.in_(["sent", "open", "partial", "overdue"]),
            Invoice.due_date < today,
        ).all()
        summary = {
            "ar_overdue_count": len(overdue_invoices),
            "ar_overdue_total": sum(float(i.total - (i.amount_paid or 0)) for i in overdue_invoices),
            "ap_due_this_week": 0, "payments_today_total": 0, "payments_today_count": 0,
        }

    # Get action_required alerts
    action_alerts = db.query(AgentAlert).filter(
        AgentAlert.tenant_id == tid, AgentAlert.severity == "action_required", AgentAlert.resolved == False,
    ).limit(5).all()
    alerts_text = "; ".join(a.title for a in action_alerts) if action_alerts else "No urgent alerts"

    # Get largest overdue customer
    largest_overdue = ""
    overdue_by_customer = db.query(
        Customer.name, func.sum(Invoice.total - Invoice.amount_paid).label("owed"),
    ).join(Invoice, Invoice.customer_id == Customer.id).filter(
        Invoice.company_id == tid, Invoice.status.in_(["sent", "open", "partial", "overdue"]),
        Invoice.due_date < date.today(),
    ).group_by(Customer.name).order_by(func.sum(Invoice.total - Invoice.amount_paid).desc()).first()
    if overdue_by_customer:
        largest_overdue = f"{overdue_by_customer[0]} owes ${float(overdue_by_customer[1]):,.2f} overdue"

    try:
        # Phase 2c-2 migration — briefing.financial_board (plain-text response,
        # force_json=false). The managed prompt carries the system prompt
        # verbatim; we supply each summary metric as a named variable so the
        # prompt's Jinja template can render the context section consistently.
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="briefing.financial_board",
            variables={
                "ar_overdue_count": summary["ar_overdue_count"],
                "ar_overdue_total": f"{summary['ar_overdue_total']:,.2f}",
                "ap_due_this_week": f"{summary.get('ap_due_this_week', 0):,.2f}",
                "payments_today_total": f"{summary['payments_today_total']:,.2f}",
                "payments_today_count": summary["payments_today_count"],
                "alerts_text": alerts_text,
                "largest_overdue": largest_overdue or "none",
            },
            company_id=tid,
            caller_module="financials_board.get_briefing",
            caller_entity_type="user",
            caller_entity_id=current_user.id,
        )
        briefing_text = result.response_text if result.status == "success" else None
        if briefing_text is None and result.error_message:
            logger.error("Financial briefing failed: %s", result.error_message)
    except Exception as e:
        logger.error(f"Financial briefing generation failed: {e}")
        briefing_text = None

    if briefing_text:
        _briefing_cache[tid] = (briefing_text, now)

    return {
        "briefing": briefing_text,
        "cached": False,
        "generated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# AR Endpoints
# ---------------------------------------------------------------------------


@router.get("/ar/overdue")
def get_ar_overdue(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get overdue invoices with customer and collection info."""
    tid = current_user.company_id
    today = date.today()

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == tid,
            Invoice.status.in_(["sent", "open", "partial", "overdue"]),
            Invoice.due_date < today,
        )
        .order_by(Invoice.due_date.asc())
        .all()
    )

    # Get collection sequences for these invoices
    inv_ids = [i.id for i in invoices]
    sequences = {}
    if inv_ids:
        seqs = db.query(AgentCollectionSequence).filter(
            AgentCollectionSequence.invoice_id.in_(inv_ids),
            AgentCollectionSequence.completed == False,
        ).all()
        sequences = {s.invoice_id: s for s in seqs}

    results = []
    for inv in invoices:
        customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()
        days_overdue = (today - inv.due_date).days if inv.due_date else 0
        balance = float(inv.total - (inv.amount_paid or 0))
        seq = sequences.get(inv.id)

        results.append({
            "id": inv.id,
            "invoice_number": inv.number,
            "customer_id": inv.customer_id,
            "customer_name": customer.name if customer else "Unknown",
            "customer_type": getattr(customer, "customer_type", None),
            "original_amount": float(inv.total),
            "balance": balance,
            "due_date": str(inv.due_date),
            "days_overdue": days_overdue,
            "collection_sequence": {
                "id": seq.id,
                "step": seq.sequence_step,
                "last_sent": seq.last_sent_at.isoformat() if seq and seq.last_sent_at else None,
                "next_scheduled": seq.next_scheduled_at.isoformat() if seq and seq.next_scheduled_at else None,
                "paused": seq.paused,
            } if seq else None,
        })

    # Aging buckets
    buckets = {"current": 0, "days_1_30": 0, "days_31_60": 0, "days_61_90": 0, "over_90": 0}
    for r in results:
        d = r["days_overdue"]
        if d <= 0:
            buckets["current"] += r["balance"]
        elif d <= 30:
            buckets["days_1_30"] += r["balance"]
        elif d <= 60:
            buckets["days_31_60"] += r["balance"]
        elif d <= 90:
            buckets["days_61_90"] += r["balance"]
        else:
            buckets["over_90"] += r["balance"]

    return {"buckets": buckets, "invoices": results}


@router.get("/ar/collections")
def get_ar_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all collection sequences with drafts and status."""
    tid = current_user.company_id
    sequences = (
        db.query(AgentCollectionSequence)
        .filter(AgentCollectionSequence.tenant_id == tid)
        .order_by(AgentCollectionSequence.created_at.desc())
        .limit(50)
        .all()
    )

    results = []
    for seq in sequences:
        customer = db.query(Customer).filter(Customer.id == seq.customer_id).first()
        invoice = db.query(Invoice).filter(Invoice.id == seq.invoice_id).first()
        results.append({
            "id": seq.id,
            "customer_name": customer.name if customer else "Unknown",
            "invoice_number": invoice.invoice_number if invoice else None,
            "invoice_amount": float(invoice.total) if invoice else 0,
            "balance": float(invoice.total - (invoice.amount_paid or 0)) if invoice else 0,
            "days_overdue": (date.today() - invoice.due_date).days if invoice and invoice.due_date else 0,
            "step": seq.sequence_step,
            "has_draft": bool(seq.draft_subject),
            "draft_subject": seq.draft_subject,
            "last_sent": seq.last_sent_at.isoformat() if seq.last_sent_at else None,
            "next_scheduled": seq.next_scheduled_at.isoformat() if seq.next_scheduled_at else None,
            "paused": seq.paused,
            "pause_reason": seq.pause_reason,
            "completed": seq.completed,
        })

    drafts_count = sum(1 for r in results if r["has_draft"] and not r["completed"] and not r["paused"])
    active_count = sum(1 for r in results if not r["completed"] and not r["paused"])
    paused_count = sum(1 for r in results if r["paused"])

    return {
        "drafts_awaiting": drafts_count,
        "active": active_count,
        "paused": paused_count,
        "sequences": results,
    }


@router.get("/ar/credit")
def get_ar_credit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get credit status for all customers with credit limits."""
    tid = current_user.company_id
    customers = db.query(Customer).filter(
        Customer.company_id == tid, Customer.credit_limit.isnot(None), Customer.credit_limit > 0,
    ).all()

    results = []
    for c in customers:
        balance = db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).filter(
            Invoice.customer_id == c.id, Invoice.status.in_(["sent", "open", "partial", "overdue"]),
        ).scalar() or 0

        pct = (float(balance) / float(c.credit_limit) * 100) if c.credit_limit else 0
        results.append({
            "customer_id": c.id,
            "customer_name": c.name,
            "credit_limit": float(c.credit_limit),
            "current_balance": float(balance),
            "available": float(c.credit_limit - balance),
            "utilization_pct": round(pct, 1),
            "on_hold": getattr(c, "credit_hold", False),
            "status": "hold" if getattr(c, "credit_hold", False) else ("warning" if pct >= 90 else ("caution" if pct >= 80 else "ok")),
        })

    results.sort(key=lambda x: x["utilization_pct"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# AP Endpoints
# ---------------------------------------------------------------------------


@router.get("/ap/due")
def get_ap_due(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all open bills grouped by urgency."""
    tid = current_user.company_id
    today = date.today()

    bills = db.query(VendorBill).filter(
        VendorBill.company_id == tid, VendorBill.status.in_(["pending", "approved", "partial"]),
    ).order_by(VendorBill.due_date.asc()).all()

    results = []
    buckets = {"overdue": 0, "due_today": 0, "due_this_week": 0, "due_next_week": 0}

    for b in bills:
        vendor = db.query(Vendor).filter(Vendor.id == b.vendor_id).first() if b.vendor_id else None
        balance = float(b.total - (b.amount_paid or 0))
        bill_due = b.due_date.date() if hasattr(b.due_date, "date") else b.due_date
        days_until = (bill_due - today).days if bill_due else 999

        if days_until < 0:
            buckets["overdue"] += balance
        elif days_until == 0:
            buckets["due_today"] += balance
        elif days_until <= 7:
            buckets["due_this_week"] += balance
        elif days_until <= 14:
            buckets["due_next_week"] += balance

        results.append({
            "id": b.id,
            "bill_number": b.number,
            "vendor_name": vendor.name if vendor else "Unknown",
            "amount": float(b.total),
            "balance": balance,
            "due_date": str(bill_due) if bill_due else None,
            "days_until_due": days_until,
            "status": b.status,
        })

    return {"buckets": buckets, "bills": results}


@router.get("/ap/payment-run/suggested")
def get_suggested_payment_run(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get suggested bills for a payment run — all due within 10 days."""
    tid = current_user.company_id
    today = date.today()
    cutoff = today + timedelta(days=10)

    bills = db.query(VendorBill).filter(
        VendorBill.company_id == tid, VendorBill.status.in_(["pending", "approved", "partial"]),
        func.date(VendorBill.due_date) <= cutoff,
    ).order_by(VendorBill.due_date.asc()).all()

    results = []
    total = 0
    for b in bills:
        vendor = db.query(Vendor).filter(Vendor.id == b.vendor_id).first() if b.vendor_id else None
        balance = float(b.total - (b.amount_paid or 0))
        total += balance
        bill_due = b.due_date.date() if hasattr(b.due_date, "date") else b.due_date
        results.append({
            "id": b.id,
            "bill_number": b.number,
            "vendor_name": vendor.name if vendor else "Unknown",
            "amount": balance,
            "due_date": str(bill_due) if bill_due else None,
            "days_until_due": (bill_due - today).days if bill_due else 0,
        })

    return {"bills": results, "total": total, "count": len(results)}


# ---------------------------------------------------------------------------
# Cash Flow Forecast
# ---------------------------------------------------------------------------


@router.get("/cashflow/forecast")
def get_cashflow_forecast(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """5-week forward cash flow view."""
    tid = current_user.company_id
    today = date.today()
    weeks = []

    for i in range(5):
        week_start = today + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)

        # Expected AR collections (invoices due this week)
        ar = db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).filter(
            Invoice.company_id == tid, Invoice.status.in_(["sent", "open", "partial", "overdue"]),
            Invoice.due_date >= week_start, Invoice.due_date <= week_end,
        ).scalar() or 0

        # Committed AP payments (bills due this week)
        try:
            ap = db.query(func.coalesce(func.sum(VendorBill.total - VendorBill.amount_paid), 0)).filter(
                VendorBill.company_id == tid, VendorBill.status.in_(["pending", "approved", "partial"]),
                func.date(VendorBill.due_date) >= week_start,
                func.date(VendorBill.due_date) <= week_end,
            ).scalar() or 0
        except Exception:
            ap = 0

        net = float(ar) - float(ap)
        weeks.append({
            "week_start": str(week_start),
            "week_end": str(week_end),
            "label": f"Week of {week_start.strftime('%b %d')}",
            "ar_expected": float(ar),
            "ap_committed": float(ap),
            "net": net,
            "has_gap": net < 0,
        })

    return {"weeks": weeks}


# ---------------------------------------------------------------------------
# Agent Activity Feed
# ---------------------------------------------------------------------------


@router.get("/debug/invoice-status")
def debug_invoice_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Debug: return invoice counts by status for this tenant."""
    tid = current_user.company_id
    rows = db.query(Invoice.status, func.count(Invoice.id), func.sum(Invoice.total)).filter(
        Invoice.company_id == tid,
    ).group_by(Invoice.status).all()
    return {
        "company_id": tid,
        "by_status": [{"status": r[0], "count": r[1], "total": float(r[2] or 0)} for r in rows],
    }


@router.get("/agent/activity-feed")
def get_agent_activity_feed(
    days: int = Query(7, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get agent activity for the last N days."""
    tid = current_user.company_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    logs = (
        db.query(AgentActivityLog)
        .filter(AgentActivityLog.tenant_id == tid, AgentActivityLog.created_at >= since)
        .order_by(AgentActivityLog.created_at.desc())
        .limit(100)
        .all()
    )

    # Summary for last 24h
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    auto_count = sum(1 for l in logs if l.autonomous and l.created_at >= last_24h)
    alerts_count = sum(1 for l in logs if l.action_type.startswith("alert") and l.created_at >= last_24h)

    return {
        "summary_24h": {
            "autonomous_actions": auto_count,
            "alerts_created": alerts_count,
            "total_actions": sum(1 for l in logs if l.created_at >= last_24h),
        },
        "entries": [
            {
                "id": l.id,
                "action_type": l.action_type,
                "description": l.description,
                "affected_record_type": l.affected_record_type,
                "affected_record_id": l.affected_record_id,
                "autonomous": l.autonomous,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
    }
