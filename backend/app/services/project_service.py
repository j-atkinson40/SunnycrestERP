import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.project import Project, ProjectMilestone, ProjectTask
from app.schemas.project import (
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskUpdate,
)


def list_projects(
    db: Session,
    company_id: str,
    project_status: str | None = None,
    customer_id: str | None = None,
    project_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated list of projects with summary info."""
    query = db.query(Project).filter(
        Project.company_id == company_id,
        Project.is_active.is_(True),
    )
    if project_status:
        query = query.filter(Project.status == project_status)
    if customer_id:
        query = query.filter(Project.customer_id == customer_id)
    if project_type:
        query = query.filter(Project.project_type == project_type)

    total = query.count()
    projects = (
        query.options(joinedload(Project.customer))
        .order_by(Project.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for project in projects:
        task_count = (
            db.query(func.count(ProjectTask.id))
            .filter(ProjectTask.project_id == project.id)
            .scalar()
        )
        completed_task_count = (
            db.query(func.count(ProjectTask.id))
            .filter(
                ProjectTask.project_id == project.id,
                ProjectTask.status == "done",
            )
            .scalar()
        )
        completion_pct = (
            int((completed_task_count / task_count) * 100) if task_count > 0 else 0
        )
        items.append(
            {
                "project": project,
                "task_count": task_count,
                "completed_task_count": completed_task_count,
                "completion_pct": completion_pct,
            }
        )

    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_project(db: Session, project_id: str, company_id: str) -> Project:
    """Get a single project with tasks and milestones eagerly loaded."""
    project = (
        db.query(Project)
        .options(
            joinedload(Project.customer),
            joinedload(Project.tasks).joinedload(ProjectTask.assignee),
            joinedload(Project.milestones),
            joinedload(Project.creator),
        )
        .filter(
            Project.id == project_id,
            Project.company_id == company_id,
            Project.is_active.is_(True),
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def create_project(
    db: Session,
    company_id: str,
    data: ProjectCreate,
    actor_id: str,
) -> Project:
    """Create a new project. Auto-generates project number."""
    # Auto-generate project number: PRJ-YYYY-####
    year = datetime.now(timezone.utc).year
    max_num = (
        db.query(func.max(Project.number))
        .filter(
            Project.company_id == company_id,
            Project.number.like(f"PRJ-{year}-%"),
        )
        .scalar()
    )
    if max_num:
        seq = int(max_num.split("-")[-1]) + 1
    else:
        seq = 1
    number = f"PRJ-{year}-{seq:04d}"

    now = datetime.now(timezone.utc)
    project = Project(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number,
        name=data.name,
        description=data.description,
        customer_id=data.customer_id,
        project_type=data.project_type,
        status="planning",
        priority=data.priority,
        start_date=data.start_date,
        target_end_date=data.target_end_date,
        budget=data.budget,
        notes=data.notes,
        created_by=actor_id,
        modified_by=actor_id,
        created_at=now,
        modified_at=now,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return get_project(db, project.id, company_id)


def update_project(
    db: Session,
    project_id: str,
    company_id: str,
    data: ProjectUpdate,
    actor_id: str,
) -> Project:
    """Update a project's fields."""
    project = get_project(db, project_id, company_id)

    now = datetime.now(timezone.utc)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.customer_id is not None:
        project.customer_id = data.customer_id
    if data.project_type is not None:
        project.project_type = data.project_type
    if data.status is not None:
        project.status = data.status
    if data.priority is not None:
        project.priority = data.priority
    if data.start_date is not None:
        project.start_date = data.start_date
    if data.target_end_date is not None:
        project.target_end_date = data.target_end_date
    if data.actual_end_date is not None:
        project.actual_end_date = data.actual_end_date
    if data.budget is not None:
        project.budget = data.budget
    if data.actual_cost is not None:
        project.actual_cost = data.actual_cost
    if data.notes is not None:
        project.notes = data.notes
    project.modified_by = actor_id
    project.modified_at = now

    db.commit()
    return get_project(db, project_id, company_id)


def delete_project(db: Session, project_id: str, company_id: str) -> None:
    """Soft-delete a project."""
    project = get_project(db, project_id, company_id)
    project.is_active = False
    project.modified_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def add_task(
    db: Session,
    project_id: str,
    company_id: str,
    data: TaskCreate,
    actor_id: str,
) -> ProjectTask:
    """Add a task to a project."""
    # Verify project exists
    get_project(db, project_id, company_id)

    now = datetime.now(timezone.utc)
    task = ProjectTask(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=data.name,
        description=data.description,
        assigned_to=data.assigned_to,
        status=data.status,
        priority=data.priority,
        sort_order=data.sort_order,
        estimated_hours=data.estimated_hours,
        start_date=data.start_date,
        due_date=data.due_date,
        depends_on_task_id=data.depends_on_task_id,
        notes=data.notes,
        created_by=actor_id,
        modified_by=actor_id,
        created_at=now,
        modified_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    task_id: str,
    project_id: str,
    company_id: str,
    data: TaskUpdate,
    actor_id: str,
) -> ProjectTask:
    """Update a task."""
    # Verify project exists
    get_project(db, project_id, company_id)

    task = (
        db.query(ProjectTask)
        .options(joinedload(ProjectTask.assignee))
        .filter(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    now = datetime.now(timezone.utc)
    if data.name is not None:
        task.name = data.name
    if data.description is not None:
        task.description = data.description
    if data.assigned_to is not None:
        task.assigned_to = data.assigned_to
    if data.status is not None:
        task.status = data.status
    if data.priority is not None:
        task.priority = data.priority
    if data.sort_order is not None:
        task.sort_order = data.sort_order
    if data.estimated_hours is not None:
        task.estimated_hours = data.estimated_hours
    if data.actual_hours is not None:
        task.actual_hours = data.actual_hours
    if data.start_date is not None:
        task.start_date = data.start_date
    if data.due_date is not None:
        task.due_date = data.due_date
    if data.depends_on_task_id is not None:
        task.depends_on_task_id = data.depends_on_task_id
    if data.notes is not None:
        task.notes = data.notes
    task.modified_by = actor_id
    task.modified_at = now

    db.commit()
    db.refresh(task)
    return task


def complete_task(
    db: Session,
    task_id: str,
    project_id: str,
    company_id: str,
    actor_id: str,
) -> ProjectTask:
    """Mark a task as done and set completed_at timestamp."""
    get_project(db, project_id, company_id)

    task = (
        db.query(ProjectTask)
        .options(joinedload(ProjectTask.assignee))
        .filter(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    now = datetime.now(timezone.utc)
    task.status = "done"
    task.completed_at = now
    task.modified_by = actor_id
    task.modified_at = now
    db.commit()
    db.refresh(task)
    return task


def delete_task(
    db: Session,
    task_id: str,
    project_id: str,
    company_id: str,
) -> None:
    """Hard-delete a task."""
    get_project(db, project_id, company_id)

    task = (
        db.query(ProjectTask)
        .filter(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    db.delete(task)
    db.commit()


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


def add_milestone(
    db: Session,
    project_id: str,
    company_id: str,
    data: MilestoneCreate,
) -> ProjectMilestone:
    """Add a milestone to a project."""
    get_project(db, project_id, company_id)

    milestone = ProjectMilestone(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=data.name,
        description=data.description,
        due_date=data.due_date,
        sort_order=data.sort_order,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


def update_milestone(
    db: Session,
    milestone_id: str,
    project_id: str,
    company_id: str,
    data: MilestoneUpdate,
) -> ProjectMilestone:
    """Update a milestone."""
    get_project(db, project_id, company_id)

    milestone = (
        db.query(ProjectMilestone)
        .filter(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == project_id,
        )
        .first()
    )
    if not milestone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found"
        )

    if data.name is not None:
        milestone.name = data.name
    if data.description is not None:
        milestone.description = data.description
    if data.due_date is not None:
        milestone.due_date = data.due_date
    if data.completed_at is not None:
        milestone.completed_at = data.completed_at
    if data.sort_order is not None:
        milestone.sort_order = data.sort_order

    db.commit()
    db.refresh(milestone)
    return milestone


def delete_milestone(
    db: Session,
    milestone_id: str,
    project_id: str,
    company_id: str,
) -> None:
    """Hard-delete a milestone."""
    get_project(db, project_id, company_id)

    milestone = (
        db.query(ProjectMilestone)
        .filter(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == project_id,
        )
        .first()
    )
    if not milestone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found"
        )
    db.delete(milestone)
    db.commit()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_project_stats(db: Session, company_id: str) -> dict:
    """Return summary counts of projects by status."""
    rows = (
        db.query(Project.status, func.count(Project.id))
        .filter(
            Project.company_id == company_id,
            Project.is_active.is_(True),
        )
        .group_by(Project.status)
        .all()
    )
    counts = {row[0]: row[1] for row in rows}
    total = sum(counts.values())

    return {
        "total": total,
        "planning": counts.get("planning", 0),
        "in_progress": counts.get("in_progress", 0),
        "on_hold": counts.get("on_hold", 0),
        "completed": counts.get("completed", 0),
        "cancelled": counts.get("cancelled", 0),
    }
