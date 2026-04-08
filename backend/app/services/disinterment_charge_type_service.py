"""CRUD service for DisintermentChargeType — per-tenant configurable line items."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.disinterment_charge_type import DisintermentChargeType

logger = logging.getLogger(__name__)


def _active_filter():
    return DisintermentChargeType.deleted_at.is_(None)


def list_charge_types(
    db: Session, company_id: str, include_inactive: bool = False
) -> list[DisintermentChargeType]:
    """Return all charge types for a tenant, ordered by sort_order."""
    q = db.query(DisintermentChargeType).filter(
        DisintermentChargeType.company_id == company_id,
        _active_filter(),
    )
    if not include_inactive:
        q = q.filter(DisintermentChargeType.active.is_(True))
    return q.order_by(DisintermentChargeType.sort_order).all()


def get_charge_type(
    db: Session, charge_type_id: str, company_id: str
) -> DisintermentChargeType:
    ct = (
        db.query(DisintermentChargeType)
        .filter(
            DisintermentChargeType.id == charge_type_id,
            DisintermentChargeType.company_id == company_id,
            _active_filter(),
        )
        .first()
    )
    if not ct:
        raise HTTPException(status_code=404, detail="Charge type not found")
    return ct


def create_charge_type(
    db: Session, company_id: str, data
) -> DisintermentChargeType:
    """Create a new charge type for the tenant."""
    ct = DisintermentChargeType(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=data.name,
        calculation_type=data.calculation_type,
        default_rate=data.default_rate,
        requires_input=data.requires_input,
        input_label=data.input_label,
        is_hazard_pay=data.is_hazard_pay,
        sort_order=data.sort_order,
    )
    db.add(ct)
    db.commit()
    db.refresh(ct)
    logger.info("Created charge type %s: %s", ct.id, ct.name)
    return ct


def update_charge_type(
    db: Session, charge_type_id: str, company_id: str, data
) -> DisintermentChargeType:
    ct = get_charge_type(db, charge_type_id, company_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ct, field, value)
    db.commit()
    db.refresh(ct)
    return ct


def soft_delete_charge_type(
    db: Session, charge_type_id: str, company_id: str
) -> None:
    ct = get_charge_type(db, charge_type_id, company_id)
    ct.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Soft-deleted charge type %s", charge_type_id)
