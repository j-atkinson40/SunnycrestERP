from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.project import Project, ProjectTask
from app.models.user import User
from app.schemas.project import (
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.project_service import (
    add_milestone,
    add_task,
    complete_task,
    create_project,
    delete_milestone,
    delete_project,
    delete_task,
    get_project,
    get_project_stats,
    list_projects,
    update_milestone,
    update_project,
    update_task,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _task_to_response(task: ProjectTask) -> dict:
    """Convert a ProjectTask ORM object to a response dict."""
    data = TaskResponse.model_validate(task).model_dump()
    if task.assignee:
        data["assigned_to_name"] = (
            f"{task.assignee.first_name} {task.assignee.last_name}"
        )
    return data


def _project_to_response(project: Project) -> dict:
    """Convert a Project ORM object to a full response dict."""
    data = ProjectResponse.model_validate(project).model_dump()
    if project.customer:
        data["customer_name"] = project.customer.name
    if project.creator:
        data["created_by_name"] = (
            f"{project.creator.first_name} {project.creator.last_name}"
        )
    data["tasks"] = [_task_to_response(t) for t in project.tasks]
    data["milestones"] = [
        MilestoneResponse.model_validate(m).model_dump()
        for m in project.milestones
    ]
    # Calculate completion percentage
    total_tasks = len(project.tasks)
    done_tasks = sum(1 for t in project.tasks if t.status == "done")
    data["completion_pct"] = (
        int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    )
    return data


def _project_to_list_response(
    project: Project,
    task_count: int,
    completed_task_count: int,
    completion_pct: int,
) -> dict:
    """Convert a Project ORM object to a summary list response dict."""
    data = ProjectListResponse.model_validate(project).model_dump()
    if project.customer:
        data["customer_name"] = project.customer.name
    data["task_count"] = task_count
    data["completed_task_count"] = completed_task_count
    data["completion_pct"] = completion_pct
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_projects_endpoint(
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    project_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.view")),
):
    """List projects with optional filters."""
    result = list_projects(
        db,
        current_user.company_id,
        project_status=status,
        customer_id=customer_id,
        project_type=project_type,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [
            _project_to_list_response(
                item["project"],
                item["task_count"],
                item["completed_task_count"],
                item["completion_pct"],
            )
            for item in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/stats")
def project_stats_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.view")),
):
    """Get project summary counts by status."""
    return get_project_stats(db, current_user.company_id)


@router.get("/{project_id}")
def get_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.view")),
):
    """Get a project with all tasks and milestones."""
    project = get_project(db, project_id, current_user.company_id)
    return _project_to_response(project)


@router.post("", status_code=201)
def create_project_endpoint(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.create")),
):
    """Create a new project."""
    project = create_project(db, current_user.company_id, data, current_user.id)
    return _project_to_response(project)


@router.patch("/{project_id}")
def update_project_endpoint(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.edit")),
):
    """Update a project."""
    project = update_project(
        db, project_id, current_user.company_id, data, current_user.id
    )
    return _project_to_response(project)


@router.delete("/{project_id}", status_code=204)
def delete_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.delete")),
):
    """Soft-delete a project."""
    delete_project(db, project_id, current_user.company_id)
    return None


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------


@router.post("/{project_id}/tasks", status_code=201)
def add_task_endpoint(
    project_id: str,
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.edit")),
):
    """Add a task to a project."""
    task = add_task(db, project_id, current_user.company_id, data, current_user.id)
    return _task_to_response(task)


@router.patch("/{project_id}/tasks/{task_id}")
def update_task_endpoint(
    project_id: str,
    task_id: str,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.edit")),
):
    """Update a task."""
    task = update_task(
        db, task_id, project_id, current_user.company_id, data, current_user.id
    )
    return _task_to_response(task)


@router.post("/{project_id}/tasks/{task_id}/complete")
def complete_task_endpoint(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.edit")),
):
    """Mark a task as complete."""
    task = complete_task(
        db, task_id, project_id, current_user.company_id, current_user.id
    )
    return _task_to_response(task)


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
def delete_task_endpoint(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.delete")),
):
    """Delete a task."""
    delete_task(db, task_id, project_id, current_user.company_id)
    return None


# ---------------------------------------------------------------------------
# Milestone endpoints
# ---------------------------------------------------------------------------


@router.post("/{project_id}/milestones", status_code=201)
def add_milestone_endpoint(
    project_id: str,
    data: MilestoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.edit")),
):
    """Add a milestone to a project."""
    milestone = add_milestone(db, project_id, current_user.company_id, data)
    return MilestoneResponse.model_validate(milestone).model_dump()


@router.patch("/{project_id}/milestones/{milestone_id}")
def update_milestone_endpoint(
    project_id: str,
    milestone_id: str,
    data: MilestoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.edit")),
):
    """Update a milestone."""
    milestone = update_milestone(
        db, milestone_id, project_id, current_user.company_id, data
    )
    return MilestoneResponse.model_validate(milestone).model_dump()


@router.delete("/{project_id}/milestones/{milestone_id}", status_code=204)
def delete_milestone_endpoint(
    project_id: str,
    milestone_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects.delete")),
):
    """Delete a milestone."""
    delete_milestone(db, milestone_id, project_id, current_user.company_id)
    return None
