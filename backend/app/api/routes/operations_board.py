"""Operations board API routes."""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.ai_service import call_anthropic
from app.services.operations_board_service import (
    get_announcement_replies,
    get_merged_settings,
    get_or_create_settings,
    get_pending_summaries,
    get_today_entries,
    log_production,
    post_summary_to_inventory,
    reply_to_announcement,
    submit_summary,
    update_qc_status,
    update_settings_bulk,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProductionLogCreate(BaseModel):
    product_name_raw: str
    quantity: int
    product_id: str | None = None
    entry_method: str = "manual"
    raw_prompt: str | None = None
    component_type: str = "complete"
    component_reason: str | None = None


class QCUpdateRequest(BaseModel):
    qc_status: str
    qc_notes: str | None = None


class SubmitSummaryRequest(BaseModel):
    notes_for_tomorrow: str | None = None


class ReplyRequest(BaseModel):
    reply_type: str  # got_it, cant_do_it, need_info


class SettingsUpdate(BaseModel):
    updates: dict


# ---------------------------------------------------------------------------
# Board Settings
# ---------------------------------------------------------------------------


@router.get("/settings")
def get_board_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all settings as a flat dict — fixed columns merged with contributor_settings JSONB."""
    return get_merged_settings(db, current_user.company_id, current_user.id)


@router.patch("/settings")
def patch_board_settings(
    body: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update operations board settings — routes to fixed column or JSONB automatically."""
    update_settings_bulk(db, current_user.company_id, current_user.id, body.updates)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Production Log
# ---------------------------------------------------------------------------


@router.get("/production-log/today")
def get_todays_log(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get today's production log entries."""
    return get_today_entries(db, current_user.company_id)


@router.post("/production-log", status_code=status.HTTP_201_CREATED)
def create_log_entry(
    body: ProductionLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a production entry."""
    entry = log_production(
        db=db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        product_name_raw=body.product_name_raw,
        quantity=body.quantity,
        product_id=body.product_id,
        entry_method=body.entry_method,
        raw_prompt=body.raw_prompt,
    )
    return {"id": entry.id}


@router.post("/production-log/bulk", status_code=status.HTTP_201_CREATED)
def create_log_entries_bulk(
    entries: list[ProductionLogCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log multiple production entries at once."""
    ids = []
    for body in entries:
        entry = log_production(
            db=db,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
            product_name_raw=body.product_name_raw,
            quantity=body.quantity,
            product_id=body.product_id,
            entry_method=body.entry_method,
            raw_prompt=body.raw_prompt,
            component_type=body.component_type,
            component_reason=body.component_reason,
        )
        ids.append(entry.id)
    return {"ids": ids, "count": len(ids)}


@router.patch("/production-log/{entry_id}/qc")
def patch_qc(
    entry_id: str,
    body: QCUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update QC status on a production log entry."""
    success = update_qc_status(
        db, entry_id, current_user.company_id, current_user.id,
        body.qc_status, body.qc_notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Daily Summary
# ---------------------------------------------------------------------------


@router.post("/summary/submit")
def submit_daily_summary(
    body: SubmitSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit today's production summary to office for review."""
    summary = submit_summary(
        db, current_user.company_id, current_user.id, body.notes_for_tomorrow,
    )
    return {"id": summary.id, "status": summary.status}


@router.get("/summaries/pending")
def get_pending(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get summaries pending inventory posting (for office staff)."""
    return get_pending_summaries(db, current_user.company_id)


@router.post("/summaries/{summary_id}/post-to-inventory")
def post_to_inventory(
    summary_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Post a submitted summary to inventory."""
    result = post_summary_to_inventory(db, summary_id, current_user.company_id, current_user.id)
    if not result:
        raise HTTPException(status_code=400, detail="Summary not found or not in submitted status")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Announcement Replies
# ---------------------------------------------------------------------------


@router.post("/announcements/{announcement_id}/reply")
def reply_announcement(
    announcement_id: str,
    body: ReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reply to an operations board announcement."""
    if body.reply_type not in ("got_it", "cant_do_it", "need_info"):
        raise HTTPException(status_code=400, detail="Invalid reply_type")
    reply_to_announcement(
        db, current_user.company_id, announcement_id, current_user.id, body.reply_type,
    )
    return {"status": "ok"}


@router.get("/announcements/{announcement_id}/replies")
def get_replies(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get replies for an operations board announcement."""
    return get_announcement_replies(db, announcement_id)


# ---------------------------------------------------------------------------
# AI: Daily Context
# ---------------------------------------------------------------------------

INTERPRET_PROMPTS: dict[str, str] = {
    "production_log": (
        "You are interpreting a voice log entry from a burial vault manufacturing plant manager. "
        "Extract production quantities. Match product names flexibly (e.g. 'monty' = Monticello, "
        "'gravliner' = Graveliner, 'venish' = Venetian). Return JSON: "
        '{\"entries\": [{\"product_name\": string, \"matched_product_id\": string|null, '
        '\"quantity\": number, \"confidence\": number}], \"unrecognized\": [string], \"notes\": string|null}'
    ),
    "incident": (
        "You are interpreting a safety incident report from a burial vault plant manager. "
        "Extract incident details. Return JSON: "
        '{\"incident_type\": \"near_miss\"|\"first_aid\"|\"recordable\"|\"property_damage\"|\"other\", '
        '\"location\": string|null, \"people_involved\": [{\"name\": string, \"matched_id\": string|null}], '
        '\"description\": string, \"immediate_actions\": string|null, \"confidence\": number}'
    ),
    "safety_observation": (
        "You are interpreting a safety observation from a burial vault plant manager. Return JSON: "
        '{\"observation_type\": \"positive\"|\"concern\"|\"near_miss\", \"location\": string|null, '
        '\"description\": string, \"people_involved\": [{\"name\": string, \"matched_id\": string|null}], '
        '\"confidence\": number}'
    ),
    "qc_fail_note": (
        "Extract a defect description from a QC failure note. Return JSON: "
        '{\"defect_description\": string, \"disposition\": \"rework\"|\"scrap\"|\"accept\"|null}'
    ),
    "inspection": (
        "Extract inspection results from a voice note. Return JSON: "
        '{\"overall_pass\": boolean, \"issues\": [{\"equipment\": string|null, \"description\": string}], '
        '\"notes\": string|null}'
    ),
}


def _maybe_add_training_reminder(db: Session, user: User, result: dict) -> None:
    """Append a training reminder to the response items if the user hasn't completed
    the vault lifecycle training and their account is more than 3 days old."""
    try:
        from app.models.training_progress import TrainingProgress

        # Check if user account is at least 3 days old
        if user.created_at:
            age_days = (datetime.now(timezone.utc) - user.created_at).days
            if age_days < 3:
                return

        # Check if already completed
        count = (
            db.query(TrainingProgress)
            .filter(
                TrainingProgress.user_id == user.id,
                TrainingProgress.training_key == "vault_order_lifecycle",
            )
            .count()
        )
        if count >= 7:
            return  # All stages complete

        items = result.get("items") or []
        items.append({
            "type": "training_reminder",
            "message": "Complete the vault order lifecycle training",
            "action_label": "Start training",
            "action_url": "/training/vault-order-lifecycle",
        })
        result["items"] = items
    except Exception:
        pass  # Never break daily-context for training reminders


def _maybe_add_legacy_photo_tasks(db: Session, user: User, result: dict) -> None:
    """Add legacy photo needed items to the daily context."""
    try:
        from app.models.sales_order import SalesOrder
        from app.models.customer import Customer

        today = date.today()
        orders = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == user.company_id,
                SalesOrder.legacy_photo_pending.is_(True),
                SalesOrder.scheduled_date >= today,
                SalesOrder.status.notin_(["cancelled", "void"]),
            )
            .order_by(SalesOrder.scheduled_date)
            .limit(5)
            .all()
        )
        if not orders:
            return

        items = result.get("items") or []
        for order in orders:
            customer = db.query(Customer).filter(Customer.id == order.customer_id).first() if order.customer_id else None
            fh_name = customer.name if customer else "Unknown"
            is_today = order.scheduled_date == today
            items.append({
                "type": "legacy_photo_needed",
                "message": f"{'TODAY: ' if is_today else ''}Legacy photo needed — {fh_name}",
                "action_label": "Upload photos",
                "action_url": f"/ar/orders/{order.id}",
            })
        result["items"] = items
    except Exception:
        pass


@router.get("/daily-context")
def get_daily_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Gather operational context and generate an AI briefing for the plant manager."""
    from app.models import SalesOrder, PurchaseOrder, ProductionLogEntry

    now = datetime.now(timezone.utc)
    hour = now.hour
    day_name = now.strftime("%A")
    today = date.today()
    tomorrow = today + timedelta(days=1)

    today_deliveries = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == current_user.company_id,
            SalesOrder.delivery_date == today,
            SalesOrder.status.notin_(["cancelled", "void"]),
        )
        .count()
    )

    expected_pos = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.company_id == current_user.company_id,
            PurchaseOrder.expected_delivery_date <= tomorrow,
            PurchaseOrder.status.in_(["approved", "sent", "partial"]),
        )
        .all()
    )

    production_today = (
        db.query(ProductionLogEntry)
        .filter(
            ProductionLogEntry.company_id == current_user.company_id,
            ProductionLogEntry.logged_at
            >= datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        .count()
    )

    context_data = {
        "day_name": day_name,
        "hour": hour,
        "today": today.isoformat(),
        "today_deliveries": today_deliveries,
        "expected_pos_count": len(expected_pos),
        "expected_pos": [
            {
                "id": po.id,
                "expected_delivery_date": po.expected_delivery_date.isoformat()
                if po.expected_delivery_date
                else None,
                "status": po.status,
            }
            for po in expected_pos
        ],
        "production_entries_today": production_today,
    }

    # ── Vault replenishment context ──────────────────────────────────────
    vault_urgency = None
    vault_delivery_today = False
    vault_po_today = None
    vault_supplier_vendor_id = None

    try:
        from app.models import VaultSupplier, Product, InventoryItem, Vendor
        from app.services.vault_inventory_service import check_reorder_needed

        supplier = (
            db.query(VaultSupplier)
            .filter(
                VaultSupplier.company_id == current_user.company_id,
                VaultSupplier.is_active.is_(True),
                VaultSupplier.is_primary.is_(True),
            )
            .first()
        )

        if supplier:
            vault_supplier_vendor_id = supplier.vendor_id

            # Check if today is a delivery day
            delivery_days = supplier.delivery_days or []
            vault_delivery_today = day_name in delivery_days

            # Scan vault products for urgency
            products = (
                db.query(Product)
                .filter(
                    Product.company_id == current_user.company_id,
                    Product.is_active.is_(True),
                    Product.product_line == "funeral_service",
                )
                .all()
            )

            any_urgent = False
            any_needs_reorder = False
            critical_products = []

            for product in products:
                inv_item = (
                    db.query(InventoryItem)
                    .filter(
                        InventoryItem.company_id == current_user.company_id,
                        InventoryItem.product_id == product.id,
                    )
                    .first()
                )
                if not inv_item or not inv_item.reorder_point:
                    continue

                reorder_info = check_reorder_needed(
                    db, current_user.company_id, product.id
                )
                if not reorder_info:
                    continue

                if reorder_info.get("urgent"):
                    any_urgent = True
                    critical_products.append({
                        "name": product.name,
                        "current_stock": reorder_info["current_stock"],
                        "reorder_point": reorder_info["reorder_point"],
                    })
                elif reorder_info.get("needs_reorder"):
                    any_needs_reorder = True

            if any_urgent:
                vault_urgency = "critical"
            elif any_needs_reorder:
                vault_urgency = "warning"
            else:
                vault_urgency = "ok"

            # Check for a vault PO expected today
            vault_po = (
                db.query(PurchaseOrder)
                .filter(
                    PurchaseOrder.company_id == current_user.company_id,
                    PurchaseOrder.vendor_id == supplier.vendor_id,
                    PurchaseOrder.expected_delivery_date == today,
                    PurchaseOrder.status.in_(["approved", "sent", "partial"]),
                )
                .first()
            )
            if vault_po:
                vendor = db.query(Vendor).filter(Vendor.id == supplier.vendor_id).first()
                vault_po_today = {
                    "id": vault_po.id,
                    "po_number": getattr(vault_po, "po_number", None),
                    "vendor_name": vendor.name if vendor else "Vault Supplier",
                    "total_units": getattr(vault_po, "total_amount", 0),
                }

            # Add vault context for Claude prompt
            if vault_urgency and vault_urgency != "ok":
                first_reorder = check_reorder_needed(
                    db, current_user.company_id, products[0].id
                ) if products else None
                context_data["vault_status"] = {
                    "urgency": vault_urgency,
                    "critical_products": critical_products,
                    "order_deadline": first_reorder["order_deadline"].isoformat()
                    if first_reorder and first_reorder.get("order_deadline")
                    else None,
                    "next_delivery": first_reorder["next_delivery"].isoformat()
                    if first_reorder and first_reorder.get("next_delivery")
                    else None,
                    "days_until_deadline": first_reorder.get("days_until_deadline")
                    if first_reorder
                    else None,
                    "supplier_vendor_id": supplier.vendor_id,
                }
    except Exception:
        logger.exception("Failed to gather vault context for daily briefing")

    # ── Vault urgency instructions for Claude ────────────────────────────
    vault_prompt_addendum = ""
    if vault_urgency == "critical":
        vault_prompt_addendum = (
            "\n\nIMPORTANT: Vault inventory is CRITICAL. Include this as the FIRST item in 'items': "
            f"type='vault_reorder', message='Vault order must be placed TODAY — stock is below reorder point', "
            f"action_label='Create Vault Order', action_url='/purchasing/po/new?vendor={vault_supplier_vendor_id}'"
        )
    elif vault_urgency == "warning":
        vault_prompt_addendum = (
            "\n\nVault inventory needs attention. Include a normal-priority item in 'items': "
            "type='vault_reorder', message='Vault reorder needed soon — stock approaching reorder point', "
            "action_label='Review Vault Stock', action_url='/console/operations'"
        )

    try:
        result = call_anthropic(
            system_prompt=(
                "You are an operations assistant for a burial vault manufacturing plant. "
                "Generate brief, practical daily context for the plant manager. "
                "Be concise — plant managers are busy. No fluff."
            ),
            user_message=(
                f"Generate a daily context briefing for {day_name} at {hour}:00. "
                "Return JSON only: {\"greeting\": string, \"priority_message\": string, "
                "\"items\": [{\"type\": string, \"message\": string, "
                "\"action_label\": string, \"action_url\": string}]}"
                + vault_prompt_addendum
            ),
            context_data=context_data,
            max_tokens=400,
        )
        result["generated_at"] = now.isoformat()
        result["cached"] = False
        result["vault_urgency"] = vault_urgency
        result["vault_delivery_today"] = vault_delivery_today
        result["vault_po_today"] = vault_po_today
        result["vault_supplier_vendor_id"] = vault_supplier_vendor_id

        # Training reminder — add to items if user hasn't completed lifecycle training
        _maybe_add_training_reminder(db, current_user, result)
        _maybe_add_legacy_photo_tasks(db, current_user, result)

        return result
    except Exception:
        greeting = (
            "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        )
        fallback = {
            "greeting": greeting,
            "priority_message": f"Today is {day_name}. {today_deliveries} deliveries scheduled.",
            "items": [],
            "generated_at": now.isoformat(),
            "cached": False,
            "vault_urgency": vault_urgency,
            "vault_delivery_today": vault_delivery_today,
            "vault_po_today": vault_po_today,
            "vault_supplier_vendor_id": vault_supplier_vendor_id,
        }
        _maybe_add_training_reminder(db, current_user, fallback)
        return fallback


# ---------------------------------------------------------------------------
# AI: Voice Transcript Interpreter
# ---------------------------------------------------------------------------


class InterpretRequest(BaseModel):
    context: str  # 'production_log' | 'incident' | 'safety_observation' | 'qc_fail_note' | 'inspection'
    transcript: str
    available_products: list[dict] = []  # [{id, name}]
    available_employees: list[dict] = []  # [{id, name}]


@router.post("/interpret")
def interpret_transcript(
    request: InterpretRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Interpret a voice transcript for a specific workflow context using Claude."""
    if request.context not in INTERPRET_PROMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown context '{request.context}'. Must be one of: {', '.join(INTERPRET_PROMPTS)}",
        )

    system_prompt = INTERPRET_PROMPTS[request.context]
    user_message = (
        f"The manager said: '{request.transcript}'\n\n"
        f"Available products: {request.available_products}\n"
        f"Available employees: {request.available_employees}"
    )

    return call_anthropic(
        system_prompt=system_prompt,
        user_message=user_message,
    )
