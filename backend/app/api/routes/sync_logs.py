from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.sync_log import SyncLogResponse
from app.services.sync_log_service import get_sync_log, get_sync_logs

router = APIRouter()


@router.get("", response_model=dict)
def list_sync_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view")),
):
    result = get_sync_logs(db, current_user.company_id, page, per_page)
    result["items"] = [
        SyncLogResponse.model_validate(log).model_dump() for log in result["items"]
    ]
    return result


@router.get("/{sync_log_id}", response_model=SyncLogResponse)
def read_sync_log(
    sync_log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view")),
):
    log = get_sync_log(db, sync_log_id, current_user.company_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sync log not found"
        )
    return log
