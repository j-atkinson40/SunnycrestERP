"""Per-entity peek builders — follow-up 4.

One builder per entity type. Each takes (db, user, entity_id),
returns a `PeekResponse` with the small summary shape the frontend
renders in the hover/click peek panels.

Pattern mirrors Phase 5 `_DIRECT_QUERIES` + follow-up 2
`_RELATED_ENTITY_BUILDERS`: module-level dict of callables keyed on
entity_type. Adding a new entity = append a builder + register in
`PEEK_BUILDERS`. No architectural change, no schema change.

Tenant isolation: every query filters by `user.company_id`. Users
only peek entities their tenant owns. For cross-tenant entities
(future), an explicit permission check would land here — for the 6
shipped types, tenant-scope is the contract.

Keep each builder small (~30-40 lines) and avoid nested relation
traversal in the payload. Peek is about the 5 fields users scan,
not the 50 fields on the detail page. If a field requires a JOIN,
keep the JOIN but project only the needed column.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.peek.types import (
    EntityNotFound,
    PeekResponse,
    UnknownEntityType,
)


# ── fh_case ─────────────────────────────────────────────────────────


def _peek_fh_case(
    db: Session, user: User, entity_id: str
) -> PeekResponse:
    from app.models.funeral_case import CaseDeceased, CaseService, FuneralCase

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == entity_id,
            FuneralCase.company_id == user.company_id,
        )
        .first()
    )
    if case is None:
        raise EntityNotFound(f"fh_case {entity_id!r} not found")

    # Deceased satellite — peek shows deceased name + DOD prominently.
    dec: CaseDeceased | None = (
        db.query(CaseDeceased)
        .filter(CaseDeceased.case_id == case.id)
        .first()
    )
    deceased_name = None
    date_of_death = None
    if dec is not None:
        parts = [
            dec.first_name,
            dec.middle_name,
            dec.last_name,
        ]
        deceased_name = " ".join(p for p in parts if p) or None
        date_of_death = dec.date_of_death

    # Next service — single CaseService satellite (one per case).
    # Falls back gracefully if absent.
    next_service_date: date | None = None
    try:
        svc = (
            db.query(CaseService)
            .filter(CaseService.case_id == case.id)
            .first()
        )
        if svc is not None:
            next_service_date = svc.service_date
    except Exception:
        next_service_date = None

    display_label = (
        f"{deceased_name} — Case {case.case_number}"
        if deceased_name
        else f"Case {case.case_number}"
    )

    return PeekResponse(
        entity_type="fh_case",
        entity_id=case.id,
        display_label=display_label,
        navigate_url=f"/fh/cases/{case.id}",
        peek={
            "case_number": case.case_number,
            "deceased_name": deceased_name,
            "date_of_death": (
                date_of_death.isoformat() if date_of_death else None
            ),
            "current_step": case.current_step,
            "next_service_date": (
                next_service_date.isoformat() if next_service_date else None
            ),
            "status": case.status,
        },
    )


# ── invoice ─────────────────────────────────────────────────────────


def _peek_invoice(
    db: Session, user: User, entity_id: str
) -> PeekResponse:
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    inv = (
        db.query(Invoice)
        .filter(
            Invoice.id == entity_id,
            Invoice.company_id == user.company_id,
        )
        .first()
    )
    if inv is None:
        raise EntityNotFound(f"invoice {entity_id!r} not found")

    customer_name: str | None = None
    customer = (
        db.query(Customer)
        .filter(Customer.id == inv.customer_id)
        .first()
    )
    if customer is not None:
        customer_name = customer.name

    return PeekResponse(
        entity_type="invoice",
        entity_id=inv.id,
        display_label=f"Invoice {inv.number}",
        navigate_url=f"/ar/invoices/{inv.id}",
        peek={
            "invoice_number": inv.number,
            "status": inv.status,
            "amount_total": _dec(inv.total),
            "amount_paid": _dec(inv.amount_paid),
            "amount_due": _dec(_as_decimal(inv.total) - _as_decimal(inv.amount_paid)),
            "customer_name": customer_name,
            "invoice_date": _iso_or_none(inv.invoice_date),
            "due_date": _iso_or_none(inv.due_date),
        },
    )


# ── sales_order ─────────────────────────────────────────────────────


def _peek_sales_order(
    db: Session, user: User, entity_id: str
) -> PeekResponse:
    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder, SalesOrderLine

    so = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.id == entity_id,
            SalesOrder.company_id == user.company_id,
        )
        .first()
    )
    if so is None:
        raise EntityNotFound(f"sales_order {entity_id!r} not found")

    customer_name: str | None = None
    customer = (
        db.query(Customer)
        .filter(Customer.id == so.customer_id)
        .first()
    )
    if customer is not None:
        customer_name = customer.name

    line_count = (
        db.query(SalesOrderLine)
        .filter(SalesOrderLine.sales_order_id == so.id)
        .count()
    )

    return PeekResponse(
        entity_type="sales_order",
        entity_id=so.id,
        display_label=f"Order {so.number}",
        navigate_url=f"/order-station/orders/{so.id}",
        peek={
            "order_number": so.number,
            "status": so.status,
            "customer_name": customer_name,
            "deceased_name": getattr(so, "deceased_name", None),
            "order_date": _iso_or_none(so.order_date),
            "required_date": _iso_or_none(so.required_date),
            "total": _dec(so.total),
            "line_count": line_count,
        },
    )


# ── task ────────────────────────────────────────────────────────────


def _peek_task(
    db: Session, user: User, entity_id: str
) -> PeekResponse:
    from app.models.task import Task
    from app.models.user import User as UserModel

    task = (
        db.query(Task)
        .filter(
            Task.id == entity_id,
            Task.company_id == user.company_id,
        )
        .first()
    )
    if task is None:
        raise EntityNotFound(f"task {entity_id!r} not found")

    assignee_name: str | None = None
    if task.assignee_user_id:
        assignee = (
            db.query(UserModel)
            .filter(UserModel.id == task.assignee_user_id)
            .first()
        )
        if assignee is not None:
            parts = [assignee.first_name, assignee.last_name]
            assignee_name = " ".join(p for p in parts if p) or assignee.email

    return PeekResponse(
        entity_type="task",
        entity_id=task.id,
        display_label=task.title,
        navigate_url=f"/tasks/{task.id}",
        peek={
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "assignee_name": assignee_name,
            "due_date": (
                task.due_date.isoformat() if task.due_date else None
            ),
            "related_entity_type": task.related_entity_type,
            "related_entity_id": task.related_entity_id,
        },
    )


# ── contact ─────────────────────────────────────────────────────────


def _peek_contact(
    db: Session, user: User, entity_id: str
) -> PeekResponse:
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact

    contact = (
        db.query(Contact)
        .filter(
            Contact.id == entity_id,
            Contact.company_id == user.company_id,
        )
        .first()
    )
    if contact is None:
        raise EntityNotFound(f"contact {entity_id!r} not found")

    company_name: str | None = None
    if contact.master_company_id:
        ce = (
            db.query(CompanyEntity)
            .filter(CompanyEntity.id == contact.master_company_id)
            .first()
        )
        if ce is not None:
            company_name = ce.name

    return PeekResponse(
        entity_type="contact",
        entity_id=contact.id,
        display_label=contact.name,
        navigate_url=f"/vault/crm/contacts/{contact.id}",
        peek={
            "name": contact.name,
            "title": contact.title,
            "role": getattr(contact, "role", None),
            "phone": contact.phone,
            "email": contact.email,
            "is_primary": getattr(contact, "is_primary", None),
            "company_name": company_name,
            "master_company_id": contact.master_company_id,
        },
    )


# ── saved_view ──────────────────────────────────────────────────────


def _peek_saved_view(
    db: Session, user: User, entity_id: str
) -> PeekResponse:
    """Peek for a saved view row — a meta-entity.

    Shows title, entity_type the view queries, current presentation
    mode, and filter/sort counts as a signal of view complexity. We
    deliberately do NOT execute the view here — peek must stay fast
    and executing arbitrary saved views blows past the 100ms p50
    budget. Users who want a live count open the detail page or
    dashboard widget.
    """
    from app.services.saved_views import (
        SavedView,
        SavedViewError,
        get_saved_view,
    )

    try:
        view: SavedView = get_saved_view(db, user=user, view_id=entity_id)
    except SavedViewError as exc:
        raise EntityNotFound(f"saved_view {entity_id!r}: {exc}") from exc

    cfg = view.config
    filter_count = len(cfg.query.filters or [])
    sort_count = len(cfg.query.sort or [])

    return PeekResponse(
        entity_type="saved_view",
        entity_id=view.id,
        display_label=view.title,
        navigate_url=f"/saved-views/{view.id}",
        peek={
            "title": view.title,
            "description": view.description,
            "entity_type": cfg.query.entity_type,
            "presentation_mode": cfg.presentation.mode,
            "filter_count": filter_count,
            "sort_count": sort_count,
            "visibility": cfg.permissions.visibility,
            "owner_user_id": cfg.permissions.owner_user_id,
        },
    )


# ── Dispatch table ──────────────────────────────────────────────────


# Callable signature: (db, user, entity_id) -> PeekResponse.
PEEK_BUILDERS: dict[
    str, Callable[[Session, User, str], PeekResponse]
] = {
    "fh_case": _peek_fh_case,
    "invoice": _peek_invoice,
    "sales_order": _peek_sales_order,
    "task": _peek_task,
    "contact": _peek_contact,
    "saved_view": _peek_saved_view,
}


def build_peek(
    db: Session, *, user: User, entity_type: str, entity_id: str
) -> PeekResponse:
    """Public dispatcher. Unknown entity_type raises `UnknownEntityType`;
    builders raise `EntityNotFound` on missing row / tenant miss."""
    builder = PEEK_BUILDERS.get(entity_type)
    if builder is None:
        raise UnknownEntityType(
            f"No peek builder for entity_type {entity_type!r}. "
            f"Available: {sorted(PEEK_BUILDERS.keys())}"
        )
    return builder(db, user, entity_id)


# ── Small helpers ───────────────────────────────────────────────────


def _dec(value: Any) -> float | None:
    """Serialize Decimal to float for JSON payload. Peek is display-
    oriented; Decimal precision isn't meaningful here."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


__all__ = ["PEEK_BUILDERS", "build_peek"]
