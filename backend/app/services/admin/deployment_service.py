"""Deployment test tracking — logs pushes and their test coverage state."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.admin_audit_run import AdminAuditRun
from app.models.admin_deployment import AdminDeployment
from app.models.company import Company


def log_deployment(
    db: Session,
    description: str,
    affected_verticals: list[str],
    affected_features: list[str] | None = None,
    git_commit: str | None = None,
    admin_user_id: str | None = None,
) -> AdminDeployment:
    dep = AdminDeployment(
        description=description,
        affected_verticals=affected_verticals,
        affected_features=affected_features,
        git_commit=git_commit,
        logged_by_admin_id=admin_user_id,
        is_tested=False,
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep


def get_untested_deployments(db: Session) -> list[AdminDeployment]:
    return (
        db.query(AdminDeployment)
        .filter(AdminDeployment.is_tested == False)  # noqa: E712
        .order_by(AdminDeployment.deployed_at.desc())
        .all()
    )


def get_untested_for_vertical(db: Session, vertical: str) -> list[AdminDeployment]:
    untested = get_untested_deployments(db)
    result = []
    for d in untested:
        if not d.affected_verticals:
            continue
        if vertical in d.affected_verticals or "all" in d.affected_verticals:
            result.append(d)
    return result


def get_tenant_test_status(
    db: Session, company_id: str, vertical: str, tenant_created_at: datetime
) -> dict:
    untested = get_untested_for_vertical(db, vertical)
    # Only flag deployments that happened AFTER the tenant was created
    relevant = [d for d in untested if d.deployed_at > tenant_created_at]
    last_tested = (
        db.query(AdminDeployment)
        .filter(AdminDeployment.is_tested == True)  # noqa: E712
        .order_by(AdminDeployment.tested_at.desc())
        .first()
    )
    return {
        "is_tested": len(relevant) == 0,
        "untested_deployments": [
            {
                "id": d.id,
                "description": d.description,
                "deployed_at": d.deployed_at.isoformat(),
                "affected_verticals": d.affected_verticals,
                "affected_features": d.affected_features,
            }
            for d in relevant
        ],
        "last_tested_at": last_tested.tested_at.isoformat() if last_tested and last_tested.tested_at else None,
    }


def mark_deployments_tested(db: Session, vertical: str, audit_run_id: str) -> int:
    """Called when an audit run passes. Marks relevant untested deployments as tested."""
    untested = get_untested_for_vertical(db, vertical) if vertical != "all" else get_untested_deployments(db)
    now = datetime.now(timezone.utc)
    count = 0
    for d in untested:
        d.is_tested = True
        d.tested_at = now
        d.test_run_id = audit_run_id
        count += 1
    db.commit()
    return count


def list_deployments(db: Session, limit: int = 50) -> list[AdminDeployment]:
    return (
        db.query(AdminDeployment)
        .order_by(AdminDeployment.deployed_at.desc())
        .limit(limit)
        .all()
    )


def manually_mark_tested(db: Session, deployment_id: str) -> AdminDeployment:
    dep = db.query(AdminDeployment).filter(AdminDeployment.id == deployment_id).first()
    if not dep:
        raise ValueError("Deployment not found")
    dep.is_tested = True
    dep.tested_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(dep)
    return dep
