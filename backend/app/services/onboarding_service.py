import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingChecklist, OnboardingTemplate
from app.schemas.onboarding import (
    OnboardingTemplateCreate,
    OnboardingTemplateUpdate,
)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def get_templates(
    db: Session, company_id: str, include_inactive: bool = False
) -> list[OnboardingTemplate]:
    query = db.query(OnboardingTemplate).filter(
        OnboardingTemplate.company_id == company_id
    )
    if not include_inactive:
        query = query.filter(OnboardingTemplate.is_active == True)  # noqa: E712
    return query.order_by(OnboardingTemplate.created_at.desc()).all()


def get_template(
    db: Session, template_id: str, company_id: str
) -> OnboardingTemplate:
    tmpl = (
        db.query(OnboardingTemplate)
        .filter(
            OnboardingTemplate.id == template_id,
            OnboardingTemplate.company_id == company_id,
        )
        .first()
    )
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding template not found",
        )
    return tmpl


def create_template(
    db: Session, data: OnboardingTemplateCreate, company_id: str
) -> OnboardingTemplate:
    tmpl = OnboardingTemplate(
        company_id=company_id,
        name=data.name,
        items=json.dumps(data.items),
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def update_template(
    db: Session,
    template_id: str,
    data: OnboardingTemplateUpdate,
    company_id: str,
) -> OnboardingTemplate:
    tmpl = get_template(db, template_id, company_id)
    if data.name is not None:
        tmpl.name = data.name
    if data.items is not None:
        tmpl.items = json.dumps(data.items)
    if data.is_active is not None:
        tmpl.is_active = data.is_active
    db.commit()
    db.refresh(tmpl)
    return tmpl


# ---------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------


def get_checklists_for_user(
    db: Session, user_id: str, company_id: str
) -> list[OnboardingChecklist]:
    return (
        db.query(OnboardingChecklist)
        .filter(
            OnboardingChecklist.user_id == user_id,
            OnboardingChecklist.company_id == company_id,
        )
        .order_by(OnboardingChecklist.created_at.desc())
        .all()
    )


def assign_checklist(
    db: Session, user_id: str, template_id: str, company_id: str
) -> OnboardingChecklist:
    tmpl = get_template(db, template_id, company_id)
    template_items = json.loads(tmpl.items)
    # Create items with completed=False
    checklist_items = [
        {"label": item, "completed": False} for item in template_items
    ]
    checklist = OnboardingChecklist(
        company_id=company_id,
        user_id=user_id,
        template_id=template_id,
        items=json.dumps(checklist_items),
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return checklist


def update_checklist_item(
    db: Session,
    checklist_id: str,
    item_index: int,
    completed: bool,
    company_id: str,
) -> OnboardingChecklist:
    cl = (
        db.query(OnboardingChecklist)
        .filter(
            OnboardingChecklist.id == checklist_id,
            OnboardingChecklist.company_id == company_id,
        )
        .first()
    )
    if not cl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding checklist not found",
        )
    items = json.loads(cl.items)
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid item index",
        )
    items[item_index]["completed"] = completed
    cl.items = json.dumps(items)
    db.commit()
    db.refresh(cl)
    return cl
