"""Opas Order List and the shortened sales order read.

⚠️ READS, PLUS ONE SETTINGS WRITE. Asking is a read. Removing a pill can teach
the phrasing, which stores the corrected question on the company's existing
`settings_json`. No migration. The caller's company is the only company read.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services.order_list.proposal import propose
from app.services.order_list.question import OrderQuestion
from app.services.order_list.service import ask, sales_order_summary, today_for

router = APIRouter()


class AskBody(BaseModel):
    phrase: str | None = None
    question: OrderQuestion | None = None
    remove_pill: str | None = None
    teach_phrase: str | None = None


def _role_slug(db: Session, user: User) -> str | None:
    if not user.role_id:
        return None
    role = db.get(Role, user.role_id)
    return role.slug if role is not None else None


@router.post("/ask")
def ask_orders(
    body: AskBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One phrase or one edited question in, orders and totals out.

    No `response_model`: grouped rows omit empty groups and absent facts, and a
    response model would put those keys back.
    """
    company = db.get(Company, current_user.company_id)
    return ask(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        role_slug=_role_slug(db, current_user),
        phrase=body.phrase,
        question=body.question,
        remove_pill_id=body.remove_pill,
        teach_phrase=body.teach_phrase,
        today=today_for(company),
        propose=propose,
    )


@router.get("/orders/{order_id}")
def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The shortened sales order. 404 when it is not this caller's order."""
    company = db.get(Company, current_user.company_id)
    summary = sales_order_summary(
        db,
        current_user.company_id,
        order_id,
        today_for(company),
        role_slug=_role_slug(db, current_user),
        user_id=current_user.id,
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="Unknown order")
    return summary
