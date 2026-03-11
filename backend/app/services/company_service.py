from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company import CompanyUpdate
from app.services import audit_service


def get_company(db: Session, company_id: str) -> Company:
    """Fetch company by ID, raise 404 if not found."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        )
    return company


def update_company(
    db: Session,
    company_id: str,
    data: CompanyUpdate,
    actor_id: str | None = None,
) -> Company:
    """Update company settings. Only non-None fields are applied."""
    company = get_company(db, company_id)

    tracked_fields = [
        "name", "address_street", "address_city", "address_state",
        "address_zip", "phone", "email", "timezone", "logo_url",
    ]
    old_data = {f: getattr(company, f) for f in tracked_fields}

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    new_data = {f: getattr(company, f) for f in tracked_fields}
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db, company_id, "updated", "company", company_id,
            user_id=actor_id, changes=changes,
        )

    db.commit()
    db.refresh(company)
    return company
