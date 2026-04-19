"""AR/AP Agent Service — background monitoring, alerting, and autonomous actions.

All autonomous write actions are limited to exact payment matching and credit memo
creation. Everything else surfaces alerts requiring human approval.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import AgentActivityLog, AgentAlert, AgentCollectionSequence, AgentJob
from app.models.customer import Customer
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)

COLLECTIONS_MODEL = "claude-haiku-4-5-20250514"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _create_job(db: Session, tenant_id: str, job_type: str) -> AgentJob:
    job = AgentJob(tenant_id=tenant_id, job_type=job_type, status="running", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _complete_job(db: Session, job: AgentJob, summary: dict | None = None, error: str | None = None):
    job.status = "failed" if error else "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.result_summary = summary
    job.error_message = error
    db.commit()


def create_alert(
    db: Session, tenant_id: str, alert_type: str, severity: str,
    title: str, message: str, action_label: str | None = None,
    action_url: str | None = None, action_payload: dict | None = None,
) -> AgentAlert:
    alert = AgentAlert(
        tenant_id=tenant_id, alert_type=alert_type, severity=severity,
        title=title, message=message, action_label=action_label,
        action_url=action_url, action_payload=action_payload,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def log_activity(
    db: Session, tenant_id: str, action_type: str, description: str,
    job_id: str | None = None, record_type: str | None = None,
    record_id: str | None = None, autonomous: bool = False,
    approved_by: str | None = None,
):
    db.add(AgentActivityLog(
        tenant_id=tenant_id, job_id=job_id, action_type=action_type,
        description=description, affected_record_type=record_type,
        affected_record_id=record_id, autonomous=autonomous,
        approved_by=approved_by,
    ))
    db.commit()


# ---------------------------------------------------------------------------
# JOB 1 — AR Aging Monitor
# ---------------------------------------------------------------------------


def run_ar_aging_monitor(db: Session, tenant_id: str) -> dict:
    """Check aging thresholds and create alerts for invoices crossing boundaries."""
    job = _create_job(db, tenant_id, "ar_aging_monitor")
    try:
        now = date.today()
        open_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == tenant_id,
                Invoice.status.in_(["sent", "partial", "overdue"]),
                Invoice.due_date.isnot(None),
            )
            .all()
        )

        alerts_created = 0
        sequences_started = 0

        for inv in open_invoices:
            days_overdue = (now - inv.due_date).days if inv.due_date else 0
            if days_overdue <= 0:
                continue

            customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()
            cust_name = customer.name if customer else "Unknown"
            balance = float(inv.total - (inv.amount_paid or 0))

            # 31-60 days — start collection sequence
            if 31 <= days_overdue <= 60:
                existing = (
                    db.query(AgentCollectionSequence)
                    .filter(AgentCollectionSequence.invoice_id == inv.id, AgentCollectionSequence.completed == False)
                    .first()
                )
                if not existing:
                    db.add(AgentCollectionSequence(
                        tenant_id=tenant_id, customer_id=inv.customer_id,
                        invoice_id=inv.id, sequence_step=1,
                        next_scheduled_at=datetime.now(timezone.utc),
                    ))
                    create_alert(
                        db, tenant_id, "ar_aging_31", "info",
                        f"{cust_name} — Invoice #{inv.invoice_number or inv.id[:8]} is now {days_overdue} days past due",
                        f"Collection sequence started. Balance: ${balance:,.2f}",
                    )
                    sequences_started += 1
                    alerts_created += 1

            # 61-90 days — escalate
            elif 61 <= days_overdue <= 90:
                seq = (
                    db.query(AgentCollectionSequence)
                    .filter(AgentCollectionSequence.invoice_id == inv.id, AgentCollectionSequence.completed == False)
                    .first()
                )
                if seq and seq.sequence_step < 2:
                    seq.sequence_step = 2
                    seq.next_scheduled_at = datetime.now(timezone.utc)
                create_alert(
                    db, tenant_id, "ar_aging_61", "warning",
                    f"{cust_name} — Invoice #{inv.invoice_number or inv.id[:8]} is now {days_overdue} days past due",
                    f"Second notice scheduled. Balance: ${balance:,.2f}",
                )
                alerts_created += 1

            # 90+ days — critical
            elif days_overdue > 90:
                create_alert(
                    db, tenant_id, "ar_aging_90", "action_required",
                    f"{cust_name} has ${balance:,.2f} outstanding 90+ days",
                    f"Recommend credit hold review. Invoice #{inv.invoice_number or inv.id[:8]} is {days_overdue} days past due.",
                    action_label="Review Account",
                    action_url=f"/customers/{inv.customer_id}",
                )
                alerts_created += 1

        summary = {"invoices_checked": len(open_invoices), "alerts_created": alerts_created, "sequences_started": sequences_started}
        log_activity(db, tenant_id, "ar_aging_monitor", f"Checked {len(open_invoices)} invoices, created {alerts_created} alerts", job.id)
        _complete_job(db, job, summary)
        return summary

    except Exception as e:
        _complete_job(db, job, error=str(e))
        logger.error(f"AR aging monitor failed for tenant {tenant_id}: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# JOB 2 — Collections Sequence
# ---------------------------------------------------------------------------


def run_collections_sequence(db: Session, tenant_id: str) -> dict:
    """Process due collection sequences — generate email drafts for human review."""
    job = _create_job(db, tenant_id, "collections_sequence")
    try:
        now = datetime.now(timezone.utc)
        due_sequences = (
            db.query(AgentCollectionSequence)
            .filter(
                AgentCollectionSequence.tenant_id == tenant_id,
                AgentCollectionSequence.paused == False,
                AgentCollectionSequence.completed == False,
                AgentCollectionSequence.next_scheduled_at <= now,
            )
            .all()
        )

        drafts_created = 0
        for seq in due_sequences:
            invoice = db.query(Invoice).filter(Invoice.id == seq.invoice_id).first()
            customer = db.query(Customer).filter(Customer.id == seq.customer_id).first()
            if not invoice or not customer:
                continue

            days_overdue = (date.today() - invoice.due_date).days if invoice.due_date else 0
            balance = float(invoice.total - (invoice.amount_paid or 0))

            # Phase 2c-1 collapse: reuse the managed `agent.ar_collections.draft_email`
            # prompt (already used by ARCollectionsAgent) instead of a duplicate
            # direct-SDK helper. Map the per-step tone to the existing tier
            # enum understood by the managed prompt.
            tier = {1: "FOLLOW_UP", 2: "ESCALATE", 3: "CRITICAL"}.get(
                seq.sequence_step, "FOLLOW_UP"
            )
            invoice_number = invoice.invoice_number or str(invoice.id)[:8]
            invoice_line = (
                f"- Invoice #{invoice_number}: ${balance:,.2f} "
                f"(due {invoice.due_date}, {days_overdue} days past due)"
            )
            draft_body = _draft_collections_email(
                db,
                tenant_id=tenant_id,
                caller_agent_job_id=job.id,
                customer_id=customer.id,
                customer_name=customer.name,
                total_outstanding=balance,
                invoice_count=1,
                oldest_days=days_overdue,
                tier=tier,
                invoice_lines=invoice_line,
            )

            # Subject line is template-based — no AI needed for it. Keep the
            # legacy shape so the reviewer UI stays compatible.
            seq.draft_subject = f"Payment Reminder — Invoice #{invoice_number}"
            seq.draft_body = draft_body or _collections_fallback_body(
                customer.name, invoice_number, balance, invoice.due_date, days_overdue
            )
            seq.original_draft_body = seq.draft_body  # Store original for edit detection
            seq.next_scheduled_at = now + timedelta(days=14)
            drafts_created += 1

            step_label = {1: "First notice", 2: "Second notice", 3: "Final notice"}.get(seq.sequence_step, "Notice")
            create_alert(
                db, tenant_id, "collections_draft_ready", "action_required",
                f"Collections email ready for {customer.name}",
                f"{step_label}: Invoice #{invoice.invoice_number or invoice.id[:8]} for ${balance:,.2f} is {days_overdue} days overdue.",
                action_label="Review & Send",
                action_url=f"/ar/collections/{seq.id}/review",
            )

        summary = {"sequences_processed": len(due_sequences), "drafts_created": drafts_created}
        log_activity(db, tenant_id, "collections_sequence", f"Processed {len(due_sequences)} sequences, created {drafts_created} drafts", job.id)
        _complete_job(db, job, summary)
        return summary

    except Exception as e:
        _complete_job(db, job, error=str(e))
        logger.error(f"Collections sequence failed for tenant {tenant_id}: {e}")
        return {"error": str(e)}


def _draft_collections_email(
    db: Session,
    *,
    tenant_id: str,
    caller_agent_job_id: str | None,
    customer_id: str,
    customer_name: str,
    total_outstanding: float,
    invoice_count: int,
    oldest_days: int,
    tier: str,
    invoice_lines: str,
) -> str | None:
    """Draft a collections email body via the managed Intelligence prompt.

    Returns the plain-text body on success, None on failure. The sequence
    caller falls back to a deterministic template when this returns None.

    Uses the same `agent.ar_collections.draft_email` prompt as the Phase 2a
    ARCollectionsAgent — Phase 2c-1 collapse eliminates the duplicate SDK
    path that used to live in `_generate_collections_draft`.
    """
    from app.services.intelligence import intelligence_service

    try:
        result = intelligence_service.execute(
            db,
            prompt_key="agent.ar_collections.draft_email",
            variables={
                "customer_name": customer_name,
                "total_outstanding": f"{total_outstanding:,.2f}",
                "invoice_count": invoice_count,
                "oldest_days": oldest_days,
                "tier": tier,
                "invoice_lines": invoice_lines,
            },
            company_id=tenant_id,
            caller_module="agent_service.run_collections_sequence",
            caller_entity_type="customer",
            caller_entity_id=customer_id,
            caller_agent_job_id=caller_agent_job_id,
        )
        if result.status == "success":
            return result.response_text
        logger.warning(
            "Collections draft failed for %s: status=%s error=%s",
            customer_name, result.status, result.error_message,
        )
        return None
    except Exception as e:
        logger.error("Collections draft generation failed: %s", e)
        return None


def _collections_fallback_body(
    customer_name: str,
    invoice_number: str,
    amount: float,
    due_date,
    days_overdue: int,
) -> str:
    """Deterministic fallback body when the Intelligence call fails."""
    return (
        f"Dear {customer_name},\n\n"
        f"This is a reminder that Invoice #{invoice_number} for ${amount:,.2f} "
        f"(due {due_date}) is now {days_overdue} days past due.\n\n"
        f"Please arrange payment at your earliest convenience.\n\n"
        f"Thank you."
    )


# ---------------------------------------------------------------------------
# JOB 5 — AP Upcoming Payments
# ---------------------------------------------------------------------------


def run_ap_upcoming_payments(db: Session, tenant_id: str) -> dict:
    """Check upcoming AP bills and create payment alerts."""
    from app.models.bill import Bill
    from app.models.vendor import Vendor

    job = _create_job(db, tenant_id, "ap_upcoming_payments")
    try:
        today = date.today()
        fourteen_days = today + timedelta(days=14)

        open_bills = (
            db.query(Bill)
            .filter(
                Bill.tenant_id == tenant_id,
                Bill.status.in_(["open", "partial", "overdue"]),
                Bill.due_date.isnot(None),
                Bill.due_date <= fourteen_days,
            )
            .all()
        )

        alerts_created = 0
        overdue_total = Decimal(0)
        due_this_week = Decimal(0)
        due_soon = []

        for bill in open_bills:
            vendor = db.query(Vendor).filter(Vendor.id == bill.vendor_id).first() if bill.vendor_id else None
            vendor_name = vendor.vendor_name if vendor else (bill.vendor_name_raw or "Unknown")
            balance = bill.balance_due or (bill.total_amount - (bill.amount_paid or 0))
            days_until = (bill.due_date - today).days

            if days_until < 0:
                # Overdue
                overdue_total += Decimal(str(balance))
                create_alert(
                    db, tenant_id, "ap_overdue", "action_required",
                    f"{vendor_name} — Bill #{bill.bill_number or bill.id[:8]} overdue",
                    f"${float(balance):,.2f} was due {abs(days_until)} days ago.",
                    action_label="Record Payment", action_url=f"/ap/bills/{bill.id}",
                )
                alerts_created += 1
            elif days_until <= 3:
                create_alert(
                    db, tenant_id, "ap_due_soon", "warning",
                    f"{vendor_name} — Bill #{bill.bill_number or bill.id[:8]} due in {days_until} days",
                    f"${float(balance):,.2f} due {bill.due_date}.",
                    action_label="Record Payment", action_url=f"/ap/bills/{bill.id}",
                )
                alerts_created += 1
                due_this_week += Decimal(str(balance))
            else:
                due_soon.append({"vendor": vendor_name, "amount": float(balance), "due": str(bill.due_date)})

        # Digest for 4-14 day bills
        if due_soon:
            total_soon = sum(b["amount"] for b in due_soon)
            create_alert(
                db, tenant_id, "ap_upcoming_digest", "info",
                f"{len(due_soon)} bills totaling ${total_soon:,.2f} due in the next 14 days",
                "Review your upcoming payment schedule.",
                action_label="View Payment Schedule", action_url="/ap/bills?tab=ap-aging",
            )
            alerts_created += 1

        # Monday payment run suggestion
        if today.weekday() == 0:  # Monday
            week_bills = [b for b in open_bills if b.due_date and 0 <= (b.due_date - today).days <= 10]
            if week_bills:
                total_run = sum(float((b.balance_due or (b.total_amount - (b.amount_paid or 0)))) for b in week_bills)
                create_alert(
                    db, tenant_id, "ap_payment_run", "action_required",
                    f"Suggested payment run: {len(week_bills)} bills totaling ${total_run:,.2f}",
                    "Bills due this week are ready for a batch payment run.",
                    action_label="Review Payment Run", action_url="/ap/payment-run",
                    action_payload={"bill_ids": [b.id for b in week_bills]},
                )
                alerts_created += 1

        summary = {"bills_checked": len(open_bills), "alerts_created": alerts_created}
        log_activity(db, tenant_id, "ap_upcoming_payments", f"Checked {len(open_bills)} bills", job.id)
        _complete_job(db, job, summary)
        return summary

    except Exception as e:
        _complete_job(db, job, error=str(e))
        logger.error(f"AP upcoming payments failed for tenant {tenant_id}: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------


def get_alerts(
    db: Session, tenant_id: str, severity: str | None = None,
    resolved: bool | None = None, limit: int = 50,
) -> list[dict]:
    query = db.query(AgentAlert).filter(AgentAlert.tenant_id == tenant_id)
    if severity:
        query = query.filter(AgentAlert.severity == severity)
    if resolved is not None:
        query = query.filter(AgentAlert.resolved == resolved)
    alerts = query.order_by(AgentAlert.created_at.desc()).limit(limit).all()
    return [
        {
            "id": a.id, "alert_type": a.alert_type, "severity": a.severity,
            "title": a.title, "message": a.message, "action_label": a.action_label,
            "action_url": a.action_url, "action_payload": a.action_payload,
            "resolved": a.resolved, "auto_resolved": a.auto_resolved,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


def resolve_alert(db: Session, alert_id: str, tenant_id: str, user_id: str | None = None, auto: bool = False) -> bool:
    alert = db.query(AgentAlert).filter(AgentAlert.id == alert_id, AgentAlert.tenant_id == tenant_id).first()
    if not alert:
        return False
    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = user_id
    alert.auto_resolved = auto
    db.commit()
    return True


def get_activity_log(db: Session, tenant_id: str, limit: int = 100) -> list[dict]:
    logs = (
        db.query(AgentActivityLog)
        .filter(AgentActivityLog.tenant_id == tenant_id)
        .order_by(AgentActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id, "action_type": l.action_type, "description": l.description,
            "affected_record_type": l.affected_record_type,
            "affected_record_id": l.affected_record_id,
            "autonomous": l.autonomous,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


def get_collection_sequence(db: Session, sequence_id: str, tenant_id: str) -> dict | None:
    seq = (
        db.query(AgentCollectionSequence)
        .filter(AgentCollectionSequence.id == sequence_id, AgentCollectionSequence.tenant_id == tenant_id)
        .first()
    )
    if not seq:
        return None
    customer = db.query(Customer).filter(Customer.id == seq.customer_id).first()
    invoice = db.query(Invoice).filter(Invoice.id == seq.invoice_id).first()
    return {
        "id": seq.id, "sequence_step": seq.sequence_step,
        "draft_subject": seq.draft_subject, "draft_body": seq.draft_body,
        "paused": seq.paused, "pause_reason": seq.pause_reason,
        "customer_name": customer.name if customer else "Unknown",
        "customer_email": customer.email if customer else None,
        "invoice_number": invoice.invoice_number if invoice else None,
        "invoice_amount": float(invoice.total) if invoice else 0,
        "days_overdue": (date.today() - invoice.due_date).days if invoice and invoice.due_date else 0,
    }


def pause_collection(db: Session, sequence_id: str, tenant_id: str, reason: str) -> bool:
    seq = (
        db.query(AgentCollectionSequence)
        .filter(AgentCollectionSequence.id == sequence_id, AgentCollectionSequence.tenant_id == tenant_id)
        .first()
    )
    if not seq:
        return False
    seq.paused = True
    seq.pause_reason = reason
    log_activity(db, tenant_id, "collection_paused", f"Paused: {reason}", record_type="collection_sequence", record_id=sequence_id)
    db.commit()
    return True
