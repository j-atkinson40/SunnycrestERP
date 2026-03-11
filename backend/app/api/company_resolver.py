from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company


def get_company_slug(request: Request) -> str:
    """
    Extract company slug using a dual strategy:
    1. Check X-Company-Slug header (works for dev and production without subdomains)
    2. Extract from subdomain (acme.sunnycrest.app -> "acme")

    Returns empty string if no company context found (root domain).
    """
    header_slug = request.headers.get("X-Company-Slug")
    if header_slug:
        return header_slug.lower().strip()

    host = request.headers.get("host", "")
    hostname = host.split(":")[0]
    parts = hostname.split(".")

    if len(parts) >= 3 and parts[0] not in ("www", "api"):
        return parts[0]

    return ""


def get_current_company(
    slug: str = Depends(get_company_slug),
    db: Session = Depends(get_db),
) -> Company:
    """
    Resolve the company from the slug.
    Raises 404 if not found or inactive.
    Used on all tenant-scoped routes.
    """
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found. Please access via a company subdomain.",
        )

    company = (
        db.query(Company)
        .filter(Company.slug == slug, Company.is_active.is_(True))
        .first()
    )

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company '{slug}' not found or is inactive.",
        )

    return company


def get_optional_company(
    slug: str = Depends(get_company_slug),
    db: Session = Depends(get_db),
) -> Company | None:
    """
    Same as get_current_company but returns None instead of raising.
    Used for routes that work both with and without a company context.
    """
    if not slug:
        return None

    return (
        db.query(Company)
        .filter(Company.slug == slug, Company.is_active.is_(True))
        .first()
    )
