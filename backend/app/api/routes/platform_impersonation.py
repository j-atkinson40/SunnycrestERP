"""Platform admin — impersonation routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.schemas.platform_impersonation import (
    EndImpersonationRequest,
    ImpersonateRequest,
    ImpersonateResponse,
    ImpersonationSessionResponse,
)
from app.services.impersonation_service import (
    end_impersonation,
    list_impersonation_sessions,
    start_impersonation,
)

router = APIRouter()


@router.post("/impersonate", response_model=ImpersonateResponse)
def impersonate_tenant(
    data: ImpersonateRequest,
    request: Request,
    platform_user: PlatformUser = Depends(
        require_platform_role("super_admin", "support")
    ),
    db: Session = Depends(get_db),
):
    """Start an impersonation session for a tenant.

    Generates a short-lived (30 min) tenant token scoped to a specific user.
    All actions are logged in the audit trail.
    """
    ip = request.client.host if request.client else None
    try:
        result = start_impersonation(
            db,
            platform_user=platform_user,
            tenant_id=data.tenant_id,
            user_id=data.user_id,
            reason=data.reason,
            ip_address=ip,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/end-impersonation")
def end_session(
    data: EndImpersonationRequest,
    platform_user: PlatformUser = Depends(
        require_platform_role("super_admin", "support")
    ),
    db: Session = Depends(get_db),
):
    """End an active impersonation session."""
    try:
        session = end_impersonation(db, data.session_id, platform_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": "Session ended", "actions_performed": session.actions_performed}


@router.get("/sessions", response_model=list[ImpersonationSessionResponse])
def get_sessions(
    platform_user: PlatformUser = Depends(
        require_platform_role("super_admin")
    ),
    db: Session = Depends(get_db),
    tenant_id: str | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List impersonation sessions (audit trail)."""
    return list_impersonation_sessions(
        db,
        tenant_id=tenant_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
