"""Opas Order List and the shortened sales order read.

⚠️ READS, PLUS ONE SETTINGS WRITE. Asking is a read. Removing a pill can teach
the phrasing, which stores the corrected question on the company's existing
`settings_json`. No migration. The caller's company is the only company read.
"""
from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services.order_list import cemetery, customer, decision_log
from app.services.order_list.proposal import propose
from app.services.order_list.question import OrderQuestion
from app.services.order_list.service import ask, sales_order_summary, today_for

router = APIRouter()


class AskBody(BaseModel):
    phrase: str | None = None
    question: OrderQuestion | None = None
    remove_pill: str | None = None
    teach_phrase: str | None = None
    #: Which pane was in front when this was typed.
    #:
    #: ⚠️ IT IS FOR THE DECISION LOG, AND IT IS THE ONE THING THE SERVER CANNOT DERIVE.
    #: "only hopkins" is a refinement with a list open and nothing at all in a cold bar,
    #: so the evidence has to record which it was or the test set built from it has cases
    #: with no single right answer. Optional, because an older bundle does not send it
    #: and a missing value is better recorded as "bar" than as a request refused.
    front: str | None = None


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

    # ⚠️ THE MODEL'S OWN ACCOUNT OF ITSELF, COLLECTED BY A CALLBACK. `ask` calls
    # `propose` positionally and must not have to know about logging, so the observer is
    # bound here. `persist=False` inside the door means there is no
    # `intelligence_executions` row for it — this is the only record that a model was
    # consulted at all.
    seen: dict = {}
    recording_propose = partial(propose, observer=seen.update)

    body_out = ask(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        role_slug=_role_slug(db, current_user),
        phrase=body.phrase,
        question=body.question,
        remove_pill_id=body.remove_pill,
        teach_phrase=body.teach_phrase,
        today=today_for(company),
        propose=recording_propose,
    )

    # ⚠️ AFTER THE ANSWER, AND IT CANNOT CHANGE IT. `record_ask` swallows its own
    # exceptions and rolls back its own failed transaction; a director asking "what's
    # going out Friday" gets the answer whether or not the row landed.
    decision_log.record_ask(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        phrase=body.phrase,
        body=body_out,
        surface=decision_log.surface_for(body.question, body.front),
        proposed_by="model" if seen.get("accepted") else "rules",
        model_latency_ms=seen.get("latency_ms"),
        # ⚠️ `None` WHEN THE MODEL WAS NEVER CONSULTED, which the CHECK constraint
        # requires to pair with `proposed_by != 'model'`. A `False` here would claim the
        # model was asked and refused, and "never asked" is a different fact.
        model_accepted=seen.get("accepted") if seen.get("called") else None,
        model_refused_reason=seen.get("reason"),
    )
    return body_out


@router.get("/customers/{customer_id}")
def get_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The Customer Pane. 404 when it is not this caller's customer.

    ⚠️ NO `response_model`, THE SAME REASON THE OTHER TWO READS GIVE: absent facts are
    omitted (a customer with no address has no meta line, one with no contacts has no
    People tab), and a response model would put those keys back as nulls — which is the
    "never shown as blank labels" rule, broken by a schema.

    ⚠️ AND IT IS A PURE READ. Opening a pane from a link or a row logs nothing; the
    decision log records BAR INTERPRETATIONS, and this endpoint is reached by clicking.
    The bar's own customer open is logged in `ask`, where the phrase exists.
    """
    company = db.get(Company, current_user.company_id)
    detail = customer.customer_detail(
        db, current_user.company_id, customer_id, today_for(company),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown customer")
    return detail


@router.get("/cemeteries/{cemetery_id}")
def get_cemetery(
    cemetery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The Cemetery Pane. 404 when it is not this caller's cemetery.

    ⚠️ NO `response_model`, for the reason the other reads give: absent facts are
    omitted, and a schema would put them back as nulls. It matters more here than
    anywhere — on today's data every optional field is empty, so a response model would
    turn four honest records into a wall of `null`.

    ⚠️ AND A PURE READ, LOGGING NOTHING. The decision log records BAR interpretations;
    this endpoint is reached by clicking a row or a link. The bar's own cemetery open is
    logged in `ask`, where the phrase exists.
    """
    company = db.get(Company, current_user.company_id)
    detail = cemetery.cemetery_detail(
        db, current_user.company_id, cemetery_id, today_for(company),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown cemetery")
    return detail


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
