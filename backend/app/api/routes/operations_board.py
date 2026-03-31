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
            ),
            context_data=context_data,
            max_tokens=400,
        )
        result["generated_at"] = now.isoformat()
        result["cached"] = False
        return result
    except Exception:
        greeting = (
            "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        )
        return {
            "greeting": greeting,
            "priority_message": f"Today is {day_name}. {today_deliveries} deliveries scheduled.",
            "items": [],
            "generated_at": now.isoformat(),
            "cached": False,
        }


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
