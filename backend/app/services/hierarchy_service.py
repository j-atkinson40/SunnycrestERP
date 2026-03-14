"""Organizational hierarchy service — manage parent/child company relationships."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.hierarchy import CompanyChildItem, CompanyHierarchyNode


def _build_path(db: Session, company: Company) -> str:
    """Compute materialized path by walking up the parent chain."""
    parts: list[str] = [company.id]
    current = company
    while current.parent_company_id:
        parent = db.query(Company).filter(Company.id == current.parent_company_id).first()
        if not parent:
            break
        parts.append(parent.id)
        current = parent
    parts.reverse()
    return ".".join(parts)


def _rebuild_subtree_paths(db: Session, company: Company) -> None:
    """Recursively update hierarchy_path for a company and all descendants."""
    company.hierarchy_path = _build_path(db, company)
    children = (
        db.query(Company).filter(Company.parent_company_id == company.id).all()
    )
    for child in children:
        _rebuild_subtree_paths(db, child)


def set_parent(
    db: Session,
    company_id: str,
    parent_company_id: str | None,
    hierarchy_level: str | None,
) -> Company:
    """Set or clear a company's parent, updating materialized paths."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if parent_company_id:
        # Prevent circular reference
        if parent_company_id == company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A company cannot be its own parent",
            )
        parent = db.query(Company).filter(Company.id == parent_company_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent company not found",
            )
        # Check parent isn't a descendant (would create cycle)
        if parent.hierarchy_path and company.id in (parent.hierarchy_path or "").split("."):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set a descendant as parent (circular reference)",
            )

    company.parent_company_id = parent_company_id
    company.hierarchy_level = hierarchy_level
    _rebuild_subtree_paths(db, company)
    db.commit()
    db.refresh(company)
    return company


def get_hierarchy_tree(db: Session) -> list[CompanyHierarchyNode]:
    """Build full hierarchy tree starting from root companies."""
    all_companies = db.query(Company).filter(Company.is_active.is_(True)).all()

    # Build lookup
    by_id: dict[str, Company] = {c.id: c for c in all_companies}
    children_map: dict[str | None, list[Company]] = {}
    for c in all_companies:
        children_map.setdefault(c.parent_company_id, []).append(c)

    def _build_node(company: Company) -> CompanyHierarchyNode:
        kids = children_map.get(company.id, [])
        return CompanyHierarchyNode(
            id=company.id,
            name=company.name,
            slug=company.slug,
            hierarchy_level=company.hierarchy_level,
            hierarchy_path=company.hierarchy_path,
            parent_company_id=company.parent_company_id,
            is_active=company.is_active,
            children=[_build_node(k) for k in kids],
        )

    roots = children_map.get(None, [])
    return [_build_node(r) for r in roots]


def get_children(db: Session, company_id: str) -> list[CompanyChildItem]:
    """Get direct children of a company."""
    children = (
        db.query(Company)
        .filter(Company.parent_company_id == company_id, Company.is_active.is_(True))
        .all()
    )
    result = []
    for child in children:
        grandchildren_count = (
            db.query(Company)
            .filter(Company.parent_company_id == child.id)
            .count()
        )
        result.append(
            CompanyChildItem(
                id=child.id,
                name=child.name,
                slug=child.slug,
                hierarchy_level=child.hierarchy_level,
                is_active=child.is_active,
                children_count=grandchildren_count,
            )
        )
    return result


def get_ancestors(db: Session, company_id: str) -> list[CompanyChildItem]:
    """Walk up the parent chain and return ancestor list (root first)."""
    ancestors: list[CompanyChildItem] = []
    current = db.query(Company).filter(Company.id == company_id).first()
    if not current:
        return ancestors
    while current.parent_company_id:
        parent = db.query(Company).filter(Company.id == current.parent_company_id).first()
        if not parent:
            break
        ancestors.append(
            CompanyChildItem(
                id=parent.id,
                name=parent.name,
                slug=parent.slug,
                hierarchy_level=parent.hierarchy_level,
                is_active=parent.is_active,
                children_count=0,
            )
        )
        current = parent
    ancestors.reverse()
    return ancestors
