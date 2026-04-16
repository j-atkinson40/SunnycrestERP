"""Admin deployment endpoints (Part 14)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.admin import deployment_service, smoke_test_service

router = APIRouter()


class LogDeploymentRequest(BaseModel):
    description: str
    affected_verticals: list[str]
    affected_features: list[str] | None = None
    git_commit: str | None = None


@router.get("")
def list_deployments(
    untested: bool = False,
    limit: int = 50,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    rows = (
        deployment_service.get_untested_deployments(db) if untested
        else deployment_service.list_deployments(db, limit=limit)
    )
    return [
        {
            "id": d.id,
            "description": d.description,
            "affected_verticals": d.affected_verticals,
            "affected_features": d.affected_features,
            "git_commit": d.git_commit,
            "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
            "is_tested": d.is_tested,
            "tested_at": d.tested_at.isoformat() if d.tested_at else None,
        }
        for d in rows
    ]


@router.post("")
def log_deployment(
    data: LogDeploymentRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    dep = deployment_service.log_deployment(
        db=db,
        description=data.description,
        affected_verticals=data.affected_verticals,
        affected_features=data.affected_features,
        git_commit=data.git_commit,
        admin_user_id=admin.id,
    )
    return {
        "id": dep.id,
        "description": dep.description,
        "affected_verticals": dep.affected_verticals,
        "is_tested": dep.is_tested,
        "deployed_at": dep.deployed_at.isoformat(),
    }


@router.get("/untested")
def list_untested(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    deps = deployment_service.get_untested_deployments(db)
    by_vertical = {}
    for d in deps:
        for v in (d.affected_verticals or []):
            by_vertical.setdefault(v, []).append({
                "id": d.id,
                "description": d.description,
                "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
            })
    return by_vertical


@router.patch("/{deployment_id}/mark-tested")
def mark_tested(
    deployment_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        dep = deployment_service.manually_mark_tested(db, deployment_id)
        return {
            "id": dep.id,
            "is_tested": dep.is_tested,
            "tested_at": dep.tested_at.isoformat() if dep.tested_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Smoke tests ---

class RunSmokeRequest(BaseModel):
    company_id: str


@router.post("/smoke-test")
async def run_smoke(
    data: RunSmokeRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        result = await smoke_test_service.run_smoke_test(
            db=db,
            company_id=data.company_id,
            trigger="manual",
            triggered_by_admin_id=admin.id,
        )
        return {
            "id": result.id,
            "company_id": result.company_id,
            "status": result.status,
            "checks_total": result.checks_total,
            "checks_passed": result.checks_passed,
            "checks_failed": result.checks_failed,
            "duration_seconds": result.duration_seconds,
            "failures": result.failures,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/smoke-tests")
def list_smoke(
    company_id: str | None = None,
    limit: int = 20,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    results = smoke_test_service.list_recent_results(db, company_id=company_id, limit=limit)
    return [
        {
            "id": r.id,
            "company_id": r.company_id,
            "trigger": r.trigger,
            "status": r.status,
            "checks_total": r.checks_total,
            "checks_passed": r.checks_passed,
            "checks_failed": r.checks_failed,
            "duration_seconds": r.duration_seconds,
            "failures": r.failures,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in results
    ]
