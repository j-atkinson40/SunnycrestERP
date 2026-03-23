"""Operations board API routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
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
