"""Organizational hierarchy routes — admin-only company tree management."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.hierarchy import (
    CompanyChildItem,
    CompanyHierarchyNode,
    HierarchyResponse,
    SetParentRequest,
)
from app.services import hierarchy_service

router = APIRouter()


@router.get("/tree", response_model=HierarchyResponse)
def get_hierarchy_tree(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get the full organizational hierarchy tree."""
    tree = hierarchy_service.get_hierarchy_tree(db)
    total = sum(1 for _ in _flatten(tree))
    return HierarchyResponse(tree=tree, total_companies=total)


def _flatten(nodes: list[CompanyHierarchyNode]):
    for n in nodes:
        yield n
        yield from _flatten(n.children)


@router.get("/{company_id}/children", response_model=list[CompanyChildItem])
def get_children(
    company_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get direct children of a company."""
    return hierarchy_service.get_children(db, company_id)


@router.get("/{company_id}/ancestors", response_model=list[CompanyChildItem])
def get_ancestors(
    company_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get ancestor chain for a company (root first)."""
    return hierarchy_service.get_ancestors(db, company_id)


@router.put("/{company_id}/parent")
def set_parent(
    company_id: str,
    body: SetParentRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Set or clear a company's parent in the hierarchy."""
    company = hierarchy_service.set_parent(
        db, company_id, body.parent_company_id, body.hierarchy_level
    )
    return {
        "id": company.id,
        "name": company.name,
        "parent_company_id": company.parent_company_id,
        "hierarchy_level": company.hierarchy_level,
        "hierarchy_path": company.hierarchy_path,
    }
