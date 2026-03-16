"""Platform admin — tenant management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services import super_admin_service

router = APIRouter()


@router.get("/dashboard")
def get_platform_dashboard(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Full platform dashboard — system health, tenant list, billing summary."""
    return super_admin_service.get_super_dashboard(db)


@router.get("/")
def list_tenants(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all tenants with user counts and subscription status."""
    from app.models.company import Company
    from app.models.subscription import Subscription
    from app.models.user import User

    query = db.query(Company)
    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(Company.is_active == is_active)

    total = query.count()
    companies = query.order_by(Company.name).offset(offset).limit(limit).all()

    items = []
    for c in companies:
        user_count = (
            db.query(User)
            .filter(User.company_id == c.id, User.is_active.is_(True))
            .count()
        )
        sub = (
            db.query(Subscription)
            .filter(
                Subscription.company_id == c.id,
                Subscription.status.in_(["active", "trialing", "past_due"]),
            )
            .first()
        )
        items.append({
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "is_active": c.is_active,
            "user_count": user_count,
            "subscription_status": sub.status if sub else None,
            "plan_name": sub.plan.name if sub and sub.plan else None,
            "created_at": c.created_at,
        })

    return {"items": items, "total": total}


@router.get("/{tenant_id}")
def get_tenant(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Get detailed tenant information."""
    from app.models.company import Company
    from app.models.company_module import CompanyModule
    from app.models.subscription import Subscription
    from app.models.sync_log import SyncLog
    from app.models.user import User

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")

    users = (
        db.query(User)
        .filter(User.company_id == tenant_id)
        .order_by(User.first_name)
        .all()
    )

    modules = (
        db.query(CompanyModule)
        .filter(CompanyModule.company_id == tenant_id)
        .all()
    )

    sub = (
        db.query(Subscription)
        .filter(Subscription.company_id == tenant_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    recent_syncs = (
        db.query(SyncLog)
        .filter(SyncLog.company_id == tenant_id)
        .order_by(SyncLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "is_active": company.is_active,
        "created_at": company.created_at,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "is_active": u.is_active,
                "role_id": u.role_id,
            }
            for u in users
        ],
        "modules": [
            {"module": m.module, "enabled": m.enabled}
            for m in modules
        ],
        "subscription": {
            "status": sub.status,
            "plan_name": sub.plan.name if sub and sub.plan else None,
            "billing_interval": sub.billing_interval if sub else None,
        } if sub else None,
        "recent_syncs": [
            {
                "id": s.id,
                "direction": s.direction,
                "entity_type": s.entity_type,
                "status": s.status,
                "created_at": s.created_at,
                "records_synced": s.records_synced,
                "error_message": s.error_message,
            }
            for s in recent_syncs
        ],
    }


@router.patch("/{tenant_id}")
def update_tenant(
    tenant_id: str,
    data: dict,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Update tenant configuration — activate, deactivate, etc."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")

    allowed_fields = {"is_active", "name"}
    for key, value in data.items():
        if key in allowed_fields:
            setattr(company, key, value)

    db.commit()
    db.refresh(company)
    return {"id": company.id, "name": company.name, "is_active": company.is_active}
