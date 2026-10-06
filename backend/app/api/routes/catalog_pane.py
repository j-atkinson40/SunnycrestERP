"""Opas Product List and Product pane reads.

⚠️ TENANT-SCOPED AUTH, PLATFORM-TIER DATA. Every caller must be a signed-in tenant user,
and what they read is the PLATFORM catalog — the same 52 variants for every tenant. Only
the personalization availability lookup is tenant-specific, and it is keyed off the
caller's own `company_id` rather than anything in the request, so one tenant cannot read
another's configuration by changing a parameter.

⚠️ READ-ONLY. No route here writes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import catalog_pane_service

router = APIRouter()


@router.get("/variants")
def list_variants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The catalog, ordered for grouping by kind.

    No `response_model`: the shape is DELIBERATELY SPARSE — keys are omitted when the
    underlying value is NULL, and a Pydantic model would re-introduce them as nulls, which
    is the thing the ruling forbids. The sparseness is the contract.
    """
    return {"variants": catalog_pane_service.list_variants(db)}


@router.get("/variants/{variant_template_id}")
def get_variant(
    variant_template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One variant. 404 when unknown — never an empty pane."""
    detail = catalog_pane_service.variant_detail(
        db, variant_template_id, company_id=current_user.company_id
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown variant_template_id")
    return detail
