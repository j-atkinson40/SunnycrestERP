"""Morning Briefing service — generates role-aware daily briefings via Claude.

Each employee gets a briefing tailored to their primary functional area.
Briefings are cached per-day in the assistant_profiles and employee_briefings tables.
"""

import logging
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import anthropic
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.assistant_profile import AssistantProfile
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.models.employee_briefing import EmployeeBriefing
from app.models.employee_profile import EmployeeProfile
from app.models.customer_payment import CustomerPayment
from app.models.invoice import Invoice
from app.models.production_log_entry import ProductionLogEntry
from app.models.sales_order import SalesOrder
from app.models.sync_log import SyncLog
from app.models.user import User
from app.services.functional_area_service import get_active_areas_for_employee

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRIMARY_CAPABLE_AREAS = [
    "funeral_scheduling",
    "precast_scheduling",
    "invoicing_ar",
    "safety_compliance",
]

BRIEFING_MODEL = "claude-haiku-4-5-20250514"
BRIEFING_MAX_TOKENS = 512

SYSTEM_PROMPTS = {
    "funeral_scheduling": (
        "You are briefing a funeral vault delivery dispatcher. Terse. Action-oriented. "
        "Lead with what needs action today. If all deliveries are assigned and vaulted, "
        "say so briefly. Max 5 items. Each item max 2 sentences. No headers. No bullet "
        "sub-points. Numbered list only. Never use \"I noticed\" or \"It appears.\" "
        "If nothing needs attention: \"All clear. [one sentence current state summary].\""
    ),
    "precast_scheduling": (
        "You are briefing a precast concrete product scheduler. Terse. Action-oriented. "
        "Focus on unscheduled orders and open quotes needing follow-up. Max 5 items. "
        "Each item max 2 sentences. No headers. Numbered list."
    ),
    "invoicing_ar": (
        "You are briefing an office manager on accounts receivable. Terse. Numbers-focused. "
        "Lead with what needs collection action. Flag sync errors immediately. Max 5 items. "
        "Each item max 2 sentences. Numbered list."
    ),
    "safety_compliance": (
        "You are briefing a safety manager. Terse. Compliance-focused. Lead with overdue "
        "items and open incidents. Flag compliance score drops. Max 5 items. Each item "
        "max 2 sentences. Numbered list."
    ),
    "full_admin": (
        "You are briefing a business owner on their operation. Terse. Business-focused. "
        "Lead with financial position then operational flags. One sentence on revenue trend. "
        "Max 5 items. Each item max 2 sentences. Numbered list."
    ),
}


# ---------------------------------------------------------------------------
# A) Primary area determination
# ---------------------------------------------------------------------------


def determine_primary_area(
    functional_areas: list[str],
    area_definitions: list[dict],
) -> str | None:
    """Pick the single primary area for briefing generation."""
    if "full_admin" in functional_areas:
        return "full_admin"

    candidates = [a for a in functional_areas if a in PRIMARY_CAPABLE_AREAS]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Pick the one with most nav_items (proxy for responsibility)
    def nav_count(area_key: str) -> int:
        defn = next(
            (d for d in area_definitions if d.get("area_key") == area_key), None
        )
        return len(defn.get("nav_items", [])) if defn else 0

    return max(candidates, key=nav_count)


# ---------------------------------------------------------------------------
# B) Context payload builders
# ---------------------------------------------------------------------------


def _build_funeral_scheduling_context(
    db: Session, company_id: str
) -> dict:
    """Gather funeral delivery context for today and tomorrow."""
    today = date.today()
    tomorrow = today + timedelta(days=1)

    try:
        # Today's deliveries
        today_deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == company_id,
                Delivery.requested_date == today,
                Delivery.status != "cancelled",
            )
            .all()
        )

        # Tomorrow's deliveries
        tomorrow_deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == company_id,
                Delivery.requested_date == tomorrow,
                Delivery.status != "cancelled",
            )
            .all()
        )

        # Unscheduled deliveries within 5 days
        five_days = today + timedelta(days=5)
        unscheduled = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == company_id,
                Delivery.status == "pending",
                Delivery.requested_date <= five_days,
                Delivery.requested_date >= today,
            )
            .all()
        )

        def _delivery_summary(d: Delivery) -> dict:
            customer_name = None
            if d.customer_id:
                try:
                    cust = db.query(Customer.name).filter(Customer.id == d.customer_id).first()
                    customer_name = cust[0] if cust else None
                except Exception:
                    pass
            return {
                "id": d.id,
                "customer_name": customer_name,
                "delivery_type": d.delivery_type,
                "status": d.status,
                "priority": d.priority,
                "requested_date": str(d.requested_date) if d.requested_date else None,
                "window_start": str(d.required_window_start) if d.required_window_start else None,
                "window_end": str(d.required_window_end) if d.required_window_end else None,
                "assigned_driver_id": d.assigned_driver_id,
                "delivery_address": d.delivery_address,
                "special_instructions": d.special_instructions,
                "type_config": d.type_config,
            }

        # Legacy proofs needing attention
        legacy_pending_review = 0
        legacy_approved_today = 0
        try:
            from app.models.legacy_proof import LegacyProof

            legacy_pending_review = (
                db.query(func.count(LegacyProof.id))
                .filter(
                    LegacyProof.company_id == company_id,
                    LegacyProof.status == "proof_generated",
                )
                .scalar() or 0
            )
            legacy_approved_today = (
                db.query(func.count(LegacyProof.id))
                .filter(
                    LegacyProof.company_id == company_id,
                    LegacyProof.status == "approved",
                    LegacyProof.approved_at >= datetime.combine(today, datetime.min.time()),
                )
                .scalar() or 0
            )
        except Exception:
            pass

        # CRM follow-up reminders — return detailed items with links
        overdue_followups = 0
        today_followups = 0
        follow_up_items = []
        try:
            from app.models.activity_log import ActivityLog
            from app.models.company_entity import CompanyEntity as _CE_fu

            overdue_followups = (
                db.query(func.count(ActivityLog.id))
                .filter(
                    ActivityLog.tenant_id == company_id,
                    ActivityLog.follow_up_completed == False,
                    ActivityLog.follow_up_date < today,
                    ActivityLog.follow_up_date.isnot(None),
                )
                .scalar() or 0
            )
            today_followups = (
                db.query(func.count(ActivityLog.id))
                .filter(
                    ActivityLog.tenant_id == company_id,
                    ActivityLog.follow_up_completed == False,
                    ActivityLog.follow_up_date == today,
                )
                .scalar() or 0
            )

            # Detailed items for briefing display (overdue + today, max 10)
            fu_rows = (
                db.query(ActivityLog, _CE_fu)
                .join(_CE_fu, ActivityLog.master_company_id == _CE_fu.id)
                .filter(
                    ActivityLog.tenant_id == company_id,
                    ActivityLog.follow_up_completed == False,
                    ActivityLog.follow_up_date.isnot(None),
                    ActivityLog.follow_up_date <= today,
                )
                .order_by(ActivityLog.follow_up_date.asc())
                .limit(10)
                .all()
            )
            for activity, entity in fu_rows:
                follow_up_items.append({
                    "activity_id": activity.id,
                    "master_company_id": entity.id,
                    "company_name": entity.name,
                    "title": activity.title,
                    "follow_up_date": activity.follow_up_date.isoformat() if activity.follow_up_date else None,
                    "overdue": activity.follow_up_date < today if activity.follow_up_date else False,
                    "action_url": f"/crm/companies/{entity.id}?tab=activity",
                })
        except Exception:
            pass

        # At-risk accounts (only new detections)
        at_risk_accounts = []
        try:
            from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
            from app.models.company_entity import CompanyEntity as _CE

            at_risk = (
                db.query(ManufacturerCompanyProfile, _CE)
                .join(_CE, ManufacturerCompanyProfile.master_company_id == _CE.id)
                .filter(
                    ManufacturerCompanyProfile.company_id == company_id,
                    ManufacturerCompanyProfile.health_score == "at_risk",
                )
                .filter(
                    (ManufacturerCompanyProfile.last_briefed_at.is_(None)) |
                    (ManufacturerCompanyProfile.health_last_calculated > ManufacturerCompanyProfile.last_briefed_at)
                )
                .limit(5)
                .all()
            )
            for profile, entity in at_risk:
                reasons = profile.health_reasons or []
                at_risk_accounts.append({
                    "company_name": entity.name,
                    "company_id": entity.id,
                    "reason": reasons[0] if reasons else "At risk",
                })
                profile.last_briefed_at = datetime.now(timezone.utc)
            if at_risk:
                db.commit()
        except Exception:
            pass

        result = {
            "today_deliveries": [_delivery_summary(d) for d in today_deliveries],
            "today_count": len(today_deliveries),
            "tomorrow_deliveries": [_delivery_summary(d) for d in tomorrow_deliveries],
            "tomorrow_count": len(tomorrow_deliveries),
            "unscheduled_within_5_days": [_delivery_summary(d) for d in unscheduled],
            "unscheduled_count": len(unscheduled),
            "legacy_proofs_pending_review": legacy_pending_review,
            "legacy_proofs_approved_today": legacy_approved_today,
            "crm_overdue_followups": overdue_followups,
            "crm_today_followups": today_followups,
            "crm_follow_up_items": follow_up_items,
            "crm_at_risk_accounts": at_risk_accounts,
        }
        return result
    except Exception as e:
        logger.warning("Error building funeral scheduling context: %s", e)
        return {
            "today_deliveries": [],
            "today_count": 0,
            "tomorrow_deliveries": [],
            "tomorrow_count": 0,
            "unscheduled_within_5_days": [],
            "unscheduled_count": 0,
        }


def _order_is_auto_confirmed(db: Session, order_id: str) -> bool:
    """Return True if the linked sales order was auto-confirmed by the system."""
    from app.models.sales_order import SalesOrder
    row = db.query(SalesOrder.delivery_auto_confirmed).filter(SalesOrder.id == order_id).first()
    return bool(row and row[0])


def _build_draft_invoice_context(db: Session, company_id: str) -> dict:
    """Return summary of draft invoices pending morning review."""
    try:
        pending = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == company_id,
                Invoice.status == "draft",
                Invoice.requires_review.is_(True),
            )
            .all()
        )
        if not pending:
            return {"count": 0, "total_amount": "0", "exception_count": 0, "customers": []}

        total = sum(inv.total for inv in pending)
        exception_count = sum(1 for inv in pending if inv.has_exceptions)
        customers: list[str] = []
        for inv in pending:
            name = None
            if inv.customer_id:
                try:
                    cust = db.query(Customer.name).filter(Customer.id == inv.customer_id).first()
                    name = cust[0] if cust else None
                except Exception:
                    pass
            customers.append(name or "Unknown")

        auto_confirmed_count = sum(
            1 for inv in pending
            if inv.sales_order_id and _order_is_auto_confirmed(db, inv.sales_order_id)
        )

        return {
            "count": len(pending),
            "total_amount": str(total),
            "exception_count": exception_count,
            "auto_confirmed_count": auto_confirmed_count,
            "customers": customers,
        }
    except Exception as e:
        logger.warning("Error building draft invoice context: %s", e)
        return {"count": 0, "total_amount": "0", "exception_count": 0, "auto_confirmed_count": 0, "customers": []}


def _build_top_overdue_accounts(db: Session, company_id: str, overdue_invoices: list) -> list[dict]:
    """Build top overdue accounts list, consolidating billing group members."""
    from app.models.company_entity import CompanyEntity

    now = datetime.now(timezone.utc)
    zero = Decimal("0")
    per_customer: dict[str, dict] = {}

    # Build billing group map
    billing_group_map: dict[str, str] = {}  # customer_id → display_key
    group_names: dict[str, str] = {}

    try:
        grouped = (
            db.query(Customer)
            .filter(
                Customer.company_id == company_id,
                Customer.billing_group_customer_id.isnot(None),
            )
            .all()
        )
        for c in grouped:
            if c.master_company_id:
                ce = db.query(CompanyEntity).filter(CompanyEntity.id == c.master_company_id).first()
                if ce and ce.parent_company_id:
                    parent = db.query(CompanyEntity).filter(CompanyEntity.id == ce.parent_company_id).first()
                    if parent and parent.billing_preference == "consolidated_single_payer":
                        billing_group_map[c.id] = c.billing_group_customer_id
                        group_names[c.billing_group_customer_id] = parent.name
    except Exception:
        pass

    for inv in overdue_invoices:
        remaining = inv.total - inv.amount_paid
        if remaining <= zero:
            continue
        days = (now - inv.due_date).days if inv.due_date else 0

        display_key = billing_group_map.get(inv.customer_id, inv.customer_id)
        if display_key not in per_customer:
            name = group_names.get(display_key, inv.customer.name if inv.customer else "Unknown")
            per_customer[display_key] = {"name": name, "total": zero, "max_days": 0, "locations": set()}

        per_customer[display_key]["total"] += remaining
        if days > per_customer[display_key]["max_days"]:
            per_customer[display_key]["max_days"] = days
        if inv.customer_id != display_key:
            per_customer[display_key]["locations"].add(inv.customer.name if inv.customer else "")

    sorted_accounts = sorted(per_customer.values(), key=lambda x: x["total"], reverse=True)[:10]
    result = []
    for a in sorted_accounts:
        entry = {
            "name": a["name"],
            "overdue_amount": str(a["total"]),
            "max_days_overdue": a["max_days"],
        }
        if a["locations"]:
            entry["location_breakdown"] = list(a["locations"])
        result.append(entry)
    return result


def _build_invoicing_ar_context(
    db: Session, company_id: str
) -> dict:
    """Gather AR / invoicing context."""
    today = date.today()
    now = datetime.now(timezone.utc)

    try:
        # Overdue invoices by age bucket
        overdue_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == company_id,
                Invoice.status.in_(["sent", "partial", "overdue"]),
                Invoice.due_date < now,
            )
            .all()
        )

        bucket_30 = Decimal("0")
        bucket_60 = Decimal("0")
        bucket_90_plus = Decimal("0")
        for inv in overdue_invoices:
            days_overdue = (now - inv.due_date).days if inv.due_date else 0
            remaining = inv.total - inv.amount_paid
            if days_overdue <= 30:
                bucket_30 += remaining
            elif days_overdue <= 60:
                bucket_60 += remaining
            else:
                bucket_90_plus += remaining

        total_overdue = bucket_30 + bucket_60 + bucket_90_plus

        # Top overdue accounts (consolidated for billing groups)
        top_overdue = _build_top_overdue_accounts(db, company_id, overdue_invoices)

        # Payments received today
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        today_end = today_start + timedelta(days=1)
        payments_today = (
            db.query(func.count(Invoice.id))
            .filter(
                Invoice.company_id == company_id,
                Invoice.status == "paid",
                Invoice.modified_at >= today_start,
                Invoice.modified_at < today_end,
            )
            .scalar()
        ) or 0

        # Uninvoiced completed sales orders
        uninvoiced_orders = (
            db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.status == "completed",
                ~SalesOrder.id.in_(
                    db.query(Invoice.sales_order_id).filter(
                        Invoice.sales_order_id.isnot(None),
                        Invoice.company_id == company_id,
                    )
                ),
            )
            .scalar()
        ) or 0

        # Recent sync errors (last 24h)
        sync_errors = (
            db.query(SyncLog)
            .filter(
                SyncLog.company_id == company_id,
                SyncLog.status == "failed",
                SyncLog.created_at >= now - timedelta(hours=24),
            )
            .all()
        )

        # Draft invoices pending morning review
        draft_invoices_pending = _build_draft_invoice_context(db, company_id)

        # Payments yesterday
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start
        recent_payments = (
            db.query(CustomerPayment)
            .filter(
                CustomerPayment.company_id == company_id,
                CustomerPayment.payment_date >= yesterday_start.date(),
                CustomerPayment.payment_date < yesterday_end.date(),
                CustomerPayment.deleted_at.is_(None),
            )
            .all()
        )
        payments_yesterday = {
            "count": len(recent_payments),
            "total_amount": sum(float(p.total_amount) for p in recent_payments),
        }

        # Outstanding discounts expiring
        week_end = today + timedelta(days=7)
        expiring_today_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == company_id,
                Invoice.discount_deadline == today,
                Invoice.status.notin_(["paid", "void"]),
            )
            .all()
        )
        expiring_week_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == company_id,
                Invoice.discount_deadline > today,
                Invoice.discount_deadline <= week_end,
                Invoice.status.notin_(["paid", "void"]),
            )
            .all()
        )
        outstanding_discounts = {
            "expiring_today": {
                "count": len(expiring_today_invoices),
                "total_discount_value": sum(
                    float(inv.total) * 0.05
                    for inv in expiring_today_invoices
                    if inv.total
                ),
            },
            "expiring_this_week": {
                "count": len(expiring_week_invoices),
                "total_discount_value": sum(
                    float(inv.total) * 0.05
                    for inv in expiring_week_invoices
                    if inv.total
                ),
            },
        }

        # Vault inventory status for purchase/hybrid tenants
        vault_inventory_status = None
        try:
            from app.models.company import Company as CompanyModel
            from app.models.vault_supplier import VaultSupplier
            from app.services.vault_inventory_service import build_suggested_order

            company_obj = db.query(CompanyModel).filter(CompanyModel.id == company_id).first()
            vault_mode = (company_obj.vault_fulfillment_mode or "produce") if company_obj else "produce"

            if vault_mode in ("purchase", "hybrid"):
                suggestion = build_suggested_order(db, company_id)
                active_pos_count = (
                    db.query(func.count(SalesOrder.id)).filter(
                        SalesOrder.company_id == company_id,
                        SalesOrder.status.in_(["sent", "partial"]),
                    ).scalar()
                    or 0
                )

                vault_inventory_status = {
                    "needs_order_today": suggestion.get("urgent", False) if suggestion else False,
                    "needs_order_this_week": (
                        any(
                            item.get("reason") in ("below_reorder_point", "urgent")
                            for item in (suggestion.get("suggested_items") or [])
                        )
                        if suggestion
                        else False
                    ),
                    "active_pos": active_pos_count,
                    "next_delivery": suggestion.get("next_delivery") if suggestion else None,
                    "order_deadline": suggestion.get("order_deadline") if suggestion else None,
                }
        except Exception as e:
            logger.debug("Could not build vault inventory context: %s", e)
            vault_inventory_status = None

        return {
            "overdue_total": str(total_overdue),
            "overdue_0_30": str(bucket_30),
            "overdue_31_60": str(bucket_60),
            "overdue_90_plus": str(bucket_90_plus),
            "overdue_invoice_count": len(overdue_invoices),
            "top_overdue_accounts": top_overdue,
            "payments_today_count": payments_today,
            "payments_yesterday": payments_yesterday,
            "outstanding_discounts": outstanding_discounts,
            "uninvoiced_completed_orders": uninvoiced_orders,
            "sync_errors_24h": [
                {
                    "sync_type": s.sync_type,
                    "error_message": (s.error_message or "")[:200],
                    "created_at": str(s.created_at),
                }
                for s in sync_errors[:5]
            ],
            "sync_error_count": len(sync_errors),
            "draft_invoices_pending": draft_invoices_pending,
            "vault_inventory_status": vault_inventory_status,
        }
    except Exception as e:
        logger.warning("Error building invoicing AR context: %s", e)
        return {
            "overdue_total": "0",
            "overdue_0_30": "0",
            "overdue_31_60": "0",
            "overdue_90_plus": "0",
            "overdue_invoice_count": 0,
            "payments_today_count": 0,
            "payments_yesterday": {"count": 0, "total_amount": 0},
            "outstanding_discounts": {
                "expiring_today": {"count": 0, "total_discount_value": 0},
                "expiring_this_week": {"count": 0, "total_discount_value": 0},
            },
            "uninvoiced_completed_orders": 0,
            "sync_errors_24h": [],
            "sync_error_count": 0,
            "draft_invoices_pending": {"count": 0, "total_amount": "0", "exception_count": 0, "auto_confirmed_count": 0, "customers": []},
            "vault_inventory_status": None,
        }


def _build_safety_compliance_context(
    db: Session, company_id: str
) -> dict:
    """Gather safety compliance context."""
    today = date.today()

    try:
        from app.models.safety_inspection import SafetyInspection, SafetyInspectionResult
        from app.models.safety_incident import SafetyIncident
        from app.models.safety_training import EmployeeTrainingRecord

        # Overdue inspection corrective actions
        overdue_actions = (
            db.query(func.count(SafetyInspectionResult.id))
            .filter(
                SafetyInspectionResult.company_id == company_id,
                SafetyInspectionResult.corrective_action_required.is_(True),
                SafetyInspectionResult.corrective_action_completed_at.is_(None),
                SafetyInspectionResult.corrective_action_due_date < today,
            )
            .scalar()
        ) or 0

        # Open incidents (not closed)
        open_incidents = (
            db.query(func.count(SafetyIncident.id))
            .filter(
                SafetyIncident.company_id == company_id,
                SafetyIncident.status.notin_(["closed", "resolved"]),
            )
            .scalar()
        ) or 0

        # Overdue training (expiry_date in the past, no newer record)
        overdue_training = (
            db.query(func.count(EmployeeTrainingRecord.id))
            .filter(
                EmployeeTrainingRecord.company_id == company_id,
                EmployeeTrainingRecord.expiry_date < today,
            )
            .scalar()
        ) or 0

        # Recent inspections with failures
        failed_inspections = (
            db.query(func.count(SafetyInspection.id))
            .filter(
                SafetyInspection.company_id == company_id,
                SafetyInspection.overall_result == "fail",
                SafetyInspection.inspection_date >= today - timedelta(days=7),
            )
            .scalar()
        ) or 0

        return {
            "overdue_corrective_actions": overdue_actions,
            "open_incidents": open_incidents,
            "overdue_training_records": overdue_training,
            "failed_inspections_7d": failed_inspections,
        }
    except Exception as e:
        logger.warning("Error building safety compliance context: %s", e)
        return {
            "overdue_corrective_actions": 0,
            "open_incidents": 0,
            "overdue_training_records": 0,
            "failed_inspections_7d": 0,
        }


def _check_kb_extension_notifications(db: Session, company_id: str) -> dict:
    """Check for new KB extension notifications to include in briefing."""
    try:
        from app.services.kb_setup_service import get_pending_notifications

        notifications = get_pending_notifications(db, company_id)
        if not notifications:
            return {}

        ext_names = [n["extension_name"] for n in notifications]
        return {
            "kb_new_extensions": ext_names,
            "kb_notification_count": len(notifications),
        }
    except Exception:
        return {}


def _build_call_summary(db: Session, company_id: str) -> dict:
    """Build yesterday's call summary for the morning briefing."""
    try:
        from app.models.ringcentral_call_log import RingCentralCallLog
        from app.models.ringcentral_call_extraction import RingCentralCallExtraction
    except ImportError:
        return {}

    yesterday = date.today() - timedelta(days=1)
    yesterday_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
    yesterday_end = datetime.combine(yesterday + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

    try:
        base = db.query(RingCentralCallLog).filter(
            RingCentralCallLog.tenant_id == company_id,
            RingCentralCallLog.started_at >= yesterday_start,
            RingCentralCallLog.started_at < yesterday_end,
        )

        total_calls = base.count()
        if total_calls == 0:
            return {}

        answered = base.filter(RingCentralCallLog.call_status == "completed").count()
        missed = base.filter(RingCentralCallLog.call_status == "missed").count()
        voicemails = base.filter(RingCentralCallLog.call_status == "voicemail").count()
        orders_created = base.filter(RingCentralCallLog.order_created.is_(True)).count()

        # Calls still needing follow-up: missed + voicemails without orders
        followup_needed = (
            base.filter(
                RingCentralCallLog.call_status.in_(["missed", "voicemail"]),
                RingCentralCallLog.order_created.is_(False),
            ).count()
        )

        return {
            "calls_yesterday": {
                "total": total_calls,
                "answered": answered,
                "missed": missed,
                "voicemails": voicemails,
                "orders_created": orders_created,
                "followup_needed": followup_needed,
            }
        }
    except Exception as e:
        logger.debug("Call summary build failed: %s", e)
        return {}


def _build_executive_context(
    db: Session, company_id: str
) -> dict:
    """Gather executive / full_admin overview context."""
    today = date.today()
    now = datetime.now(timezone.utc)
    week_start = today - timedelta(days=today.weekday())  # Monday

    try:
        # Revenue this week (sum of invoice totals created this week)
        week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
        revenue_week = (
            db.query(func.coalesce(func.sum(Invoice.total), 0))
            .filter(
                Invoice.company_id == company_id,
                Invoice.invoice_date >= week_start_dt,
                Invoice.status.notin_(["void", "draft"]),
            )
            .scalar()
        ) or Decimal("0")

        # Outstanding AR
        outstanding_ar = (
            db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0))
            .filter(
                Invoice.company_id == company_id,
                Invoice.status.in_(["sent", "partial", "overdue"]),
            )
            .scalar()
        ) or Decimal("0")

        # Today's delivery count
        today_deliveries = (
            db.query(func.count(Delivery.id))
            .filter(
                Delivery.company_id == company_id,
                Delivery.requested_date == today,
                Delivery.status != "cancelled",
            )
            .scalar()
        ) or 0

        # Active orders
        active_orders = (
            db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.status.in_(["confirmed", "processing"]),
            )
            .scalar()
        ) or 0

        # Sync errors
        sync_errors_24h = (
            db.query(func.count(SyncLog.id))
            .filter(
                SyncLog.company_id == company_id,
                SyncLog.status == "failed",
                SyncLog.created_at >= now - timedelta(hours=24),
            )
            .scalar()
        ) or 0

        call_summary = _build_call_summary(db, company_id)

        # KB extension notifications
        kb_notifications = _check_kb_extension_notifications(db, company_id)

        return {
            "revenue_this_week": str(revenue_week),
            "outstanding_ar": str(outstanding_ar),
            "today_delivery_count": today_deliveries,
            "active_orders": active_orders,
            "sync_errors_24h": sync_errors_24h,
            **call_summary,
            **kb_notifications,
        }
    except Exception as e:
        logger.warning("Error building executive context: %s", e)
        return {
            "revenue_this_week": "0",
            "outstanding_ar": "0",
            "today_delivery_count": 0,
            "active_orders": 0,
            "sync_errors_24h": 0,
        }


def _build_precast_scheduling_context(
    db: Session, company_id: str
) -> dict:
    """Gather precast product scheduling context."""
    today = date.today()
    five_days = today + timedelta(days=5)

    try:
        # Pending precast deliveries
        pending = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == company_id,
                Delivery.status == "pending",
                Delivery.requested_date <= five_days,
                Delivery.requested_date >= today,
            )
            .all()
        )

        today_deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == company_id,
                Delivery.requested_date == today,
                Delivery.status != "cancelled",
            )
            .all()
        )

        def _delivery_summary(d: Delivery) -> dict:
            customer_name = None
            if d.customer_id:
                try:
                    cust = db.query(Customer.name).filter(Customer.id == d.customer_id).first()
                    customer_name = cust[0] if cust else None
                except Exception:
                    pass
            return {
                "id": d.id,
                "customer_name": customer_name,
                "delivery_type": d.delivery_type,
                "status": d.status,
                "priority": d.priority,
                "requested_date": str(d.requested_date) if d.requested_date else None,
                "type_config": d.type_config,
                "special_instructions": d.special_instructions,
            }

        # Active sales orders
        active_orders = (
            db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.status.in_(["confirmed", "processing"]),
            )
            .scalar()
        ) or 0

        return {
            "today_deliveries": [_delivery_summary(d) for d in today_deliveries],
            "today_count": len(today_deliveries),
            "unscheduled_within_5_days": [_delivery_summary(d) for d in pending],
            "unscheduled_count": len(pending),
            "active_orders": active_orders,
        }
    except Exception as e:
        logger.warning("Error building precast scheduling context: %s", e)
        return {
            "today_deliveries": [],
            "today_count": 0,
            "unscheduled_within_5_days": [],
            "unscheduled_count": 0,
            "active_orders": 0,
        }


CONTEXT_BUILDERS = {
    "funeral_scheduling": _build_funeral_scheduling_context,
    "precast_scheduling": _build_precast_scheduling_context,
    "invoicing_ar": _build_invoicing_ar_context,
    "safety_compliance": _build_safety_compliance_context,
    "full_admin": _build_executive_context,
}


# ---------------------------------------------------------------------------
# Historical order context (appended to briefing context when available)
# ---------------------------------------------------------------------------


def _get_historical_context(db: Session, company_id: str) -> dict | None:
    """Return seasonal intelligence from historical order data if available.

    Returns None if no historical import exists.
    """
    try:
        from app.models.historical_order_import import HistoricalOrder, HistoricalOrderImport
        from sqlalchemy import func as _func

        # Check if any historical data exists
        count = (
            db.query(_func.count(HistoricalOrder.id))
            .filter(HistoricalOrder.company_id == company_id)
            .scalar()
            or 0
        )
        if count == 0:
            return None

        today = date.today()
        current_month = today.month

        # Compute average daily orders from history (exclude current month if limited data)
        month_rows = (
            db.query(
                _func.extract("month", HistoricalOrder.scheduled_date).label("mo"),
                _func.count().label("cnt"),
            )
            .filter(
                HistoricalOrder.company_id == company_id,
                HistoricalOrder.scheduled_date.isnot(None),
            )
            .group_by("mo")
            .all()
        )

        if not month_rows:
            return None

        month_counts = {int(row.mo): row.cnt for row in month_rows}
        avg_count = sum(month_counts.values()) / len(month_counts)
        avg_daily = round(avg_count / 30.0, 1)

        current_month_count = month_counts.get(current_month, 0)
        is_peak = current_month_count > avg_count * 1.3

        # Read seasonal pattern from company settings if available
        peak_months: list[int] = []
        try:
            from app.models.company import Company as _Company
            company = db.query(_Company).filter(_Company.id == company_id).first()
            if company:
                seasonal = company.settings.get("seasonal_pattern", {})
                peak_months = seasonal.get("peak_months", [])
        except Exception:
            pass

        month_names = [
            "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        peak_month_names = [month_names[m] for m in peak_months if 1 <= m <= 12]

        return {
            "avg_daily_orders": avg_daily,
            "total_historical_orders": count,
            "peak_season_alert": is_peak,
            "peak_month_names": peak_month_names,
            "current_month_name": month_names[current_month],
            "current_month_avg_orders": round(current_month_count / 30.0, 1),
        }

    except Exception as exc:
        logger.debug("Could not build historical context: %s", exc)
        return None


# ---------------------------------------------------------------------------
# C) Secondary area critical items
# ---------------------------------------------------------------------------


def get_secondary_critical_items(
    db: Session, company_id: str, area: str, all_areas: list[str]
) -> list[dict]:
    """Return critical-only items for secondary areas."""
    items: list[dict] = []

    try:
        if area == "production_log":
            yesterday = date.today() - timedelta(days=1)
            # Skip weekends
            if yesterday.weekday() < 5:
                count = (
                    db.query(func.count(ProductionLogEntry.id))
                    .filter(
                        ProductionLogEntry.tenant_id == company_id,
                        ProductionLogEntry.log_date == yesterday,
                    )
                    .scalar()
                ) or 0
                if count == 0:
                    items.append({
                        "priority": "critical",
                        "text": "No production logged yesterday.",
                    })

        elif area == "invoicing_ar" and area not in []:
            # Check for sync errors
            now = datetime.now(timezone.utc)
            sync_errors = (
                db.query(func.count(SyncLog.id))
                .filter(
                    SyncLog.company_id == company_id,
                    SyncLog.status == "failed",
                    SyncLog.created_at >= now - timedelta(hours=24),
                )
                .scalar()
            ) or 0
            if sync_errors > 0:
                items.append({
                    "priority": "critical",
                    "text": f"{sync_errors} accounting sync error(s) in the last 24 hours.",
                })

        elif area == "safety_compliance":
            try:
                from app.models.safety_incident import SafetyIncident

                open_incidents = (
                    db.query(func.count(SafetyIncident.id))
                    .filter(
                        SafetyIncident.company_id == company_id,
                        SafetyIncident.status.notin_(["closed", "resolved"]),
                    )
                    .scalar()
                ) or 0
                if open_incidents > 0:
                    items.append({
                        "priority": "critical",
                        "text": f"{open_incidents} open safety incident(s) require attention.",
                    })
            except Exception:
                pass

    except Exception as e:
        logger.warning("Error getting secondary critical items for %s: %s", area, e)

    return items


# ---------------------------------------------------------------------------
# D) Claude API call
# ---------------------------------------------------------------------------


def _call_briefing_api(
    system_prompt: str, user_prompt: str
) -> tuple[str, dict, int]:
    """Call Claude for briefing generation. Returns (text, usage_dict, duration_ms).

    Falls back to a simple message if the API key is not configured.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set; returning fallback briefing")
        return (
            "1. AI briefing unavailable — API key not configured. Check system settings.",
            {"input_tokens": 0, "output_tokens": 0},
            0,
        )

    start = time.monotonic()
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=BRIEFING_MODEL,
            max_tokens=BRIEFING_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        text = message.content[0].text
        usage = {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }
        return text, usage, duration_ms

    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit during briefing generation")
        return (
            "1. Briefing temporarily unavailable due to rate limiting. Try again shortly.",
            {"input_tokens": 0, "output_tokens": 0},
            int((time.monotonic() - start) * 1000),
        )
    except anthropic.AuthenticationError:
        logger.error("Anthropic auth failed during briefing generation")
        return (
            "1. Briefing unavailable — authentication error. Contact admin.",
            {"input_tokens": 0, "output_tokens": 0},
            int((time.monotonic() - start) * 1000),
        )
    except Exception as e:
        logger.error("Unexpected error during briefing generation: %s", e)
        return (
            "1. Briefing generation failed. The system will retry on next request.",
            {"input_tokens": 0, "output_tokens": 0},
            int((time.monotonic() - start) * 1000),
        )


# ---------------------------------------------------------------------------
# E) Response parsing
# ---------------------------------------------------------------------------


def infer_priority(text: str) -> str:
    """Infer priority from briefing item text."""
    text_lower = text.lower()
    critical_words = [
        "unassigned", "no vault", "overdue", "error", "past due 60",
        "open incident", "not syncing", "failed", "missing",
    ]
    warning_words = [
        "unscheduled", "no driver", "pending", "not yet", "7 days",
        "not confirmed", "approaching", "tomorrow",
    ]
    if any(w in text_lower for w in critical_words):
        return "critical"
    if any(w in text_lower for w in warning_words):
        return "warning"
    return "info"


def parse_briefing_items(text: str) -> list[dict]:
    """Parse a numbered-list briefing into structured items."""
    items: list[dict] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if match:
            number = int(match.group(1))
            text_content = match.group(2)
            priority = infer_priority(text_content)
            items.append({
                "number": number,
                "text": text_content,
                "priority": priority,
                "related_entity_type": None,
                "related_entity_hint": None,
            })
    return items


# ---------------------------------------------------------------------------
# F) Driver briefing (templated, no Claude)
# ---------------------------------------------------------------------------


def generate_driver_briefing(db: Session, user: User) -> str:
    """Generate a simple driver briefing from today's delivery data."""
    today = date.today()

    try:
        deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == user.company_id,
                Delivery.requested_date == today,
                Delivery.assigned_driver_id == user.id,
                Delivery.status != "cancelled",
            )
            .order_by(Delivery.required_window_start)
            .all()
        )

        if not deliveries:
            return "No deliveries assigned to you today. Check with dispatch for updates."

        parts = [f"You have {len(deliveries)} delivery(ies) today."]
        for i, d in enumerate(deliveries, 1):
            customer_name = "Unknown"
            if d.customer_id:
                try:
                    cust = db.query(Customer.name).filter(Customer.id == d.customer_id).first()
                    customer_name = cust[0] if cust else "Unknown"
                except Exception:
                    pass

            window = ""
            if d.required_window_start:
                start_str = d.required_window_start.strftime("%-I:%M %p")
                end_str = d.required_window_end.strftime("%-I:%M %p") if d.required_window_end else ""
                window = f" | Window: {start_str}"
                if end_str:
                    window += f"-{end_str}"

            addr = f" | {d.delivery_address}" if d.delivery_address else ""
            priority_flag = " [URGENT]" if d.priority == "urgent" else ""
            instructions = f" Note: {d.special_instructions}" if d.special_instructions else ""

            parts.append(
                f"{i}. {customer_name}{window}{addr}{priority_flag}{instructions}"
            )

        return "\n".join(parts)

    except Exception as e:
        logger.warning("Error generating driver briefing: %s", e)
        return "Unable to load today's delivery schedule. Contact dispatch."


def generate_production_briefing(db: Session, user: User) -> str:
    """Generate a simple production worker briefing."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        # Yesterday's production count
        yesterday_count = (
            db.query(func.coalesce(func.sum(ProductionLogEntry.quantity_produced), 0))
            .filter(
                ProductionLogEntry.tenant_id == user.company_id,
                ProductionLogEntry.log_date == yesterday,
            )
            .scalar()
        ) or 0

        # Today's deliveries (need to produce for)
        today_delivery_count = (
            db.query(func.count(Delivery.id))
            .filter(
                Delivery.company_id == user.company_id,
                Delivery.requested_date == today,
                Delivery.status != "cancelled",
            )
            .scalar()
        ) or 0

        parts = []
        if yesterday.weekday() < 5 and yesterday_count == 0:
            parts.append("Yesterday's production log is empty — please verify.")
        elif yesterday_count > 0:
            parts.append(f"Yesterday's production: {yesterday_count} units logged.")

        parts.append(f"Today's scheduled deliveries: {today_delivery_count}.")
        return " ".join(parts)

    except Exception as e:
        logger.warning("Error generating production briefing: %s", e)
        return "Unable to load production summary. Check the production log."


# ---------------------------------------------------------------------------
# H) Context serialization
# ---------------------------------------------------------------------------


def _serialize_context_to_text(
    primary_area: str, context: dict
) -> str:
    """Convert a context dict into plain text for the Claude user prompt."""
    today = date.today()
    day_name = today.strftime("%A, %B %d, %Y")
    lines = [f"TODAY: {day_name}", ""]

    if primary_area == "funeral_scheduling":
        tc = context.get("today_count", 0)
        lines.append(f"TODAY'S FUNERAL DELIVERIES ({tc}):")
        for d in context.get("today_deliveries", []):
            cust = d.get("customer_name") or "Unknown"
            dtype = d.get("delivery_type") or ""
            addr = d.get("delivery_address") or ""
            driver = "Assigned" if d.get("assigned_driver_id") else "UNASSIGNED"
            status = d.get("status", "")
            window = ""
            if d.get("window_start"):
                window = f" | Time: {d['window_start']}"
                if d.get("window_end"):
                    window += f"-{d['window_end']}"
            lines.append(f"- {cust} -- {dtype} -- {addr}")
            lines.append(f"  Driver: {driver} | Status: {status}{window}")
            if d.get("special_instructions"):
                lines.append(f"  Note: {d['special_instructions']}")

        lines.append("")
        uc = context.get("unscheduled_count", 0)
        lines.append(f"UNSCHEDULED WITHIN 5 DAYS ({uc}):")
        for d in context.get("unscheduled_within_5_days", []):
            cust = d.get("customer_name") or "Unknown"
            rdate = d.get("requested_date") or "?"
            lines.append(f"- {cust} -- requested {rdate}")

        tc2 = context.get("tomorrow_count", 0)
        lines.append("")
        lines.append(f"TOMORROW'S DELIVERIES ({tc2}):")
        for d in context.get("tomorrow_deliveries", []):
            cust = d.get("customer_name") or "Unknown"
            driver = "Assigned" if d.get("assigned_driver_id") else "UNASSIGNED"
            lines.append(f"- {cust} -- Driver: {driver}")

    elif primary_area == "invoicing_ar":
        lines.append("ACCOUNTS RECEIVABLE AGING:")
        lines.append(f"  0-30 days overdue: ${context.get('overdue_0_30', '0')}")
        lines.append(f"  31-60 days overdue: ${context.get('overdue_31_60', '0')}")
        lines.append(f"  90+ days overdue: ${context.get('overdue_90_plus', '0')}")
        lines.append(f"  Total overdue: ${context.get('overdue_total', '0')} ({context.get('overdue_invoice_count', 0)} invoices)")
        lines.append("")
        lines.append(f"PAYMENTS RECEIVED TODAY: {context.get('payments_today_count', 0)}")
        py = context.get("payments_yesterday", {})
        if py.get("count", 0) > 0:
            lines.append(
                f"PAYMENTS YESTERDAY: {py['count']} payments totaling "
                f"${py.get('total_amount', 0):.2f}"
            )
        disc = context.get("outstanding_discounts", {})
        exp_today = disc.get("expiring_today", {})
        exp_week = disc.get("expiring_this_week", {})
        if exp_today.get("count", 0) > 0:
            lines.append(
                f"DISCOUNT EXPIRY URGENT: {exp_today['count']} early payment discount(s) "
                f"expire TODAY — ${exp_today.get('total_discount_value', 0):.2f} in savings "
                "for customers. Consider reaching out."
            )
        if exp_week.get("count", 0) > 0:
            lines.append(
                f"DISCOUNTS EXPIRING THIS WEEK: {exp_week['count']} more discount(s) "
                f"expiring — ${exp_week.get('total_discount_value', 0):.2f} total."
            )
        lines.append(f"UNINVOICED COMPLETED ORDERS: {context.get('uninvoiced_completed_orders', 0)}")
        lines.append("")
        dp = context.get("draft_invoices_pending", {})
        dp_count = dp.get("count", 0) if dp else 0
        if dp_count > 0:
            dp_total = dp.get("total_amount", "0")
            dp_exc = dp.get("exception_count", 0)
            dp_auto = dp.get("auto_confirmed_count", 0)
            dp_customers = dp.get("customers", [])
            lines.append(f"DRAFT INVOICES PENDING REVIEW: {dp_count} (${dp_total} total)")
            if dp_auto > 0:
                lines.append(
                    f"  🤖 {dp_auto} deliveries were auto-confirmed — "
                    "review for any exceptions before approving."
                )
            if dp_exc > 0:
                lines.append(f"  ⚠ {dp_exc} have driver exceptions — require individual review")
            lines.append(f"  Customers: {', '.join(dp_customers[:5])}")
            lines.append(f"  Action: Review at /ar/invoices/review")
            lines.append("")
        se = context.get("sync_error_count", 0)
        lines.append(f"ACCOUNTING SYNC ERRORS (24H): {se}")
        for err in context.get("sync_errors_24h", []):
            lines.append(f"  - {err.get('sync_type')}: {err.get('error_message', '')[:100]}")

    elif primary_area == "safety_compliance":
        lines.append("SAFETY DASHBOARD:")
        lines.append(f"  Overdue corrective actions: {context.get('overdue_corrective_actions', 0)}")
        lines.append(f"  Open incidents: {context.get('open_incidents', 0)}")
        lines.append(f"  Overdue training records: {context.get('overdue_training_records', 0)}")
        lines.append(f"  Failed inspections (7 days): {context.get('failed_inspections_7d', 0)}")

    elif primary_area == "full_admin":
        lines.append("BUSINESS OVERVIEW:")
        lines.append(f"  Revenue this week: ${context.get('revenue_this_week', '0')}")
        lines.append(f"  Outstanding AR: ${context.get('outstanding_ar', '0')}")
        lines.append(f"  Today's deliveries: {context.get('today_delivery_count', 0)}")
        lines.append(f"  Active orders: {context.get('active_orders', 0)}")
        se = context.get("sync_errors_24h", 0)
        if se:
            lines.append(f"  Sync errors (24h): {se}")

    elif primary_area == "precast_scheduling":
        tc = context.get("today_count", 0)
        lines.append(f"TODAY'S DELIVERIES ({tc}):")
        for d in context.get("today_deliveries", []):
            cust = d.get("customer_name") or "Unknown"
            dtype = d.get("delivery_type") or ""
            lines.append(f"- {cust} -- {dtype} -- status: {d.get('status', '')}")
        lines.append("")
        uc = context.get("unscheduled_count", 0)
        lines.append(f"UNSCHEDULED WITHIN 5 DAYS ({uc}):")
        for d in context.get("unscheduled_within_5_days", []):
            cust = d.get("customer_name") or "Unknown"
            rdate = d.get("requested_date") or "?"
            lines.append(f"- {cust} -- requested {rdate}")
        lines.append("")
        lines.append(f"ACTIVE ORDERS: {context.get('active_orders', 0)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Permission-based briefing items
# ---------------------------------------------------------------------------


def _get_permission_based_items(db: Session, user: User) -> list[str]:
    """Gather briefing items based on user's effective permissions."""
    from app.services.permission_service import get_user_permissions

    perms = get_user_permissions(user, db)
    items: list[str] = []

    # invoice.approve → draft invoices pending approval
    if "invoice.approve" in perms:
        try:
            draft_count = (
                db.query(Invoice)
                .filter(
                    Invoice.company_id == user.company_id,
                    Invoice.status == "draft",
                )
                .count()
            )
            if draft_count > 0:
                items.append(
                    f"{draft_count} draft invoice(s) pending your approval."
                )
        except Exception:
            pass

    # financials.ar.view → overdue invoice summary
    if "financials.ar.view" in perms:
        try:
            overdue_count = (
                db.query(Invoice)
                .filter(
                    Invoice.company_id == user.company_id,
                    Invoice.status == "overdue",
                )
                .count()
            )
            if overdue_count > 0:
                items.append(f"{overdue_count} overdue invoice(s) need attention.")
        except Exception:
            pass

    # operations.view → orders due today
    if "operations.view" in perms:
        try:
            today = date.today()
            due_today = (
                db.query(SalesOrder)
                .filter(
                    SalesOrder.company_id == user.company_id,
                    SalesOrder.scheduled_date == today,
                    SalesOrder.status.in_(["confirmed", "processing"]),
                )
                .count()
            )
            if due_today > 0:
                items.append(f"{due_today} order(s) scheduled for delivery today.")
        except Exception:
            pass

    # safety.trainer.view → safety program generation status
    if "safety.trainer.view" in perms:
        try:
            from app.models.safety_program_generation import SafetyProgramGeneration
            from datetime import datetime as _dt, timezone as _tz

            now = _dt.now(_tz.utc)
            current_month = now.month
            current_year = now.year

            # Check for pending review programs
            pending_review = (
                db.query(SafetyProgramGeneration)
                .filter(
                    SafetyProgramGeneration.tenant_id == user.company_id,
                    SafetyProgramGeneration.status == "pending_review",
                )
                .count()
            )
            if pending_review > 0:
                items.append(
                    f"{pending_review} written safety program(s) awaiting your review and approval."
                )

            # Check if this month's program has been generated
            this_month_gen = (
                db.query(SafetyProgramGeneration)
                .filter(
                    SafetyProgramGeneration.tenant_id == user.company_id,
                    SafetyProgramGeneration.year == current_year,
                    SafetyProgramGeneration.month_number == current_month,
                )
                .first()
            )
            if not this_month_gen:
                from app.models.tenant_training_schedule import TenantTrainingSchedule as _TTS
                from app.models.safety_training_topic import SafetyTrainingTopic as _STT

                schedule = (
                    db.query(_TTS)
                    .filter(
                        _TTS.tenant_id == user.company_id,
                        _TTS.year == current_year,
                        _TTS.month_number == current_month,
                    )
                    .first()
                )
                if schedule:
                    topic = db.query(_STT).filter(_STT.id == schedule.topic_id).first()
                    topic_name = topic.title if topic else "this month's topic"
                    items.append(
                        f"No written safety program generated yet for {topic_name}. "
                        f"Generate one from the Safety Programs page."
                    )

            # Check for failed generations
            failed = (
                db.query(SafetyProgramGeneration)
                .filter(
                    SafetyProgramGeneration.tenant_id == user.company_id,
                    SafetyProgramGeneration.generation_status == "failed",
                    SafetyProgramGeneration.year == current_year,
                )
                .count()
            )
            if failed > 0:
                items.append(
                    f"{failed} safety program generation(s) failed — check error details and retry."
                )
        except Exception:
            pass

    # Check custom permissions with notification_routing
    try:
        from app.models.custom_permission import CustomPermission

        custom_perms = (
            db.query(CustomPermission)
            .filter(
                CustomPermission.tenant_id == user.company_id,
                CustomPermission.notification_routing.is_(True),
            )
            .all()
        )
        for cp in custom_perms:
            if cp.slug in perms:
                items.append(
                    f"[{cp.name}] You have the '{cp.name}' specialty permission — "
                    f"check for related items."
                )
    except Exception:
        pass

    return items


# ---------------------------------------------------------------------------
# Functional area briefing generation
# ---------------------------------------------------------------------------


def generate_functional_area_briefing(
    db: Session,
    user: User,
    primary_area: str,
    active_areas: list[str],
    tenant_areas: list[dict],
) -> tuple[str, dict, dict, int]:
    """Generate a Claude-powered briefing for a functional area.

    Returns (content, context_payload, token_usage, duration_ms).
    """
    # Build context
    builder = CONTEXT_BUILDERS.get(primary_area)
    if not builder:
        return (
            "1. No briefing template available for this area.",
            {},
            {"input_tokens": 0, "output_tokens": 0},
            0,
        )

    context = builder(db, user.company_id)

    # Build secondary critical items
    secondary_items: list[dict] = []
    for area in active_areas:
        if area != primary_area:
            secondary_items.extend(
                get_secondary_critical_items(db, user.company_id, area, active_areas)
            )

    # Build user prompt
    user_prompt = _serialize_context_to_text(primary_area, context)

    if secondary_items:
        user_prompt += "\n\nCRITICAL ITEMS FROM OTHER AREAS:"
        for item in secondary_items:
            user_prompt += f"\n- [{item['priority'].upper()}] {item['text']}"

    # Inject permission-based briefing items
    perm_items = _get_permission_based_items(db, user)
    if perm_items:
        user_prompt += "\n\nPERMISSION-BASED ACTION ITEMS:"
        for item in perm_items:
            user_prompt += f"\n- {item}"

    # Inject historical seasonal context if available
    hist = _get_historical_context(db, user.company_id)
    if hist:
        user_prompt += "\n\nHISTORICAL CONTEXT (from imported order history):"
        user_prompt += f"\n  Avg daily orders (historical): {hist['avg_daily_orders']}"
        if hist.get("peak_season_alert"):
            user_prompt += (
                f"\n  PEAK SEASON: {hist['current_month_name']} is historically one of your "
                f"busiest months — averaging {hist['current_month_avg_orders']} orders/day."
            )
        if hist.get("peak_month_names"):
            user_prompt += f"\n  Historical peak months: {', '.join(hist['peak_month_names'])}"
        user_prompt += (
            "\n  Note: If current month is a historical peak, mention it naturally in the briefing."
        )

    user_prompt += "\n\nGenerate today's briefing."

    # Get system prompt
    system_prompt = SYSTEM_PROMPTS.get(primary_area, SYSTEM_PROMPTS["full_admin"])

    # Call Claude
    content, token_usage, duration_ms = _call_briefing_api(system_prompt, user_prompt)

    return content, context, token_usage, duration_ms


# ---------------------------------------------------------------------------
# G) Main entry point with caching
# ---------------------------------------------------------------------------


def get_briefing_for_employee(
    db: Session,
    user: User,
    employee_profile: EmployeeProfile,
    tenant_areas: list[dict],
) -> dict | None:
    """Main entry. Returns cached or fresh briefing."""
    today = date.today()

    # Check cache via assistant_profile
    profile = (
        db.query(AssistantProfile)
        .filter(AssistantProfile.user_id == user.id)
        .first()
    )
    if profile and profile.last_briefing_date == today and profile.last_briefing_content:
        # Load parsed items from employee_briefings
        existing_briefing = (
            db.query(EmployeeBriefing)
            .filter(
                EmployeeBriefing.user_id == user.id,
                EmployeeBriefing.briefing_date == today,
            )
            .first()
        )
        return {
            "content": profile.last_briefing_content,
            "items": existing_briefing.parsed_items if existing_briefing else [],
            "tier": existing_briefing.tier if existing_briefing else "unknown",
            "primary_area": profile.primary_area,
            "was_cached": True,
            "generated_at": profile.updated_at.isoformat() if profile.updated_at else None,
            "briefing_date": str(today),
        }

    # Determine tier and generate
    active_areas = get_active_areas_for_employee(
        employee_profile.functional_areas, tenant_areas
    )

    primary = None
    tier = "primary_area"
    content = ""
    context_payload: dict = {}
    token_usage: dict = {"input_tokens": 0, "output_tokens": 0}
    duration_ms = 0
    parsed_items: list[dict] = []

    if user.track == "production_delivery":
        console_access = user.console_access or []
        if "delivery_console" in console_access:
            content = generate_driver_briefing(db, user)
            tier = "role_based"
        else:
            content = generate_production_briefing(db, user)
            tier = "role_based"
    else:
        primary = (
            employee_profile.briefing_primary_area_override
            or determine_primary_area(active_areas, tenant_areas)
        )
        if not primary:
            return None

        content, context_payload, token_usage, duration_ms = (
            generate_functional_area_briefing(
                db, user, primary, active_areas, tenant_areas
            )
        )
        tier = "executive" if primary == "full_admin" else "primary_area"

    # Parse items
    if tier != "role_based":
        parsed_items = parse_briefing_items(content)

    # Save to employee_briefings table
    briefing = EmployeeBriefing(
        id=str(uuid.uuid4()),
        company_id=user.company_id,
        user_id=user.id,
        briefing_date=today,
        primary_area=primary,
        tier=tier,
        context_payload=context_payload or None,
        generated_content=content,
        parsed_items=parsed_items or None,
        token_usage=token_usage or None,
        generation_duration_ms=duration_ms,
        was_cached=False,
    )
    db.add(briefing)

    # Update assistant_profile cache
    if not profile:
        profile = AssistantProfile(
            id=str(uuid.uuid4()),
            user_id=user.id,
            company_id=user.company_id,
        )
        db.add(profile)

    profile.last_briefing_date = today
    profile.last_briefing_content = content
    profile.primary_area = primary
    profile.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "content": content,
        "items": parsed_items,
        "tier": tier,
        "primary_area": primary,
        "was_cached": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "briefing_date": str(today),
        "token_usage": token_usage,
        "duration_ms": duration_ms,
    }


def refresh_briefing_for_employee(
    db: Session,
    user: User,
    employee_profile: EmployeeProfile,
    tenant_areas: list[dict],
) -> dict | None:
    """Force-refresh: delete today's cache and regenerate."""
    today = date.today()

    # Delete today's briefing record if exists
    db.query(EmployeeBriefing).filter(
        EmployeeBriefing.user_id == user.id,
        EmployeeBriefing.briefing_date == today,
    ).delete()

    # Clear assistant_profile cache
    profile = (
        db.query(AssistantProfile)
        .filter(AssistantProfile.user_id == user.id)
        .first()
    )
    if profile:
        profile.last_briefing_date = None
        profile.last_briefing_content = None

    db.flush()

    return get_briefing_for_employee(db, user, employee_profile, tenant_areas)
