from datetime import datetime

from pydantic import BaseModel


class OnboardingTemplateCreate(BaseModel):
    name: str
    items: list[str]  # list of checklist item labels


class OnboardingTemplateUpdate(BaseModel):
    name: str | None = None
    items: list[str] | None = None
    is_active: bool | None = None


class OnboardingTemplateResponse(BaseModel):
    id: str
    company_id: str
    name: str
    items: str  # JSON string in DB; frontend parses it
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardingChecklistAssign(BaseModel):
    user_id: str
    template_id: str


class ChecklistItemUpdate(BaseModel):
    """Update a single checklist item's completed state."""
    item_index: int
    completed: bool


class OnboardingChecklistResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    template_id: str
    items: str  # JSON string with completion state
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
