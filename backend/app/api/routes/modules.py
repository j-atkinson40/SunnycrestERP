from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.module import ModuleResponse, ModuleUpdate
from app.services.module_service import get_company_modules, update_module_status

router = APIRouter()


@router.get("/", response_model=list[ModuleResponse])
def list_modules(
    current_user: User = Depends(require_permission("company.view")),
    db: Session = Depends(get_db),
):
    """List all modules with their enabled status for the current company."""
    return get_company_modules(db, current_user.company_id)


@router.put("/{module}", response_model=ModuleResponse)
def toggle_module(
    module: str,
    data: ModuleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Enable or disable a module. Admin only."""
    from app.core.modules import AVAILABLE_MODULES

    record = update_module_status(
        db, current_user.company_id, module, data.enabled, actor_id=current_user.id
    )
    meta = AVAILABLE_MODULES.get(module, {})
    return {
        "module": record.module,
        "enabled": record.enabled,
        "label": meta.get("label", module),
        "description": meta.get("description", ""),
        "locked": meta.get("locked", False),
    }
