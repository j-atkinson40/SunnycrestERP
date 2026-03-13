from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.onboarding import (
    ChecklistItemUpdate,
    OnboardingChecklistAssign,
    OnboardingChecklistResponse,
    OnboardingTemplateCreate,
    OnboardingTemplateResponse,
    OnboardingTemplateUpdate,
)
from app.services.onboarding_service import (
    assign_checklist,
    create_template,
    get_checklists_for_user,
    get_template,
    get_templates,
    update_checklist_item,
    update_template,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Template endpoints
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[OnboardingTemplateResponse])
def list_templates(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    return get_templates(db, current_user.company_id, include_inactive)


@router.get("/templates/{template_id}", response_model=OnboardingTemplateResponse)
def read_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    return get_template(db, template_id, current_user.company_id)


@router.post("/templates", status_code=201, response_model=OnboardingTemplateResponse)
def create_tmpl(
    data: OnboardingTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return create_template(db, data, current_user.company_id)


@router.patch("/templates/{template_id}", response_model=OnboardingTemplateResponse)
def update_tmpl(
    template_id: str,
    data: OnboardingTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return update_template(db, template_id, data, current_user.company_id)


# ---------------------------------------------------------------------------
# Checklist endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/checklists",
    response_model=list[OnboardingChecklistResponse],
)
def list_checklists(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    return get_checklists_for_user(db, user_id, current_user.company_id)


@router.post(
    "/checklists",
    status_code=201,
    response_model=OnboardingChecklistResponse,
)
def assign_cl(
    data: OnboardingChecklistAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return assign_checklist(
        db, data.user_id, data.template_id, current_user.company_id
    )


@router.patch(
    "/checklists/{checklist_id}/items",
    response_model=OnboardingChecklistResponse,
)
def update_item(
    checklist_id: str,
    data: ChecklistItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return update_checklist_item(
        db, checklist_id, data.item_index, data.completed, current_user.company_id
    )
