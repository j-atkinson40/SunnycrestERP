"""Tenant kanban endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.company import Company
from app.models.platform_user import PlatformUser
from app.services.admin import tenant_kanban_service

router = APIRouter()


@router.get("/kanban")
def kanban(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    return tenant_kanban_service.get_kanban(db)


@router.get("/lookup")
def tenant_lookup(
    q: str | None = None,
    limit: int = 25,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Lightweight tenant search for picker UI.

    Returns a flat list of {id, slug, name, vertical} for tenants
    whose name OR slug matches the query (ILIKE). Empty query
    returns the first `limit` companies sorted by name.

    Used by the Visual Editor's tenant_override scope selector
    (relocation phase, May 2026).
    """
    capped = max(1, min(limit, 100))
    query = db.query(Company).filter(Company.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Company.name.ilike(like), Company.slug.ilike(like)))
    rows = query.order_by(Company.name).limit(capped).all()
    return [
        {"id": c.id, "slug": c.slug, "name": c.name, "vertical": c.vertical}
        for c in rows
    ]


@router.get("/{company_id}/detail")
def tenant_detail(
    company_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        return tenant_kanban_service.get_tenant_detail(db, company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
