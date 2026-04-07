"""Call Intelligence API routes — call log, transcripts, extraction, reprocessing."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.models.ringcentral_call_extraction import RingCentralCallExtraction
from app.models.ringcentral_call_log import RingCentralCallLog
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_call(call: RingCentralCallLog) -> dict:
    extraction = call.extraction
    return {
        "id": call.id,
        "call_id": call.rc_call_id,
        "direction": call.direction,
        "status": call.call_status,
        "caller_number": call.caller_number,
        "caller_name": call.caller_name,
        "company_name": call.company_entity.name if call.company_entity else None,
        "company_id": call.company_entity_id,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "answered_at": call.answered_at.isoformat() if call.answered_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "has_transcript": bool(call.transcription),
        "order_created": call.order_created,
        "order_id": call.order_id,
        "extraction": _serialize_extraction(extraction) if extraction else None,
    }


def _serialize_extraction(ext: RingCentralCallExtraction) -> dict:
    return {
        "id": ext.id,
        "funeral_home_name": ext.funeral_home_name,
        "deceased_name": ext.deceased_name,
        "vault_type": ext.vault_type,
        "vault_size": ext.vault_size,
        "cemetery_name": ext.cemetery_name,
        "burial_date": ext.burial_date.isoformat() if ext.burial_date else None,
        "burial_time": ext.burial_time.isoformat() if ext.burial_time else None,
        "grave_location": ext.grave_location,
        "special_requests": ext.special_requests,
        "confidence": ext.confidence_json,
        "missing_fields": ext.missing_fields or [],
        "call_summary": ext.call_summary,
        "call_type": ext.call_type,
        "urgency": ext.urgency,
        "suggested_callback": ext.suggested_callback,
        "draft_order_created": ext.draft_order_created,
        "draft_order_id": ext.draft_order_id,
    }


@router.get("/calls")
def list_calls(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    direction: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    company_id: str | None = None,
    has_order: bool | None = None,
    call_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List calls with optional filters. Returns paginated results with extractions."""
    q = (
        db.query(RingCentralCallLog)
        .options(joinedload(RingCentralCallLog.extraction), joinedload(RingCentralCallLog.company_entity))
        .filter(RingCentralCallLog.tenant_id == current_user.company_id)
    )

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (RingCentralCallLog.caller_name.ilike(pattern))
            | (RingCentralCallLog.caller_number.ilike(pattern))
        )

    if direction and direction != "all":
        q = q.filter(RingCentralCallLog.direction == direction)

    if status_filter and status_filter != "all":
        q = q.filter(RingCentralCallLog.call_status == status_filter)

    if company_id:
        q = q.filter(RingCentralCallLog.company_entity_id == company_id)

    if has_order is not None:
        q = q.filter(RingCentralCallLog.order_created == has_order)

    if call_type:
        q = q.join(RingCentralCallExtraction, isouter=True).filter(
            RingCentralCallExtraction.call_type == call_type
        )

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            q = q.filter(RingCentralCallLog.started_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            q = q.filter(RingCentralCallLog.started_at <= dt)
        except ValueError:
            pass

    total = q.count()
    calls = q.order_by(desc(RingCentralCallLog.started_at)).offset(offset).limit(limit).all()

    return {
        "calls": [_serialize_call(c) for c in calls],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/calls/{call_id}")
def get_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full call record with transcript, extraction, and draft order link."""
    call = (
        db.query(RingCentralCallLog)
        .options(joinedload(RingCentralCallLog.extraction), joinedload(RingCentralCallLog.company_entity))
        .filter(
            RingCentralCallLog.id == call_id,
            RingCentralCallLog.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    result = _serialize_call(call)
    result["transcript"] = call.transcription
    return result


@router.get("/calls/{call_id}/transcript")
def get_transcript(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get formatted transcript for a call."""
    call = (
        db.query(RingCentralCallLog)
        .filter(
            RingCentralCallLog.id == call_id,
            RingCentralCallLog.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.transcription:
        raise HTTPException(status_code=404, detail="No transcript available")

    return {
        "call_id": call_id,
        "transcript": call.transcription,
        "source": call.transcription_source,
    }


@router.post("/calls/{call_id}/reprocess")
def reprocess_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run Claude extraction on existing transcript."""
    from app.services.after_call_service import reprocess_call as do_reprocess

    result = do_reprocess(db, call_id, current_user.company_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
