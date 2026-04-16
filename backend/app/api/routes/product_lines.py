"""Tenant product lines — replaces the extension library endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import product_line_service

router = APIRouter()


class EnableLineRequest(BaseModel):
    line_key: str
    display_name: str | None = None


@router.get("")
def list_lines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lines = product_line_service.list_lines(db, current_user.company_id)
    return [
        {
            "id": l.id,
            "line_key": l.line_key,
            "display_name": l.display_name,
            "is_enabled": l.is_enabled,
            "sort_order": l.sort_order,
        }
        for l in lines
    ]


@router.get("/available")
def list_available(current_user: User = Depends(get_current_user)):
    return product_line_service.get_available_lines()


@router.post("/enable")
def enable(
    data: EnableLineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    line = product_line_service.enable_line(
        db, current_user.company_id, data.line_key, data.display_name
    )
    return {
        "id": line.id,
        "line_key": line.line_key,
        "display_name": line.display_name,
        "is_enabled": line.is_enabled,
    }


@router.post("/disable/{line_key}")
def disable(
    line_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    line = product_line_service.disable_line(db, current_user.company_id, line_key)
    if not line:
        raise HTTPException(status_code=404, detail="Product line not found")
    return {"id": line.id, "line_key": line.line_key, "is_enabled": line.is_enabled}
