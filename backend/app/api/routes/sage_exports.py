import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.sage_export import (
    SageExportConfigResponse,
    SageExportConfigUpdate,
    SageExportRequest,
    SageExportResponse,
)
from app.schemas.sync_log import SyncLogResponse
from app.services.sage_export_service import (
    generate_sage_csv,
    get_export_history,
    get_or_create_config,
    update_config,
)

router = APIRouter()


@router.get("/config")
def read_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    config = get_or_create_config(db, current_user.company_id)
    return SageExportConfigResponse.model_validate(config).model_dump()


@router.patch("/config")
def update_export_config(
    data: SageExportConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    config = update_config(
        db,
        current_user.company_id,
        warehouse_code=data.warehouse_code,
        export_directory=data.export_directory,
        actor_id=current_user.id,
    )
    return SageExportConfigResponse.model_validate(config).model_dump()


@router.post("/generate")
def generate_export(
    data: SageExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    csv_data, record_count, sync_log_id = generate_sage_csv(
        db,
        current_user.company_id,
        data.date_from,
        data.date_to,
        actor_id=current_user.id,
    )
    return SageExportResponse(
        csv_data=csv_data,
        record_count=record_count,
        sync_log_id=sync_log_id,
    ).model_dump()


@router.get("/download")
def download_export(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    csv_data, _, _ = generate_sage_csv(
        db,
        current_user.company_id,
        date_from,
        date_to,
        actor_id=current_user.id,
    )
    filename = f"sage_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/history")
def list_export_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    result = get_export_history(
        db, current_user.company_id, page=page, per_page=per_page
    )
    return {
        "items": [
            SyncLogResponse.model_validate(log).model_dump()
            for log in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }
