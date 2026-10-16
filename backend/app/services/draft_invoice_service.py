"""End-of-day draft invoice generation for funeral service orders.

Runs at 18:00 in the scheduler's declared timezone — `BUSINESS_TZ` in
`app/scheduler.py`, i.e. 6 PM Eastern.

⚠️ IT RAN AT 2 PM EASTERN UNTIL 2026-10-16, and "Runs at 6 PM daily" sat here the whole
time. Every `CronTrigger` in `app/scheduler.py` was built without a timezone and so
inherited the container's, which is UTC; 18:00 UTC is 2 PM EDT. See
`docs/investigations/2026-10-16-scheduler-timezone.md`. The hour is NOT restated here
beyond "18:00" — `scheduler.py` owns it, and a second copy of a number is a second thing
to go stale, which is exactly what happened.

WHICH ORDERS IT SELECTS (James's ruling, 2026-10-16 — step 2 of the confirm arc):

An order is selected only if **its service date has arrived in the TENANT'S local time**
and its status is one of `INVOICEABLE_STATUSES` (confirmed or beyond) and it is not
cancelled/postponed and it is not already invoiced.

  * Confirmed with a service date in the future  -> UNTOUCHED. It waits.
  * Confirmed with no service date at all        -> NEVER auto-delivered, and raised as
                                                    an `AgentAlert` so the office is told
                                                    rather than left to notice the
                                                    missing money. See
                                                    `confirmed_without_a_service_date`.

⚠️ "TODAY" IS THE TENANT'S DATE, NOT THE CONTAINER'S. It was `date.today()` until
2026-10-16 — the container's date, UTC in production. A service on Friday evening in
Skaneateles is still Friday locally when UTC has already rolled to Saturday. See
`app/services/tenant_clock.py`, which also records that eight existing readers of
`companies.timezone` disagree about the fallback.

Two modes, controlled by require_driver_status_updates on DeliverySettings:

  False (default — auto-confirm):
    Every selected order that a driver has NOT already marked delivered is marked
    delivered by the system (`delivery_auto_confirmed = True`, `delivered_at = now()`,
    `status -> 'delivered'`) and a draft invoice is created against it.
    ⚠️ `delivery_auto_confirmed = True` is the system recording that it ASSUMED the
    delivery happened. Nothing asks anyone to confirm or correct that assumption today;
    the morning queue reviews the INVOICE, not the delivery.

  True (require driver):
    Only orders already in `DRIVER_CONFIRMED_STATUSES` are invoiced. Everything else is
    gathered into a warning alert for dispatch to follow up. No tenant runs this mode on
    production as of 2026-10-16.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.sales_order import CANCEL_SPELLINGS, SalesOrder

from app.services.job_outcome import JobOutcome
from app.services.tenant_clock import tenant_today

logger = logging.getLogger(__name__)


def _try_send_invoice_email(db: Session, inv: Invoice) -> None:
    """Attempt to generate PDF and send invoice email. Logs errors but never raises."""
    try:
        from app.services.pdf_generation_service import generate_invoice_pdf
        from app.services.email_service import email_service
        from app.models.company import Company
        from datetime import datetime, timezone

        customer = inv.customer
        # Try CRM contacts first, fallback to legacy customer email
        to_emails = []
        if customer and customer.master_company_id:
            try:
                from app.services.crm.contact_service import get_invoice_recipients
                to_emails = get_invoice_recipients(db, customer.master_company_id, inv.company_id)
            except Exception:
                pass
        if not to_emails:
            fallback = (customer.billing_email or customer.email) if customer else None
            to_emails = [fallback] if fallback else []
        if not to_emails:
            logger.warning("Invoice %s: no email on customer — skipping email delivery", inv.number)
            return
        to_email = to_emails[0]  # primary recipient for email_service API

        company = db.query(Company).filter(Company.id == inv.company_id).first()
        company_name = company.name if company else "Your supplier"

        pdf_bytes = generate_invoice_pdf(db, inv.id, inv.company_id)
        if pdf_bytes is None:
            logger.warning("Invoice %s: PDF generation unavailable — email not sent", inv.number)
            return

        from app.utils.company_name_resolver import resolve_customer_name
        result = email_service.send_invoice_email(
            to_email=to_email,
            to_name=resolve_customer_name(customer),
            company_name=company_name,
            invoice_number=inv.number,
            invoice_date=inv.invoice_date.strftime("%B %d, %Y") if inv.invoice_date else "",
            due_date=inv.due_date.strftime("%B %d, %Y") if inv.due_date else "",
            total_amount=f"${inv.total:,.2f}",
            balance_due=f"${inv.balance_remaining:,.2f}",
            deceased_name=inv.deceased_name,
            pdf_attachment=pdf_bytes,
            reply_to=company.email if company else None,
            company_id=inv.company_id,
            db=db,
        )

        # Persist PDF to R2 (non-blocking, idempotent)
        if pdf_bytes:
            try:
                from app.services.document_r2_service import save_generated_document
                from app.models.document import Document as DocModel

                filename = f"Invoice-{inv.number}.pdf"
                r2_key = f"tenants/{inv.company_id}/invoices/{inv.id}/invoice/{filename}"
                existing = db.query(DocModel).filter(DocModel.r2_key == r2_key).first()

                if not existing:
                    save_generated_document(
                        db,
                        company_id=inv.company_id,
                        entity_type="invoice",
                        entity_id=str(inv.id),
                        document_type="invoice",
                        file_name=filename,
                        file_bytes=pdf_bytes,
                        mime_type="application/pdf",
                        generated_by=None,
                        metadata={
                            "invoice_id": str(inv.id),
                            "invoice_number": inv.number,
                            "customer_id": str(inv.customer_id),
                            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                            "due_date": inv.due_date.isoformat() if inv.due_date else None,
                            "total": str(inv.total),
                            "amount_paid": str(inv.amount_paid),
                            "balance_remaining": str(inv.balance_remaining),
                            "status": inv.status,
                            "deceased_name": inv.deceased_name,
                            "payment_terms": inv.payment_terms,
                        },
                    )
            except Exception as e:
                logger.warning(f"Invoice PDF persistence failed (non-blocking): {e}")

        if result.get("success"):
            now = datetime.now(timezone.utc)
            inv.sent_at = now
            inv.sent_to_email = to_email
            db.commit()
            logger.info("Invoice %s emailed to %s", inv.number, to_email)
            # CRM activity log
            try:
                from app.services.crm.activity_log_service import log_system_event
                log_system_event(
                    db, inv.company_id, None,
                    activity_type="invoice",
                    title=f"Invoice #{inv.number} sent — ${inv.total:,.2f}",
                    related_invoice_id=inv.id,
                    customer_id=inv.customer_id,
                )
                db.commit()
            except Exception:
                pass
        else:
            logger.error("Invoice %s email delivery failed", inv.number)
    except Exception as exc:
        logger.error("Invoice %s email send error: %s", getattr(inv, "number", "?"), exc)


# Statuses that count as driver-confirmed delivery
DRIVER_CONFIRMED_STATUSES = {"completed", "shipped", "delivered"}

#: Statuses from which an order may be auto-delivered and invoiced by this batch.
#:
#: ⚠️ `draft` IS NOT HERE AND THAT IS THE WHOLE SAFETY PROPERTY — see
#: `capture/session_service.approve`'s docstring. Everything in this set is at or past
#: `confirmed`, i.e. somebody or something has already asserted the order is real.
#:
#: ⚠️ EXTRACTED TO A CONSTANT 2026-10-16 so `app/services/capture/session_service.py` and
#: the tests can import the ACTUAL list instead of restating it. It had been written out
#: inline here and quoted by hand in two docstrings, which is three places to go stale.
INVOICEABLE_STATUSES = (
    "confirmed",
    "processing",
    "shipped",
    "delivered",
    "completed",
)

#: An order's service date: the day the service happens.
#:
#: ⚠️ ONE EXPRESSION, BECAUSE THREE THINGS NEED THE SAME ANSWER — the selection filter,
#: the "confirmed but undated" alert (which must be its exact complement), and the tests.
#: Written inline as a two-branch OR until 2026-10-16, which meant the undated case was
#: only implicit and could not be reported on.
#:
#: `scheduled_date` is a DATE and is what Opas Approve writes. `required_date` is a
#: TIMESTAMP and is the pre-Opas field; `func.date()` narrows it so the comparison is
#: date-to-date rather than timestamp-to-date.
SERVICE_DATE = func.coalesce(
    SalesOrder.scheduled_date, func.date(SalesOrder.required_date)
)

# Statuses that mean the order is cancelled / won't be invoiced.
# CANCEL_SPELLINGS covers legacy inbound rows defensively; the canonical
# spelling is STATUS_CANCELLED (see app/models/sales_order.py).
SKIP_STATUSES = {*CANCEL_SPELLINGS, "postponed"}

# SHIPMENT BILLING POLICY (audit #2, Session Three — Operator Decision 2,
# pre-staged as option (b) pending the operator's word): orders bill IN
# FULL at first shipment/delivery. This was always the behavior; now it
# is EXPLICIT and stated on the invoice's face. Partial-shipment
# (proportional) billing has no substrate today — quantity_shipped has
# zero writers and deliveries are one-per-order in practice.
SHIPMENT_BILLING_POLICY = "bill_in_full_at_first_shipment"
_POLICY_NOTE = "Billed in full upon shipment."


def _stamp_billing_policy(invoice) -> None:
    """State the shipment-billing policy on the invoice's face."""
    if invoice.notes and _POLICY_NOTE in invoice.notes:
        return
    invoice.notes = f"{invoice.notes}\n{_POLICY_NOTE}" if invoice.notes else _POLICY_NOTE


#: `alert_type` for the undated-order surface. Stable because anything that later wants
#: to filter or dismiss these needs a name that does not move.
UNDATED_ALERT_TYPE = "confirmed_order_without_service_date"


def confirmed_without_a_service_date(db: Session, tenant_id: str) -> list[SalesOrder]:
    """Orders that are confirmed-or-beyond, uncancelled, and have NO service date.

    ⚠️ THE EXACT COMPLEMENT OF THE SELECTION FILTER'S DATE CONDITION, and it is written
    from the same `SERVICE_DATE` expression for that reason. If the two were derived
    separately, an order could fall through both — invisible to the batch AND absent from
    the alert — which is the state this function exists to end.

    Public because the office-facing surface should be able to ask the question directly
    rather than waiting for the nightly alert.
    """
    return (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.status.in_(INVOICEABLE_STATUSES),
            ~SalesOrder.status.in_(SKIP_STATUSES),
            SERVICE_DATE.is_(None),
            (SalesOrder.order_type == "funeral") | (SalesOrder.order_type.is_(None)),
        )
        .order_by(SalesOrder.order_date.asc())
        .all()
    )


def _alert_confirmed_without_a_service_date(
    db: Session, tenant_id: str, already_invoiced_order_ids: set[str]
) -> int:
    """Raise one alert naming every confirmed order the batch can never reach.

    ⚠️ ALREADY-INVOICED ORDERS ARE EXCLUDED. An order that was invoiced by hand is not
    stuck, whatever its dates look like, and alerting on it every night would train the
    office to ignore the alert — which is the failure mode that matters for a surface
    whose whole job is to be noticed.

    ⚠️ BEST-EFFORT, AND NEVER RAISES. This is a report about the run, not part of it: an
    alert that fails must not abort a batch that has invoices to create. It returns the
    count so the caller can put it in the outcome rather than discovering it from logs.
    """
    try:
        stuck = [
            o
            for o in confirmed_without_a_service_date(db, tenant_id)
            if o.id not in already_invoiced_order_ids
        ]
        if not stuck:
            return 0

        from app.services.agent_service import create_alert

        names = ", ".join(
            f"{o.number} ({o.deceased_name or 'no name'})" for o in stuck[:5]
        )
        more = f" and {len(stuck) - 5} more" if len(stuck) > 5 else ""
        create_alert(
            db,
            tenant_id,
            UNDATED_ALERT_TYPE,
            "warning",
            f"{len(stuck)} confirmed order{'s' if len(stuck) != 1 else ''} "
            "with no service date",
            # ⚠️ THE MESSAGE SAYS WHAT WILL HAPPEN IF NOBODY ACTS, not just what is true.
            # "N orders have no service date" is a fact; "they will never be delivered or
            # invoiced until one is set" is the reason to open it.
            f"{names}{more}. An order with no service date is never auto-delivered and "
            "never invoiced — the end-of-day batch cannot see it. Set the service date "
            "on each one, or cancel it.",
            action_label="Review orders",
            action_url="/orders?filter=missing_service_date",
        )
        logger.warning(
            "[DRAFT_INVOICE_GENERATOR] Tenant %s: %d confirmed order(s) have no "
            "service date and can never be invoiced: %s",
            tenant_id, len(stuck), [o.number for o in stuck],
        )
        return len(stuck)
    except Exception as exc:
        logger.error(
            "[DRAFT_INVOICE_GENERATOR] Tenant %s: undated-order alert failed: %s",
            tenant_id, exc,
        )
        return 0


# ---------------------------------------------------------------------------
# Batch job — called once per tenant from the scheduler
# ---------------------------------------------------------------------------


def generate_draft_invoices(db: Session, tenant_id: str) -> JobOutcome:
    """Generate end-of-day draft invoices for a single tenant.

    Idempotent — orders that already have an invoice are skipped.
    """
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, tenant_id)

    # Only run if tenant has enabled end-of-day batch mode
    mode = getattr(settings, "invoice_generation_mode", None)
    if mode != "end_of_day":
        # NOT APPLICABLE to this tenant, which is a different fact from "no
        # work today" below. Both are `no_work`; the detail says which.
        return JobOutcome.nothing_to_do(skipped="mode_not_end_of_day", mode=mode)

    require_driver = getattr(settings, "require_driver_status_updates", False)

    # ⚠️ THE TENANT'S OWN TODAY, NOT THE CONTAINER'S. This was `date.today()` until
    # 2026-10-16, which is the container's date — UTC in production. "The night of the
    # service date" has to mean the night where the service happened: a service on
    # Friday in Skaneateles is still Friday at 23:30 local even though UTC has already
    # rolled over to Saturday. See `tenant_today`.
    today = tenant_today(db, tenant_id)
    tomorrow = today + timedelta(days=1)
    now = datetime.now(timezone.utc)

    # IDs of orders that already have an invoice
    already_invoiced_order_ids = set(
        row[0]
        for row in db.query(Invoice.sales_order_id)
        .filter(
            Invoice.company_id == tenant_id,
            Invoice.sales_order_id.isnot(None),
        )
        .all()
    )

    # Base query: funeral orders whose SERVICE DATE HAS ARRIVED in the tenant's own
    # local time, not cancelled, not yet invoiced.
    #
    # ⚠️ THE SERVICE DATE IS `COALESCE(scheduled_date, date(required_date))`, EXPRESSED
    # ONCE AS `SERVICE_DATE` AND USED EVERYWHERE. It was previously written out as a
    # two-branch OR inline, and the same expression had to be re-derived by hand
    # wherever anything else wanted to ask "what is this order's service date" — so the
    # no-date case was only implicit (neither branch matched) and nothing could report
    # on it. One expression, three consumers: this filter, the no-date surface below,
    # and the tests.
    #
    # ⚠️ `required_date` IS KEPT AS A FALLBACK DELIBERATELY, though Opas writes
    # `scheduled_date`. Pre-Opas and hand-entered orders carry only `required_date`, and
    # dropping the fallback would silently stop invoicing them — a quiet regression in
    # the opposite direction from the one this dispatch is fixing.
    base_q = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            # `completed` joined the net (audit #2 D-3): it is set by full
            # payment (already invoiced — the uninvoiced check skips those)
            # OR by manual PATCH / seeds (possibly never invoiced — these
            # were stranded forever, ~$9,942 on dev). The double-invoice
            # guard + already_invoiced_order_ids make inclusion safe.
            SalesOrder.status.in_(INVOICEABLE_STATUSES),
            ~SalesOrder.status.in_(SKIP_STATUSES),
        )
        # ⚠️ `IS NOT NULL` IS STATED RATHER THAN RELIED UPON. `NULL <= today` is NULL,
        # which SQL treats as not-true, so an order with no service date would be
        # excluded either way. It is written explicitly because the exclusion is a RULE
        # James gave ("confirmed with no service date = never auto-delivered"), not an
        # accident of three-valued logic — and because the no-date surface below has to
        # select exactly the complement of this condition.
        .filter(SERVICE_DATE.isnot(None), SERVICE_DATE <= today)
        .filter(
            (SalesOrder.order_type == "funeral") | (SalesOrder.order_type.is_(None))
        )
    )

    all_today = base_q.all()
    uninvoiced = [o for o in all_today if o.id not in already_invoiced_order_ids]

    # ⚠️ THE NO-DATE ORDERS, SURFACED RATHER THAN SILENTLY SKIPPED. Before this they
    # simply failed to match and nobody was told. An order that is confirmed and has no
    # service date is stuck: it will never be auto-delivered and never be invoiced, and
    # the only way anyone found out was by noticing the money was missing.
    undated = _alert_confirmed_without_a_service_date(
        db, tenant_id, already_invoiced_order_ids
    )

    if not uninvoiced:
        logger.info(
            "[DRAFT_INVOICE_GENERATOR] Tenant %s: no uninvoiced orders for %s "
            "(tenant-local)",
            tenant_id,
            today,
        )
        # ⚠️ `undated` RIDES IN THE DETAIL, so a day that drafted nothing BECAUSE orders
        # are stuck reads differently from a genuinely quiet day. Both are `no_work`;
        # only the detail distinguishes them, and that distinction is the whole reason
        # the undated surface exists.
        return JobOutcome.nothing_to_do(
            orders_due=len(all_today),
            uninvoiced=0,
            mode="end_of_day",
            tenant_today=today.isoformat(),
            confirmed_without_service_date=undated,
        )

    from app.services import sales_service
    from app.services.agent_service import create_alert, log_activity

    if require_driver:
        stats = _generate_require_driver_mode(
            db, tenant_id, uninvoiced, today, tomorrow, now,
            sales_service, create_alert, log_activity,
        )
    else:
        stats = _generate_auto_confirm_mode(
            db, tenant_id, uninvoiced, today, tomorrow, now,
            sales_service, create_alert, log_activity,
        )

    # `succeeded` is DRAFT INVOICES CREATED, deliberately. In require_driver
    # mode a day where no driver confirmed anything drafts nothing and raises an
    # unconfirmed-services alert; that reads as `no_work`, which is accurate --
    # the job's product is invoices -- with `unconfirmed` in the detail saying
    # why there were none. Counting the alert as a success would mix units and
    # make a blocked day look like a productive one.
    return JobOutcome.worked(
        succeeded=stats["created"],
        failed=stats["failed"],
        mode="require_driver" if require_driver else "auto_confirm",
        orders_uninvoiced=len(uninvoiced),
        tenant_today=today.isoformat(),
        confirmed_without_service_date=undated,
        **{k: v for k, v in stats.items() if k != "failed"},
    )


# ---------------------------------------------------------------------------
# Mode: auto-confirm  (require_driver_status_updates = False)
# ---------------------------------------------------------------------------


def _generate_auto_confirm_mode(
    db, tenant_id, uninvoiced, today, tomorrow, now,
    sales_service, create_alert, log_activity,
):
    """Auto-mark unconfirmed orders as delivered, then generate draft invoices."""
    created_invoices: list[Invoice] = []
    # WARNING: `exception_count` is NOT a failure count. It counts invoices
    # carrying DRIVER exceptions -- a business concept -- and sits eight lines
    # above an exception handler it has nothing to do with. `failed_count` is
    # the failure count, authored by (c) commit 2c.
    exception_count = 0
    failed_count = 0
    auto_confirmed_count = 0

    for order in uninvoiced:
        # Auto-confirm if driver hasn't marked it delivered
        if order.status not in DRIVER_CONFIRMED_STATUSES:
            order.status = "delivered"
            order.delivered_at = now
            order.delivery_auto_confirmed = True
            auto_confirmed_count += 1
            logger.debug(
                "[DRAFT_INVOICE_GENERATOR] Auto-confirmed order %s for tenant %s",
                order.number, tenant_id,
            )

        try:
            invoice = sales_service.create_invoice_from_order(
                # System-generated draft (no human actor): nullable attribution,
                # matching create_vault_order. "system" is not a users row →
                # FK violation; created_by + audit actor are both None-tolerant.
                db, tenant_id, None, order.id
            )

            invoice.status = "draft"
            invoice.requires_review = True
            invoice.review_due_date = tomorrow
            invoice.auto_generated = True
            invoice.generation_reason = "end_of_day_batch"
            _stamp_billing_policy(invoice)

            if order.has_driver_exception and order.driver_exceptions:
                invoice.has_exceptions = True
                exception_notes = "; ".join(
                    f"{e.get('reason', 'issue')} — {e.get('notes', '')}"
                    for e in order.driver_exceptions
                )
                invoice.review_notes = f"Driver exception(s): {exception_notes}"
                exception_count += 1

            db.add(invoice)
            created_invoices.append(invoice)

            from app.utils.company_name_resolver import resolve_customer_name as _rcn
            customer_name = _rcn(order.customer) if order.customer else order.customer_id
            log_activity(
                db, tenant_id,
                action_type="draft_invoice_created",
                description=(
                    f"Draft invoice auto-created for {customer_name} "
                    f"(order {order.number}, service {today})"
                ),
                record_type="invoice",
                record_id=invoice.id,
                autonomous=True,
            )

        except Exception as exc:
            failed_count += 1
            logger.error(
                "[DRAFT_INVOICE_GENERATOR] Failed to create draft invoice for order %s: %s",
                order.id, exc,
            )

    if not created_invoices:
        # ⚠️ THIS EARLY RETURN IS THE COLLAPSE. Pre-2c it returned bare `None`
        # whether nothing was eligible or every single creation raised. The
        # failure count travels out of here now, so those two stop being the
        # same event.
        return {"created": 0, "failed": failed_count, "auto_confirmed": auto_confirmed_count}

    db.commit()

    customer_names = _collect_customer_names(db, created_invoices, uninvoiced)
    count = len(created_invoices)
    total_amount = sum(inv.total for inv in created_invoices)

    severity = "warning" if exception_count > 0 else "info"
    title = f"{count} draft invoice{'s' if count != 1 else ''} ready for morning review"

    lines = [
        f"End-of-day batch created {count} draft invoice{'s' if count != 1 else ''} "
        f"for {today} services totaling ${total_amount:,.2f}.",
    ]
    if auto_confirmed_count > 0:
        lines.append(
            f"{auto_confirmed_count} of {count} service{'s were' if auto_confirmed_count != 1 else ' was'} "
            "auto-confirmed (drivers did not update status in the app)."
        )
    lines += ["", "Services:"] + [f"  • {name}" for name in customer_names]

    if exception_count > 0:
        lines.append(
            f"\n⚠ {exception_count} invoice{'s have' if exception_count != 1 else ' has'} "
            "driver exceptions flagged — review before approving."
        )

    create_alert(
        db, tenant_id,
        alert_type="draft_invoices_ready",
        severity=severity,
        title=title,
        message="\n".join(lines),
        action_label="Review invoices",
        action_url="/ar/invoices/review",
    )

    logger.info(
        "[DRAFT_INVOICE_GENERATOR] Tenant %s: created %d draft invoices "
        "(%d auto-confirmed, %d with exceptions, %d failed)",
        tenant_id, count, auto_confirmed_count, exception_count, failed_count,
    )
    return {"created": count, "failed": failed_count,
            "auto_confirmed": auto_confirmed_count,
            "with_driver_exceptions": exception_count}


# ---------------------------------------------------------------------------
# Mode: require driver  (require_driver_status_updates = True)
# ---------------------------------------------------------------------------


def _generate_require_driver_mode(
    db, tenant_id, uninvoiced, today, tomorrow, now,
    sales_service, create_alert, log_activity,
):
    """Only invoice driver-confirmed orders; alert on unconfirmed ones."""
    confirmed = [o for o in uninvoiced if o.status in DRIVER_CONFIRMED_STATUSES]
    unconfirmed = [o for o in uninvoiced if o.status not in DRIVER_CONFIRMED_STATUSES]

    created_invoices: list[Invoice] = []
    # WARNING: `exception_count` is NOT a failure count. It counts invoices
    # carrying DRIVER exceptions -- a business concept -- and sits eight lines
    # above an exception handler it has nothing to do with. `failed_count` is
    # the failure count, authored by (c) commit 2c.
    exception_count = 0
    failed_count = 0

    for order in confirmed:
        try:
            invoice = sales_service.create_invoice_from_order(
                # System-generated draft (no human actor): nullable attribution,
                # matching create_vault_order. "system" is not a users row →
                # FK violation; created_by + audit actor are both None-tolerant.
                db, tenant_id, None, order.id
            )

            invoice.status = "draft"
            invoice.requires_review = True
            invoice.review_due_date = tomorrow
            invoice.auto_generated = True
            invoice.generation_reason = "end_of_day_batch"
            _stamp_billing_policy(invoice)

            if order.has_driver_exception and order.driver_exceptions:
                invoice.has_exceptions = True
                exception_notes = "; ".join(
                    f"{e.get('reason', 'issue')} — {e.get('notes', '')}"
                    for e in order.driver_exceptions
                )
                invoice.review_notes = f"Driver exception(s): {exception_notes}"
                exception_count += 1

            db.add(invoice)
            created_invoices.append(invoice)

            from app.utils.company_name_resolver import resolve_customer_name as _rcn
            customer_name = _rcn(order.customer) if order.customer else order.customer_id
            log_activity(
                db, tenant_id,
                action_type="draft_invoice_created",
                description=(
                    f"Draft invoice auto-created for {customer_name} "
                    f"(order {order.number}, service {today})"
                ),
                record_type="invoice",
                record_id=invoice.id,
                autonomous=True,
            )

        except Exception as exc:
            failed_count += 1
            logger.error(
                "[DRAFT_INVOICE_GENERATOR] Failed to create draft invoice for order %s: %s",
                order.id, exc,
            )

    if created_invoices:
        db.commit()

        customer_names = _collect_customer_names(db, created_invoices, confirmed)
        count = len(created_invoices)
        total_amount = sum(inv.total for inv in created_invoices)

        severity = "warning" if exception_count > 0 else "info"
        title = f"{count} draft invoice{'s' if count != 1 else ''} ready for morning review"
        lines = [
            f"End-of-day batch created {count} draft invoice{'s' if count != 1 else ''} "
            f"for {today} services totaling ${total_amount:,.2f}.",
            "", "Services:",
        ] + [f"  • {name}" for name in customer_names]
        if exception_count > 0:
            lines.append(
                f"\n⚠ {exception_count} invoice{'s have' if exception_count != 1 else ' has'} "
                "driver exceptions flagged — review before approving."
            )

        create_alert(
            db, tenant_id,
            alert_type="draft_invoices_ready",
            severity=severity,
            title=title,
            message="\n".join(lines),
            action_label="Review invoices",
            action_url="/ar/invoices/review",
        )

    # Warn about unconfirmed orders
    if unconfirmed:
        _create_unconfirmed_alert(db, tenant_id, unconfirmed, today, create_alert)

    logger.info(
        "[DRAFT_INVOICE_GENERATOR] Tenant %s: created %d draft invoices, "
        "%d unconfirmed services flagged, %d failed",
        tenant_id, len(created_invoices), len(unconfirmed), failed_count,
    )
    return {"created": len(created_invoices), "failed": failed_count,
            "unconfirmed": len(unconfirmed),
            "with_driver_exceptions": exception_count}


def _create_unconfirmed_alert(db, tenant_id, unconfirmed, today, create_alert):
    from app.utils.company_name_resolver import resolve_customer_name
    count = len(unconfirmed)
    details = []
    for order in unconfirmed:
        cust = resolve_customer_name(order.customer)
        dest = order.ship_to_name or order.ship_to_address or "—"
        details.append(f"  • {cust} — {dest}")

    create_alert(
        db, tenant_id,
        alert_type="unconfirmed_deliveries",
        severity="warning",
        title=f"{count} service{'s' if count != 1 else ''} today not marked delivered",
        message=(
            f"These funeral services were scheduled for {today} but drivers have "
            "not confirmed delivery. Verify completion before approving draft invoices "
            "tomorrow morning.\n\n"
            + "\n".join(details)
        ),
        action_label="Review orders",
        action_url=f"/orders?date={today}&status=unconfirmed",
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _collect_customer_names(db, invoices, orders) -> list[str]:
    from app.utils.company_name_resolver import resolve_customer_name
    names: list[str] = []
    for inv in invoices:
        order = next((o for o in orders if o.id == inv.sales_order_id), None)
        name = resolve_customer_name(order.customer) if (order and order.customer) else "Unknown"
        names.append(name)
    return names


# ---------------------------------------------------------------------------
# Review queue query
# ---------------------------------------------------------------------------


def get_review_queue(db: Session, company_id: str) -> list[dict]:
    """Return all draft invoices pending review, exceptions first."""
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
            Invoice.requires_review.is_(True),
        )
        .order_by(Invoice.has_exceptions.desc(), Invoice.review_due_date.asc())
        .all()
    )

    result = []
    for inv in invoices:
        order = None
        if inv.sales_order_id:
            order = db.query(SalesOrder).filter(SalesOrder.id == inv.sales_order_id).first()

        from app.utils.company_name_resolver import resolve_customer_name
        customer_name = None
        ship_to = None
        if inv.customer:
            customer_name = resolve_customer_name(inv.customer)
        elif order and order.customer:
            customer_name = resolve_customer_name(order.customer)

        if order:
            ship_to = order.ship_to_name or order.ship_to_address

        result.append({
            "id": inv.id,
            "number": inv.number,
            "customer_id": inv.customer_id,
            "customer_name": customer_name,
            "ship_to": ship_to,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "subtotal": inv.subtotal,
            "tax_amount": inv.tax_amount,
            "total": inv.total,
            "has_exceptions": inv.has_exceptions,
            "review_notes": inv.review_notes,
            "review_due_date": inv.review_due_date,
            "auto_generated": inv.auto_generated,
            "generation_reason": inv.generation_reason,
            "sales_order_id": inv.sales_order_id,
            "order_number": order.number if order else None,
            "scheduled_date": str(order.scheduled_date) if order and order.scheduled_date else None,
            "driver_exceptions": order.driver_exceptions if order else None,
            # Delivery confirmation
            "delivery_auto_confirmed": order.delivery_auto_confirmed if order else False,
            "delivered_at": order.delivered_at.isoformat() if (order and order.delivered_at) else None,
            "delivered_by_driver_name": order.delivered_by_driver_name if order else None,
            "deceased_name": inv.deceased_name,
            "invoice_delivery_preference": getattr(inv.customer, "invoice_delivery_preference", "statement_only") if inv.customer else "statement_only",
            "lines": [
                {
                    "id": ln.id,
                    "description": ln.description,
                    "quantity": float(ln.quantity),
                    "unit_price": float(ln.unit_price),
                    "line_total": float(ln.line_total),
                    "product_id": ln.product_id,
                }
                for ln in (inv.lines or [])
            ],
        })
    return result


# ---------------------------------------------------------------------------
# Approve single invoice
# ---------------------------------------------------------------------------


def approve_invoice(
    db: Session, company_id: str, invoice_id: str, user_id: str
) -> Invoice:
    """Post a draft review invoice to AR (status → 'sent', updates customer balance)."""
    from fastapi import HTTPException, status as http_status

    inv = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if inv.status != "draft":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice is already '{inv.status}' — only drafts can be approved",
        )

    now = datetime.now(timezone.utc)
    inv.requires_review = False
    inv.reviewed_by = user_id
    inv.reviewed_at = now
    inv.approved_by = user_id
    inv.approved_at = now
    inv.modified_at = now

    # THE ONE POSTING MOMENT (audit #2 D-2): approval is when the
    # invoice becomes real — the single AR post, via the chokepoint.
    from app.services.sales_service import post_invoice_to_ar
    post_invoice_to_ar(db, company_id, inv)

    # Determine delivery preference and whether to email
    customer = inv.customer
    delivery_pref = getattr(customer, "invoice_delivery_preference", "statement_only") if customer else "statement_only"
    should_email = delivery_pref in ("invoice_immediately", "both")

    if should_email:
        inv.status = "sent"
    else:
        inv.status = "open"

    db.commit()
    db.refresh(inv)

    # Send email after commit so invoice is fully persisted
    if should_email:
        _try_send_invoice_email(db, inv)

    logger.info("Invoice %s approved by user %s (delivery=%s)", inv.number, user_id, delivery_pref)
    return inv


# ---------------------------------------------------------------------------
# Bulk approve — all no-exception drafts
# ---------------------------------------------------------------------------


def approve_all_no_exceptions(
    db: Session, company_id: str, user_id: str
) -> dict:
    """Approve all draft review invoices that have no driver exceptions."""
    pending = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
            Invoice.requires_review.is_(True),
            Invoice.has_exceptions.is_(False),
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    approved_count = 0
    total_amount = Decimal("0")

    to_email_after: list[Invoice] = []

    for inv in pending:
        inv.requires_review = False
        inv.reviewed_by = user_id
        inv.reviewed_at = now
        inv.approved_by = user_id
        inv.approved_at = now
        inv.modified_at = now
        # THE ONE POSTING MOMENT (audit #2 D-2) — same chokepoint as
        # single approve.
        from app.services.sales_service import post_invoice_to_ar
        post_invoice_to_ar(db, company_id, inv)
        delivery_pref = getattr(inv.customer, "invoice_delivery_preference", "statement_only") if inv.customer else "statement_only"
        if delivery_pref in ("invoice_immediately", "both"):
            inv.status = "sent"
            to_email_after.append(inv)
        else:
            inv.status = "open"
        approved_count += 1
        total_amount += inv.total

    db.commit()

    for inv in to_email_after:
        _try_send_invoice_email(db, inv)

    logger.info(
        "Bulk approved %d invoices ($%.2f) for tenant %s by user %s",
        approved_count, total_amount, company_id, user_id,
    )
    return {
        "approved_count": approved_count,
        "total_amount": str(total_amount),
    }


# ---------------------------------------------------------------------------
# Overdue review check — used by alert job
# ---------------------------------------------------------------------------


def get_overdue_review_invoices(db: Session, company_id: str) -> list[Invoice]:
    """Return draft review invoices whose review_due_date has passed."""
    today = date.today()
    return (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
            Invoice.requires_review.is_(True),
            Invoice.review_due_date < today,
        )
        .all()
    )
