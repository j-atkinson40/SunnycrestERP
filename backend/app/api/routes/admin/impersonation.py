"""Admin impersonation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.admin import impersonation_service

router = APIRouter()


class StartImpersonationRequest(BaseModel):
    tenant_id: str
    impersonated_user_id: str
    reason: str | None = None
    environment: str = "production"


@router.post("/start")
def start(
    data: StartImpersonationRequest,
    request: Request,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        return impersonation_service.start_impersonation(
            db=db,
            admin=admin,
            tenant_id=data.tenant_id,
            impersonated_user_id=data.impersonated_user_id,
            reason=data.reason,
            source_ip=request.client.host if request.client else None,
            environment=data.environment,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{session_id}/end")
def end(
    session_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        session = impersonation_service.end_impersonation(db, session_id, admin)
        return {"id": session.id, "ended_at": session.ended_at.isoformat() if session.ended_at else None}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sessions")
def list_sessions(
    limit: int = 50,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    sessions = impersonation_service.list_sessions(db, limit=limit)
    return [
        {
            "id": s.id,
            "admin_user_id": s.admin_user_id,
            "tenant_id": s.tenant_id,
            "impersonated_user_id": s.impersonated_user_id,
            "reason": s.reason,
            "environment": s.environment,
            "started_at": s.started_at.isoformat(),
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "is_active": s.is_active,
        }
        for s in sessions
    ]
