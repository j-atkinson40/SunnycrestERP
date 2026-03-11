import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services import audit_service

router = APIRouter()


def _audit_log_to_response(log, db: Session) -> dict:
    """Convert an AuditLog model to a response dict with user name."""
    data = AuditLogResponse.model_validate(log).model_dump()
    # Deserialize changes JSON
    if log.changes:
        try:
            data["changes"] = json.loads(log.changes)
        except (json.JSONDecodeError, TypeError):
            data["changes"] = None
    # Look up user name
    if log.user_id:
        user = db.query(User).filter(User.id == log.user_id).first()
        if user:
            data["user_name"] = f"{user.first_name} {user.last_name}"
    return data


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    user_id: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view")),
):
    result = audit_service.get_audit_logs(
        db,
        current_user.company_id,
        page=page,
        per_page=per_page,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "items": [_audit_log_to_response(log, db) for log in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/{log_id}", response_model=AuditLogResponse)
def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view")),
):
    log = audit_service.get_audit_log(db, log_id, current_user.company_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )
    return _audit_log_to_response(log, db)
