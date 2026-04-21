"""Triage AI Question panel — interactive Q&A about the current item.

Follow-up 2 of the UI/UX arc. When a user triages an item and the
queue config includes an `ai_question` context panel, they can ask
Claude arbitrary questions about the item; Claude answers grounded
in the item record + related entities + vertical-aware terminology.

Contrast with the `ai_summary` panel type (Phase 5 stub, still
unwired): summary is passive (generated on render); question is
interactive (user provides the prompt).

Prompt reuse — deliberate:
  The existing `triage.task_context_question` and
  `triage.ss_cert_context_question` prompts (seeded at the end of
  Phase 5) were authored with Q&A shape — `user_question` variable,
  `{answer, confidence, sources}` response. Each queue's
  `ai_question` panel cites its own `ai_prompt_key` so per-queue
  specialization is preserved. The seed script
  `scripts/seed_intelligence_followup2.py` adds a vertical-aware
  terminology block via v1→v2 bump (Phase 6 Option A pattern).

Related-entity context:
  `_RELATED_ENTITY_BUILDERS` mirrors `engine._DIRECT_QUERIES` — one
  builder per direct-query key. Each builder takes the item row dict
  (already denormalized by the direct query) and returns a list of
  related-entity dicts the prompt can reason over. Keeping the
  builder dict parallel to `_DIRECT_QUERIES` means adding a new
  queue is one extension point, not two.

  Future extension path (post-arc): `ContextPanelConfig` could gain
  an `include_saved_view_context: str` (Phase 2 seed key) for
  dynamic saved-view-scoping. That would require extending Phase 2's
  executor to accept per-row filter injection — a non-trivial
  coordinated change. Deferred.

Rate limiting:
  In-memory token bucket per (user_id) at 10 req/min. Enough to
  defend against accidental runaway clients without crushing the UX.
  Returns a structured `RateLimited` error that the API layer
  translates to HTTP 429 with `retry_after_seconds`. Post-arc could
  swap to Redis-backed if we need cross-process enforcement.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.intelligence import intelligence_service
from app.services.intelligence.confidence import ConfidenceTier, to_tier
from app.services.triage import engine as _engine
from app.services.triage import registry as _registry
from app.services.triage.types import (
    ContextPanelConfig,
    ContextPanelType,
    SessionNotFound,
    TriageError,
    TriageQueueConfig,
)

logger = logging.getLogger(__name__)


# ── Types ───────────────────────────────────────────────────────────


@dataclass
class SourceReference:
    entity_type: str
    entity_id: str
    display_label: str
    snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "display_label": self.display_label,
            "snippet": self.snippet,
        }


@dataclass
class AskQuestionResponse:
    question: str
    answer: str
    confidence: ConfidenceTier
    confidence_score: float | None  # raw 0.0-1.0 from the model, for telemetry
    source_references: list[SourceReference]
    latency_ms: int
    asked_at: datetime
    execution_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "source_references": [s.to_dict() for s in self.source_references],
            "latency_ms": self.latency_ms,
            "asked_at": self.asked_at.isoformat(),
            "execution_id": self.execution_id,
        }


class QuestionTooLong(TriageError):
    http_status = 400


class NoAIQuestionPanel(TriageError):
    http_status = 400


class AIQuestionFailed(TriageError):
    http_status = 502


class ItemNotFound(TriageError):
    http_status = 404


# ── Rate limiter ────────────────────────────────────────────────────


_RATE_LIMIT_WINDOW_SECONDS: int = 60
_RATE_LIMIT_MAX_REQUESTS: int = 10
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK: Lock = Lock()


class RateLimited(TriageError):
    """Raised when a user exceeds the per-user question rate limit.

    The API layer catches this and translates it to HTTP 429 with a
    structured body carrying `retry_after_seconds` so the frontend
    can render a friendly toast instead of a raw error.
    """

    http_status = 429

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            f"Rate limit exceeded. Retry in {retry_after_seconds}s."
        )
        self.retry_after_seconds = retry_after_seconds


def _check_rate_limit(user_id: str) -> None:
    """Sliding-window rate limit. Records the request timestamp on
    success; raises `RateLimited` with `retry_after_seconds` if the
    user is over budget.

    In-process state — resets on worker restart. Documented +
    acceptable for the scope; swap to Redis if cross-process
    enforcement becomes necessary.
    """
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.setdefault(user_id, deque())
        # Drop expired entries.
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
            # Next available slot = oldest entry's age + window + 1s cushion.
            oldest = bucket[0]
            retry = int((oldest + _RATE_LIMIT_WINDOW_SECONDS) - now) + 1
            retry = max(retry, 1)
            raise RateLimited(retry)
        bucket.append(now)


def _reset_rate_limiter() -> None:
    """Test seam — clears all buckets. Not exported publicly."""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()


# ── Related-entity builders ─────────────────────────────────────────


def _build_task_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """Task Q&A context: resolve the linked related entity (if any) +
    the last 5 tasks for the same assignee (open/in_progress/blocked,
    excluding the current item)."""
    from app.models.task import Task

    out: list[dict[str, Any]] = []
    rel_type = item_row.get("related_entity_type")
    rel_id = item_row.get("related_entity_id")
    if rel_type and rel_id:
        out.append(
            {
                "entity_type": rel_type,
                "entity_id": rel_id,
                "context": "linked_entity",
                "display_label": f"Linked {rel_type}",
            }
        )

    assignee_id = item_row.get("assignee_user_id") or user.id
    sibling_tasks = (
        db.query(Task)
        .filter(
            Task.company_id == user.company_id,
            Task.assignee_user_id == assignee_id,
            Task.is_active.is_(True),
            Task.id != item_row.get("id"),
        )
        .order_by(Task.created_at.desc())
        .limit(5)
        .all()
    )
    for t in sibling_tasks:
        out.append(
            {
                "entity_type": "task",
                "entity_id": t.id,
                "context": "same_assignee",
                "display_label": t.title,
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            }
        )
    return out


def _build_ss_cert_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """SS Cert Q&A context: the SalesOrder + Customer, plus the last
    3 approved certs for the same funeral home (for history
    questions)."""
    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder
    from app.models.social_service_certificate import (
        SocialServiceCertificate,
    )

    out: list[dict[str, Any]] = []

    order_id = item_row.get("order_id")
    order: SalesOrder | None = None
    if order_id:
        order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if order is not None:
        out.append(
            {
                "entity_type": "sales_order",
                "entity_id": order.id,
                "context": "source_order",
                "display_label": f"Order {order.number}",
                "total": float(order.total or 0),
                "status": order.status,
                "ship_to_name": getattr(order, "ship_to_name", None),
                "deceased_name": getattr(order, "deceased_name", None),
            }
        )

        customer_id = getattr(order, "customer_id", None)
        customer: Customer | None = None
        if customer_id:
            customer = (
                db.query(Customer).filter(Customer.id == customer_id).first()
            )
        if customer is not None:
            out.append(
                {
                    "entity_type": "customer",
                    "entity_id": customer.id,
                    "context": "funeral_home",
                    "display_label": customer.name,
                    "account_status": getattr(customer, "account_status", None),
                }
            )
            # Past 3 approved certs for the same funeral home.
            past = (
                db.query(SocialServiceCertificate)
                .join(
                    SalesOrder,
                    SalesOrder.id == SocialServiceCertificate.order_id,
                )
                .filter(
                    SocialServiceCertificate.company_id == user.company_id,
                    SalesOrder.customer_id == customer.id,
                    SocialServiceCertificate.id != item_row.get("id"),
                    SocialServiceCertificate.status.in_(("approved", "sent")),
                )
                .order_by(SocialServiceCertificate.generated_at.desc())
                .limit(3)
                .all()
            )
            for c in past:
                out.append(
                    {
                        "entity_type": "social_service_certificate",
                        "entity_id": c.id,
                        "context": "past_same_fh",
                        "display_label": c.certificate_number
                        or f"Cert {c.id[:8]}",
                        "status": c.status,
                        "generated_at": c.generated_at.isoformat()
                        if c.generated_at
                        else None,
                    }
                )
    return out


def _build_cash_receipts_matching_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8b — related-entity context for a cash
    receipts triage item.

    Returns (a) the CustomerPayment row, (b) the paying Customer + AR
    summary, (c) up to 5 candidate open invoices for that customer
    ranked by |balance - payment_amount|, (d) the last 3 applied
    payment/invoice pairs for that customer (pattern-matching aid).
    """
    from decimal import Decimal

    from app.models.customer import Customer
    from app.models.customer_payment import (
        CustomerPayment,
        CustomerPaymentApplication,
    )
    from app.models.invoice import Invoice

    out: list[dict[str, Any]] = []

    payment_id = item_row.get("payment_id")
    if not payment_id:
        return out
    payment = (
        db.query(CustomerPayment)
        .filter(
            CustomerPayment.id == payment_id,
            CustomerPayment.deleted_at.is_(None),
        )
        .first()
    )
    if payment is None:
        return out

    pay_amount = Decimal(str(payment.total_amount or 0))
    out.append(
        {
            "entity_type": "customer_payment",
            "entity_id": payment.id,
            "context": "payment",
            "display_label": (
                f"Payment ${float(pay_amount):,.2f} on "
                f"{payment.payment_date.date().isoformat() if payment.payment_date else '—'}"
            ),
            "amount": float(pay_amount),
            "payment_date": (
                payment.payment_date.isoformat() if payment.payment_date else None
            ),
            "payment_method": payment.payment_method,
            "reference_number": payment.reference_number,
        }
    )

    # Customer
    customer = (
        db.query(Customer)
        .filter(Customer.id == payment.customer_id)
        .first()
    )
    if customer is not None:
        out.append(
            {
                "entity_type": "customer",
                "entity_id": customer.id,
                "context": "paying_customer",
                "display_label": customer.name,
                "account_status": getattr(customer, "account_status", None),
            }
        )

        # Candidate open invoices — top 5 by |balance - payment_amount|
        open_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == user.company_id,
                Invoice.customer_id == customer.id,
                Invoice.status.notin_(("paid", "void", "write_off", "draft")),
            )
            .all()
        )
        scored = []
        for inv in open_invoices:
            balance = Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))
            if balance <= 0:
                continue
            scored.append((abs(balance - pay_amount), inv, balance))
        scored.sort(key=lambda t: t[0])
        for _, inv, balance in scored[:5]:
            out.append(
                {
                    "entity_type": "invoice",
                    "entity_id": inv.id,
                    "context": "candidate_invoice",
                    "display_label": (
                        f"Invoice {inv.number} — ${float(balance):,.2f} due"
                    ),
                    "number": inv.number,
                    "balance_due": float(balance),
                    "total": float(inv.total or 0),
                    "status": inv.status,
                    "invoice_date": (
                        inv.invoice_date.isoformat() if inv.invoice_date else None
                    ),
                }
            )

        # Last 3 applied payment/invoice pairs for this customer
        # (pattern-matching aid — "this customer usually pays lumped").
        past = (
            db.query(CustomerPaymentApplication, CustomerPayment, Invoice)
            .join(
                CustomerPayment,
                CustomerPayment.id == CustomerPaymentApplication.payment_id,
            )
            .join(Invoice, Invoice.id == CustomerPaymentApplication.invoice_id)
            .filter(
                CustomerPayment.company_id == user.company_id,
                CustomerPayment.customer_id == customer.id,
                CustomerPayment.id != payment.id,
            )
            .order_by(CustomerPayment.payment_date.desc())
            .limit(3)
            .all()
        )
        for app_row, past_pay, past_inv in past:
            out.append(
                {
                    "entity_type": "customer_payment_application",
                    "entity_id": app_row.id,
                    "context": "past_match_same_customer",
                    "display_label": (
                        f"${float(app_row.amount_applied):,.2f} → "
                        f"Invoice {past_inv.number}"
                    ),
                    "amount_applied": float(app_row.amount_applied),
                    "invoice_number": past_inv.number,
                    "payment_date": (
                        past_pay.payment_date.isoformat()
                        if past_pay.payment_date
                        else None
                    ),
                }
            )

    return out


def _build_month_end_close_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — month-end-close related entities.

    The item is an AgentJob; the related context is:
      - The AgentJob itself (executive summary fields)
      - Flagged customers (anomalies with entity_type="customer")
      - Uninvoiced deliveries (anomalies with entity_type="sales_order")
      - The prior-period AgentJob (for comparison context)
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    out: list[dict[str, Any]] = []

    agent_job_id = item_row.get("agent_job_id") or item_row.get("id")
    if not agent_job_id:
        return out
    job = (
        db.query(AgentJob)
        .filter(AgentJob.id == agent_job_id)
        .first()
    )
    if job is None:
        return out

    payload = job.report_payload or {}
    exec_summary = (
        payload.get("executive_summary", {})
        if isinstance(payload, dict)
        else {}
    )
    out.append(
        {
            "entity_type": "agent_job",
            "entity_id": job.id,
            "context": "close_run",
            "display_label": (
                f"Month-end close — "
                f"{job.period_start:%B %Y}"
                if job.period_start
                else f"Agent job {job.id[:8]}"
            ),
            "period_start": (
                job.period_start.isoformat() if job.period_start else None
            ),
            "period_end": (
                job.period_end.isoformat() if job.period_end else None
            ),
            "total_revenue": exec_summary.get("total_revenue"),
            "total_ar": exec_summary.get("total_ar"),
            "collection_rate_pct": exec_summary.get(
                "collection_rate_pct"
            ),
            "anomaly_count": job.anomaly_count or 0,
        }
    )

    # Top flagged customers (up to 5 critical/warning by severity)
    sev_order = {"critical": 0, "warning": 1, "info": 2}
    customer_anomalies = (
        db.query(AgentAnomaly)
        .filter(
            AgentAnomaly.agent_job_id == job.id,
            AgentAnomaly.entity_type == "customer",
        )
        .all()
    )
    customer_anomalies.sort(
        key=lambda a: (sev_order.get(a.severity or "", 3), a.created_at)
    )
    for a in customer_anomalies[:5]:
        out.append(
            {
                "entity_type": "customer",
                "entity_id": a.entity_id,
                "context": "flagged_customer",
                "display_label": (
                    (a.description or "")[:80]
                    if a.description
                    else f"Customer {a.entity_id[:8] if a.entity_id else ''}"
                ),
                "severity": a.severity,
                "anomaly_type": a.anomaly_type,
            }
        )

    # Most recent prior month-end close for this tenant (comparison).
    prior = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == "month_end_close",
            AgentJob.id != job.id,
            AgentJob.status.in_(("complete", "approved")),
        )
        .order_by(AgentJob.completed_at.desc().nulls_last())
        .first()
    )
    if prior is not None:
        out.append(
            {
                "entity_type": "agent_job",
                "entity_id": prior.id,
                "context": "prior_month_close",
                "display_label": (
                    f"Prior close — {prior.period_start:%B %Y}"
                    if prior.period_start
                    else "Prior close"
                ),
                "completed_at": (
                    prior.completed_at.isoformat()
                    if prior.completed_at
                    else None
                ),
            }
        )
    return out


def _build_ar_collections_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — AR collections related entities.

    Per-customer context: the Customer row, their open invoices, past
    collection-email deliveries (via document_deliveries filtered by
    caller linkage), past successful collections if any.
    """
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    out: list[dict[str, Any]] = []

    customer_id = item_row.get("customer_id")
    if not customer_id:
        return out

    customer = (
        db.query(Customer)
        .filter(
            Customer.id == customer_id,
            Customer.company_id == user.company_id,
        )
        .first()
    )
    if customer is None:
        return out

    out.append(
        {
            "entity_type": "customer",
            "entity_id": customer.id,
            "context": "paying_customer",
            "display_label": customer.name,
            "billing_email": customer.billing_email or customer.email,
            "account_status": getattr(customer, "account_status", None),
        }
    )

    # Open invoices for this customer — top 5 by age
    open_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == user.company_id,
            Invoice.customer_id == customer.id,
            Invoice.status.notin_(
                ("paid", "void", "write_off", "draft")
            ),
        )
        .order_by(Invoice.invoice_date.asc().nulls_last())
        .limit(5)
        .all()
    )
    for inv in open_invoices:
        balance = float(
            (inv.total or 0) - (inv.amount_paid or 0)
        )
        out.append(
            {
                "entity_type": "invoice",
                "entity_id": inv.id,
                "context": "open_invoice",
                "display_label": (
                    f"Invoice {inv.number} — ${balance:,.2f} due"
                ),
                "number": inv.number,
                "balance_due": balance,
                "total": float(inv.total or 0),
                "status": inv.status,
                "invoice_date": (
                    inv.invoice_date.isoformat()
                    if inv.invoice_date
                    else None
                ),
            }
        )

    # Past collection emails for this customer via document_deliveries.
    try:
        from app.models.document_delivery import DocumentDelivery

        past_sends = (
            db.query(DocumentDelivery)
            .filter(
                DocumentDelivery.company_id == user.company_id,
                DocumentDelivery.template_key == "email.collections",
                DocumentDelivery.recipient_value
                == (customer.billing_email or customer.email or ""),
            )
            .order_by(DocumentDelivery.created_at.desc())
            .limit(3)
            .all()
        )
        for d in past_sends:
            out.append(
                {
                    "entity_type": "document_delivery",
                    "entity_id": d.id,
                    "context": "past_collection_email",
                    "display_label": (
                        f"Collection sent "
                        f"{d.sent_at.isoformat() if d.sent_at else d.created_at.isoformat()}"
                    ),
                    "subject": d.subject,
                    "status": d.status,
                }
            )
    except Exception:
        # If document_delivery query fails (model shape, etc), don't
        # block the rest of the context.
        logger.debug(
            "past-collections lookup failed for customer %s",
            customer.id,
            exc_info=True,
        )

    return out


def _build_expense_categorization_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — expense_categorization related
    entities. Per-line context: VendorBillLine + parent VendorBill +
    Vendor + past categorized lines for the same vendor
    (pattern-matching aid).
    """
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine

    out: list[dict[str, Any]] = []

    line_id = item_row.get("line_id")
    if not line_id:
        return out

    joined = (
        db.query(VendorBillLine, VendorBill, Vendor)
        .join(VendorBill, VendorBill.id == VendorBillLine.bill_id)
        .outerjoin(Vendor, Vendor.id == VendorBill.vendor_id)
        .filter(
            VendorBillLine.id == line_id,
            VendorBill.company_id == user.company_id,
        )
        .first()
    )
    if joined is None:
        return out
    line, bill, vendor = joined

    out.append(
        {
            "entity_type": "vendor_bill_line",
            "entity_id": line.id,
            "context": "expense_line",
            "display_label": (
                f"${float(line.amount or 0):,.2f} — "
                f"{(line.description or 'no description')[:60]}"
            ),
            "amount": float(line.amount or 0),
            "description": line.description,
            "current_category": line.expense_category,
        }
    )
    out.append(
        {
            "entity_type": "vendor_bill",
            "entity_id": bill.id,
            "context": "parent_bill",
            "display_label": (
                f"Bill {bill.number or bill.id[:8]}"
            ),
            "bill_date": (
                bill.bill_date.isoformat() if bill.bill_date else None
            ),
            "total": float(bill.total or 0)
            if getattr(bill, "total", None) is not None
            else None,
        }
    )
    if vendor is not None:
        out.append(
            {
                "entity_type": "vendor",
                "entity_id": vendor.id,
                "context": "vendor",
                "display_label": vendor.name,
            }
        )
        # Past categorized lines for the same vendor — top 3 most
        # recent pattern-matching aid.
        past = (
            db.query(VendorBillLine, VendorBill)
            .join(
                VendorBill, VendorBill.id == VendorBillLine.bill_id
            )
            .filter(
                VendorBill.company_id == user.company_id,
                VendorBill.vendor_id == vendor.id,
                VendorBillLine.id != line.id,
                VendorBillLine.expense_category.isnot(None),
                VendorBillLine.expense_category != "",
            )
            .order_by(VendorBill.bill_date.desc().nulls_last())
            .limit(3)
            .all()
        )
        for past_line, past_bill in past:
            out.append(
                {
                    "entity_type": "vendor_bill_line",
                    "entity_id": past_line.id,
                    "context": "past_line_same_vendor",
                    "display_label": (
                        f"${float(past_line.amount or 0):,.2f} → "
                        f"{past_line.expense_category}"
                    ),
                    "category": past_line.expense_category,
                    "bill_date": (
                        past_bill.bill_date.isoformat()
                        if past_bill.bill_date
                        else None
                    ),
                }
            )
    return out


def _build_safety_program_related(
    db: Session, user: User, item_row: dict[str, Any]
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8d.1 — safety_program related entities.

    AI panel grounds in:
      - The generation itself (generated_at, token usage, model)
      - The SafetyTrainingTopic (title, OSHA code, description, key_points)
      - OSHA scrape preview (text snippet + scrape URL)
      - Prior SafetyProgram version for the same OSHA code (so
        Claude can answer "what's changing from last year?")
      - PDF download URL via D-1 presigned URL (inline — dedicated
        DOCUMENT_PREVIEW panel type is post-arc polish per approved
        scope)
    """
    from app.models.canonical_document import Document as CanonicalDocument
    from app.models.safety_program import SafetyProgram
    from app.models.safety_program_generation import (
        SafetyProgramGeneration,
    )
    from app.models.safety_training_topic import SafetyTrainingTopic

    out: list[dict[str, Any]] = []

    generation_id = item_row.get("generation_id") or item_row.get("id")
    if not generation_id:
        return out

    gen = (
        db.query(SafetyProgramGeneration)
        .filter(
            SafetyProgramGeneration.id == generation_id,
            SafetyProgramGeneration.tenant_id == user.company_id,
        )
        .first()
    )
    if gen is None:
        return out

    # 1. Generation summary — the core artifact being reviewed.
    token_usage = gen.generation_token_usage or {}
    out.append(
        {
            "entity_type": "safety_program_generation",
            "entity_id": gen.id,
            "context": "generation_summary",
            "display_label": (
                f"Safety program generation — "
                f"{gen.year}-{gen.month_number:02d}"
            ),
            "year": gen.year,
            "month_number": gen.month_number,
            "status": gen.status,
            "generation_model": gen.generation_model,
            "input_tokens": token_usage.get("input_tokens"),
            "output_tokens": token_usage.get("output_tokens"),
            "generated_at": (
                gen.generated_at.isoformat() if gen.generated_at else None
            ),
        }
    )

    # 2. Training topic — Claude's target: title, OSHA code, key points.
    if gen.topic_id:
        topic = (
            db.query(SafetyTrainingTopic)
            .filter(SafetyTrainingTopic.id == gen.topic_id)
            .first()
        )
        if topic is not None:
            out.append(
                {
                    "entity_type": "safety_training_topic",
                    "entity_id": topic.id,
                    "context": "target_topic",
                    "display_label": topic.title,
                    "title": topic.title,
                    "osha_standard": topic.osha_standard,
                    "osha_standard_label": topic.osha_standard_label,
                    "description": topic.description,
                    "key_points": topic.key_points,
                    "is_high_risk": topic.is_high_risk,
                    "month_number": topic.month_number,
                }
            )

    # 3. OSHA scrape result — what Claude saw as the regulatory
    # source. Snippet only (first 500 chars); full text stays on
    # the gen row.
    if gen.osha_scraped_text or gen.osha_scrape_url:
        out.append(
            {
                "entity_type": "osha_scrape",
                "entity_id": gen.id,  # keyed on generation; no scrape id
                "context": "regulatory_source",
                "display_label": (
                    f"OSHA standard {gen.osha_standard_code}"
                    if gen.osha_standard_code
                    else "OSHA scrape"
                ),
                "osha_standard_code": gen.osha_standard_code,
                "scrape_url": gen.osha_scrape_url,
                "scrape_status": gen.osha_scrape_status,
                "text_snippet": (
                    (gen.osha_scraped_text or "")[:500]
                    if gen.osha_scraped_text
                    else None
                ),
                "scraped_at": (
                    gen.osha_scraped_at.isoformat()
                    if gen.osha_scraped_at
                    else None
                ),
            }
        )

    # 4. Prior SafetyProgram version — "what's changing from last
    # year's program?" Keyed on matching osha_standard_code.
    if gen.osha_standard_code:
        prior = (
            db.query(SafetyProgram)
            .filter(
                SafetyProgram.company_id == user.company_id,
                SafetyProgram.osha_standard_code == gen.osha_standard_code,
            )
            .order_by(SafetyProgram.updated_at.desc().nulls_last())
            .first()
        )
        if prior is not None:
            out.append(
                {
                    "entity_type": "safety_program",
                    "entity_id": prior.id,
                    "context": "prior_version",
                    "display_label": (
                        f"Prior program (v{prior.version}) — "
                        f"{prior.program_name}"
                    ),
                    "program_name": prior.program_name,
                    "version": prior.version,
                    "status": prior.status,
                    "last_reviewed_at": (
                        prior.last_reviewed_at.isoformat()
                        if prior.last_reviewed_at
                        else None
                    ),
                    # Content is large; include first 1000 chars for
                    # Claude's diff-style reasoning. Full text is
                    # accessible via the bespoke UI if needed.
                    "content_snippet": (
                        (prior.content or "")[:1000]
                        if prior.content
                        else None
                    ),
                }
            )

    # 5. PDF download URL via D-1 — inline per approved scope (no
    # dedicated DOCUMENT_PREVIEW panel). Best-effort: if R2 isn't
    # configured (tests), skip the entity rather than raise.
    if gen.pdf_document_id:
        doc = (
            db.query(CanonicalDocument)
            .filter(
                CanonicalDocument.id == gen.pdf_document_id,
                CanonicalDocument.company_id == user.company_id,
            )
            .first()
        )
        if doc is not None:
            signed_url: str | None = None
            try:
                from app.services.legacy_r2_client import generate_signed_url

                signed_url = generate_signed_url(doc.storage_key, expires_in=3600)
            except Exception:  # noqa: BLE001 — non-fatal
                signed_url = None
            out.append(
                {
                    "entity_type": "document",
                    "entity_id": doc.id,
                    "context": "generated_pdf",
                    "display_label": f"Generated PDF ({doc.title})",
                    "title": doc.title,
                    "storage_key": doc.storage_key,
                    "download_url": signed_url,
                    "pdf_generated_at": (
                        gen.pdf_generated_at.isoformat()
                        if gen.pdf_generated_at
                        else None
                    ),
                }
            )

    return out


# Builder type: (db, user, item_row_dict) → list[related_entity_dict]
_RELATED_ENTITY_BUILDERS: dict[
    str,
    Callable[[Session, User, dict[str, Any]], list[dict[str, Any]]],
] = {
    "task_triage": _build_task_related,
    "ss_cert_triage": _build_ss_cert_related,
    "cash_receipts_matching_triage": _build_cash_receipts_matching_related,
    # Phase 8c — core accounting migrations batch 1
    "month_end_close_triage": _build_month_end_close_related,
    "ar_collections_triage": _build_ar_collections_related,
    "expense_categorization_triage": _build_expense_categorization_related,
    # Phase 8d.1 — AI-generation-with-approval
    "safety_program_triage": _build_safety_program_related,
}


# ── Orchestration ───────────────────────────────────────────────────


def ask_question(
    db: Session,
    *,
    user: User,
    session_id: str,
    item_id: str,
    question: str,
) -> AskQuestionResponse:
    """Answer a question about the current triage item.

    Flow:
      1. Load session (assert user ownership + active) + queue config.
      2. Locate the `ai_question` panel on the queue config.
      3. Enforce rate limit + max question length.
      4. Fetch current item row via the queue's source.
      5. Build related-entity context via `_RELATED_ENTITY_BUILDERS`.
      6. Render tenant context string (vertical, role, queue name).
      7. Call `intelligence_service.execute` with the panel's
         `ai_prompt_key`.
      8. Parse `{answer, confidence, sources}`; map numeric
         confidence → ConfidenceTier.
      9. Return `AskQuestionResponse`.

    Raises typed `TriageError` subclasses that the API layer
    translates to HTTP. `_RateLimited` surfaces via RateLimited
    sentinel returned from `_check_rate_limit` — caller translates
    to 429 with `retry_after_seconds` in the body.
    """
    # 1. Session + queue config.
    session = _engine.get_session(db, session_id=session_id, user=user)
    if session.ended_at is not None:
        raise SessionNotFound("Session already ended")
    config = _registry.get_config(
        db, company_id=user.company_id, queue_id=session.queue_id
    )
    _engine._check_user_can_access_queue(db, user, config)

    # 2. Find the ai_question panel — use the first one (spec allows
    #    multiple AI panels but seeded queues have exactly one).
    panel = _find_ai_question_panel(config)
    if panel is None:
        raise NoAIQuestionPanel(
            f"Queue {config.queue_id!r} has no ai_question panel configured"
        )
    if not panel.ai_prompt_key:
        raise NoAIQuestionPanel(
            f"ai_question panel on queue {config.queue_id!r} is missing "
            f"ai_prompt_key"
        )

    # 3. Validate + rate limit.
    normalized = (question or "").strip()
    if not normalized:
        raise QuestionTooLong("Question cannot be empty.")
    if len(normalized) > panel.max_question_length:
        raise QuestionTooLong(
            f"Question must be {panel.max_question_length} characters or less."
        )
    # Rate-limit check raises RateLimited on overrun; API layer
    # translates to a structured 429 body.
    _check_rate_limit(user.id)

    # 4. Current item row. We fan out to the same executor the engine
    #    uses for `next_item` — keeps the row shape identical to what
    #    the UI rendered on the page.
    rows = _engine._execute_queue_saved_view(db, config=config, user=user)
    item_row = next(
        (r for r in rows if r.get("id") == item_id), None
    )
    if item_row is None:
        raise ItemNotFound(
            f"Item {item_id!r} not found in queue {config.queue_id!r}"
        )

    # 5. Related entities via per-queue builder (if registered).
    related: list[dict[str, Any]] = []
    if config.source_direct_query_key:
        builder = _RELATED_ENTITY_BUILDERS.get(config.source_direct_query_key)
        if builder is not None:
            try:
                related = builder(db, user, item_row)
            except Exception:
                logger.exception(
                    "Related-entity builder failed for queue %s",
                    config.queue_id,
                )
                related = []  # best-effort — don't block the answer

    # 6. Tenant context string.
    vertical = _resolve_vertical(db, user)
    tenant_context = _format_tenant_context(
        user=user,
        vertical=vertical,
        config=config,
    )

    # 7. Intelligence call.
    import json as _json

    variables = {
        "item_json": _json.dumps(item_row, default=str),
        "user_question": normalized,
        "tenant_context": tenant_context,
        "related_entities_json": _json.dumps(related, default=str),
        # Exposed so the Jinja terminology block (v2) can branch on
        # it. Existing v1 ignores unknown variables.
        "vertical": vertical or "",
        "user_role": _resolve_role_slug(db, user) or "",
        "queue_name": config.queue_name,
        "queue_description": config.description,
        "item_type": config.item_entity_type,
    }
    asked_at = datetime.now(timezone.utc)
    try:
        result = intelligence_service.execute(
            db,
            prompt_key=panel.ai_prompt_key,
            variables=variables,
            company_id=user.company_id,
            caller_module="triage.ai_question",
            caller_entity_type=config.item_entity_type,
            caller_entity_id=item_id,
        )
    except Exception as exc:
        logger.exception("Triage AI question call failed (queue=%s)", config.queue_id)
        raise AIQuestionFailed(f"AI service unavailable: {exc}") from exc

    if result.status != "success":
        raise AIQuestionFailed(
            f"AI call returned status={result.status!r}: "
            f"{result.error_message or '(no message)'}"
        )

    parsed = result.response_parsed
    if not isinstance(parsed, dict):
        # Fallback — try to recover from a raw text response when the
        # prompt was misconfigured with force_json=False.
        raise AIQuestionFailed(
            "AI response was not parseable JSON. "
            "Check that the prompt has force_json=True."
        )

    answer = str(parsed.get("answer") or "").strip()
    if not answer:
        raise AIQuestionFailed("AI response was missing an answer.")
    confidence_score = _coerce_score(parsed.get("confidence"))
    confidence_tier = to_tier(confidence_score)
    source_references = _parse_source_references(parsed.get("sources"))

    return AskQuestionResponse(
        question=normalized,
        answer=answer,
        confidence=confidence_tier,
        confidence_score=confidence_score,
        source_references=source_references,
        latency_ms=int(result.latency_ms or 0),
        asked_at=asked_at,
        execution_id=result.execution_id,
    )


# ── Helpers ─────────────────────────────────────────────────────────


def _find_ai_question_panel(
    config: TriageQueueConfig,
) -> ContextPanelConfig | None:
    for p in config.context_panels:
        if p.panel_type == ContextPanelType.AI_QUESTION:
            return p
    return None


def _resolve_vertical(db: Session, user: User) -> str | None:
    from app.models.company import Company

    co = db.query(Company).filter(Company.id == user.company_id).first()
    return getattr(co, "vertical", None) if co else None


def _resolve_role_slug(db: Session, user: User) -> str | None:
    from app.models.role import Role

    if user.role_id is None:
        return None
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return role.slug if role else None


def _format_tenant_context(
    *, user: User, vertical: str | None, config: TriageQueueConfig
) -> str:
    """One-line context string the existing v1 prompts expect as
    `tenant_context`. v2 prompts still receive this but ALSO have
    access to `vertical` / `user_role` / `queue_name` via the new
    variables — so the context string is belt-and-suspenders for the
    unversioned fallback path.
    """
    parts = [f"queue={config.queue_name}"]
    if vertical:
        parts.append(f"vertical={vertical}")
    first = (user.first_name or "").strip() or "User"
    parts.append(f"user={first}")
    return " | ".join(parts)


def _coerce_score(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_source_references(raw: Any) -> list[SourceReference]:
    """The prompt's response schema declares `sources` as a list; be
    defensive about the shape since prompt output quality can drift."""
    if not isinstance(raw, list):
        return []
    out: list[SourceReference] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        entity_type = str(entry.get("entity_type") or "").strip()
        entity_id = str(entry.get("entity_id") or "").strip()
        display_label = str(
            entry.get("display_label") or entry.get("label") or ""
        ).strip()
        if not (entity_type and entity_id):
            # Reject malformed rows rather than render broken links.
            continue
        snippet_raw = entry.get("snippet")
        snippet = str(snippet_raw).strip() if snippet_raw else None
        out.append(
            SourceReference(
                entity_type=entity_type,
                entity_id=entity_id,
                display_label=display_label or entity_id,
                snippet=snippet,
            )
        )
    return out


__all__ = [
    "AskQuestionResponse",
    "SourceReference",
    "AIQuestionFailed",
    "ItemNotFound",
    "NoAIQuestionPanel",
    "QuestionTooLong",
    "RateLimited",
    "ask_question",
    "list_related_entities",
]


# ── Follow-up 4 — exposed related-entity list for the triage
#    related_entities context panel. Same dispatch table as the
#    Q&A path; returns the raw list without invoking Intelligence.


def list_related_entities(
    db: Session,
    *,
    user: User,
    session_id: str,
    item_id: str,
) -> list[dict[str, Any]]:
    """Fetch the related-entity tiles for the current item.

    Reuses follow-up 2's `_RELATED_ENTITY_BUILDERS` so the triage
    context panel renders the exact same rows that Q&A grounds on —
    no drift between what users peek and what Claude reasons over.
    Returns an empty list when no builder is registered for the
    queue (rather than erroring) so the panel degrades gracefully
    for tenant-custom queues that haven't opted in.
    """
    session = _engine.get_session(db, session_id=session_id, user=user)
    if session.ended_at is not None:
        raise SessionNotFound("Session already ended")
    config = _registry.get_config(
        db, company_id=user.company_id, queue_id=session.queue_id
    )
    _engine._check_user_can_access_queue(db, user, config)

    rows = _engine._execute_queue_saved_view(db, config=config, user=user)
    item_row = next((r for r in rows if r.get("id") == item_id), None)
    if item_row is None:
        raise ItemNotFound(
            f"Item {item_id!r} not found in queue {config.queue_id!r}"
        )

    if not config.source_direct_query_key:
        return []
    builder = _RELATED_ENTITY_BUILDERS.get(config.source_direct_query_key)
    if builder is None:
        return []
    try:
        return builder(db, user, item_row)
    except Exception:
        logger.exception(
            "Related-entity builder failed for queue %s", config.queue_id
        )
        return []
