from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Milestone schemas
# ---------------------------------------------------------------------------


class MilestoneCreate(BaseModel):
    name: str
    description: str | None = None
    due_date: datetime
    sort_order: int = 0


class MilestoneUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None
    sort_order: int | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class MilestoneResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None = None
    due_date: datetime
    completed_at: datetime | None = None
    sort_order: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    name: str
    description: str | None = None
    assigned_to: str | None = None
    status: str = "todo"
    priority: str = "medium"
    sort_order: int = 0
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    due_date: datetime | None = None
    depends_on_task_id: str | None = None
    notes: str | None = None


class TaskUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    status: str | None = None
    priority: str | None = None
    sort_order: int | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    due_date: datetime | None = None
    depends_on_task_id: str | None = None
    notes: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class TaskResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None = None
    assigned_to: str | None = None
    assigned_to_name: str | None = None
    status: str
    priority: str
    sort_order: int
    estimated_hours: Decimal | None = None
    actual_hours: Decimal
    start_date: datetime | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None
    depends_on_task_id: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_at: datetime
    modified_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    customer_id: str | None = None
    project_type: str = "custom"
    priority: str = "medium"
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    budget: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    customer_id: str | None = None
    project_type: str | None = None
    status: str | None = None
    priority: str | None = None
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    actual_end_date: datetime | None = None
    budget: Decimal | None = Field(default=None, ge=0)
    actual_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ProjectResponse(BaseModel):
    id: str
    company_id: str
    number: str
    name: str
    description: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    project_type: str
    status: str
    priority: str
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    actual_end_date: datetime | None = None
    budget: Decimal | None = None
    actual_cost: Decimal
    notes: str | None = None
    is_active: bool
    created_by: str | None = None
    created_by_name: str | None = None
    modified_by: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    tasks: list[TaskResponse] = []
    milestones: list[MilestoneResponse] = []
    completion_pct: int = 0

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: str
    company_id: str
    number: str
    name: str
    customer_id: str | None = None
    customer_name: str | None = None
    project_type: str
    status: str
    priority: str
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    budget: Decimal | None = None
    actual_cost: Decimal
    is_active: bool
    created_at: datetime
    task_count: int = 0
    completed_task_count: int = 0
    completion_pct: int = 0

    model_config = {"from_attributes": True}
