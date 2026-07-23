"""Command Bar entity-portal hydration — S-1 (§4.2).

Second-call hydration for the command bar's entity portal cards.
`/command-bar/query` stays untouched (its BLOCKING latency gate is
sacrosanct); when the user HIGHLIGHTS an entity result, the frontend
debounces ~150ms and fetches this endpoint for the full card payload.

Architecture — adapter over the fragmented entity models, wrapping
the peek substrate:

  - For the four entity types peek already covers (contact, fh_case,
    sales_order, invoice) the portal builder CALLS the peek builder
    for the base payload and enriches it with portal-only sections
    (pivots, related lists, gated financials). Zero duplication.
  - company_entity (the FLAGSHIP customer/account card) and product
    get their own base builders.
  - The 4-way contact fragmentation (Contact / CustomerContact /
    VendorContact / FHCaseContact — see docs/DEBT.md) is adapted,
    not unified: v1 reads CRM `Contact` rows only (matching what
    Vault CRM shows). When the CRM unification (Vault audit Option
    B) lands, builder internals swap; the response contract does
    not change. Same for the CompanyEntity↔Customer split:
    CompanyEntity is the canonical identity; Customer (AR account)
    is joined via `Customer.master_company_id` at hydration time.

Permission gating: the financial-standing section reuses the SAME
pipeline as the registry/VaultServiceDescriptor gates —
`permission_service.user_has_permission` — keyed on the existing
catalog permission `invoice.approve` (the finance-tier key the
triage financial queues gate on). Users without it get the card
with the section quietly omitted (§4.2: "surfaces the user has
permission to see appear, others quietly omit").

Tenant isolation: every query filters by `user.company_id`. The
company card renders strictly tenant-scoped data — nothing crosses
the cross-tenant boundary outside the existing consent-gated
sharing mechanisms (none of which this module touches).

Latency: BLOCKING gate at tests/test_command_bar_portal_latency.py
(p50 < 150 ms / p99 < 400 ms).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.peek.builders import PEEK_BUILDERS
from app.services.peek.types import EntityNotFound, UnknownEntityType


logger = logging.getLogger(__name__)


# ── Response contract ────────────────────────────────────────────────
# Envelope is model-agnostic: per-type payload rides `portal`;
# `pivots` and `actions` are shared shapes every card renders the
# same way. S-2..S-5 consume this contract unchanged.


@dataclass
class PortalResponse:
    entity_type: str
    entity_id: str
    display_label: str
    navigate_url: str
    portal: dict[str, Any]
    # Relational pivots — click-through to another entity's card
    # without navigation (§4.2 "action affordances and relational
    # pivots"). Shape: {entity_type, entity_id, label, context}.
    pivots: list[dict[str, Any]] = field(default_factory=list)
    # Card-level affordances. Shape: {kind: tel|mailto|navigate,
    # label, value}. `tel:` is the ruled v1 click-to-call transport.
    actions: list[dict[str, Any]] = field(default_factory=list)
    # Section keys omitted for permission reasons — lets the card
    # render nothing (quietly) rather than an empty panel.
    omitted_sections: list[str] = field(default_factory=list)


def _money(v: Decimal | float | None) -> float | None:
    return float(v) if v is not None else None


def _iso(d: Any) -> str | None:
    # Brief cards show dates, not timestamps — collapse datetimes to
    # their date part so the renderer never displays a raw ISO stamp.
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


# ── company_entity — the FLAGSHIP card (§4.2's customer example) ─────


def _portal_company_entity(
    db: Session, user: User, entity_id: str
) -> PortalResponse:
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.sales_order import SalesOrder

    ce = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.id == entity_id,
            CompanyEntity.company_id == user.company_id,
        )
        .first()
    )
    if ce is None:
        raise EntityNotFound(f"company_entity {entity_id!r} not found")

    # Identity roles — render as small neutral descriptors.
    roles = [
        label
        for flag, label in (
            (ce.is_funeral_home, "Funeral home"),
            (ce.is_cemetery, "Cemetery"),
            (ce.is_customer, "Customer"),
            (ce.is_vendor, "Vendor"),
            (ce.is_licensee, "Licensee"),
            (ce.is_crematory, "Crematory"),
        )
        if flag
    ]

    # Contacts — CRM Contact rows only (v1 fragmentation stance:
    # CustomerContact / VendorContact / FHCaseContact rows are NOT
    # visible here; see module docstring).
    contacts = (
        db.query(Contact)
        .filter(
            Contact.company_id == user.company_id,
            Contact.master_company_id == ce.id,
            Contact.is_active.is_(True),
        )
        .order_by(Contact.updated_at.desc())
        .limit(3)
        .all()
    )

    # AR account (Customer) via the master_company_id adapter join.
    customer: Customer | None = (
        db.query(Customer)
        .filter(
            Customer.company_id == user.company_id,
            Customer.master_company_id == ce.id,
        )
        .first()
    )

    # Recent + open orders through the AR account, newest first.
    recent_orders: list[SalesOrder] = []
    open_order_count = 0
    if customer is not None:
        recent_orders = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == user.company_id,
                SalesOrder.customer_id == customer.id,
            )
            .order_by(SalesOrder.created_at.desc())
            .limit(5)
            .all()
        )
        open_order_count = (
            db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.company_id == user.company_id,
                SalesOrder.customer_id == customer.id,
                SalesOrder.status.notin_(("delivered", "cancelled", "invoiced")),
            )
            .scalar()
            or 0
        )

    portal: dict[str, Any] = {
        "name": ce.name,
        "legal_name": ce.legal_name,
        "roles": roles,
        "phone": ce.phone,
        "email": ce.email,
        "website": ce.website,
        "city": ce.city,
        "state": ce.state,
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "title": c.title,
                "phone": c.phone,
                "email": c.email,
            }
            for c in contacts
        ],
        "recent_orders": [
            {
                "id": o.id,
                "number": o.number,
                "status": o.status,
                "total": _money(o.total),
                "order_date": _iso(o.order_date),
            }
            for o in recent_orders
        ],
        "open_order_count": int(open_order_count),
    }

    omitted: list[str] = []
    # Financial standing — permission-gated through the SAME pipeline
    # as the registry gates (permission_service), key `invoice.approve`.
    from app.services.permission_service import user_has_permission

    if user_has_permission(user, db, "invoice.approve"):
        outstanding = Decimal("0")
        overdue_count = 0
        overdue_total = Decimal("0")
        if customer is not None:
            rows = (
                db.query(Invoice)
                .filter(
                    Invoice.company_id == user.company_id,
                    Invoice.customer_id == customer.id,
                    Invoice.status.notin_(("paid", "voided")),
                )
                .all()
            )
            from datetime import datetime, timezone

            # timezone-aware comparison — invoices.due_date is
            # timestamptz (see the financials_board date-vs-datetime
            # 500 caught in the e2e tail; this avoids that class).
            _now = datetime.now(timezone.utc)
            for inv in rows:
                balance = (inv.total or Decimal("0")) - (
                    inv.amount_paid or Decimal("0")
                )
                outstanding += balance
                if inv.due_date is not None and inv.due_date < _now and balance > 0:
                    overdue_count += 1
                    overdue_total += balance
        portal["financial"] = {
            "current_balance": _money(
                customer.current_balance if customer else None
            ),
            "credit_limit": _money(customer.credit_limit if customer else None),
            "payment_terms": customer.payment_terms if customer else None,
            "outstanding": _money(outstanding),
            "overdue_count": overdue_count,
            "overdue_total": _money(overdue_total),
        }
    else:
        omitted.append("financial")

    pivots = [
        {
            "entity_type": "contact",
            "entity_id": c.id,
            "label": c.name,
            "context": c.title or "Contact",
        }
        for c in contacts
    ] + [
        {
            "entity_type": "sales_order",
            "entity_id": o.id,
            "label": o.number,
            "context": o.status,
        }
        for o in recent_orders[:3]
    ]

    actions = []
    if ce.phone:
        actions.append({"kind": "tel", "label": "Call", "value": ce.phone})
    if ce.email:
        actions.append({"kind": "mailto", "label": "Email", "value": ce.email})
    actions.append(
        {
            "kind": "navigate",
            "label": "Open profile",
            "value": f"/vault/crm/companies/{ce.id}",
        }
    )

    return PortalResponse(
        entity_type="company_entity",
        entity_id=ce.id,
        display_label=ce.name,
        navigate_url=f"/vault/crm/companies/{ce.id}",
        portal=portal,
        pivots=pivots,
        actions=actions,
        omitted_sections=omitted,
    )


# ── peek-wrapped builders (contact / fh_case / sales_order / invoice) ─


def _wrap_peek(
    entity_type: str,
    db: Session,
    user: User,
    entity_id: str,
) -> PortalResponse:
    base = PEEK_BUILDERS[entity_type](db, user, entity_id)
    portal = dict(base.peek)
    # Presentation normalization at the portal seam (peek builders
    # stay untouched): Brief cards show dates, not timestamps, and
    # the renderers read `total`/`balance` regardless of source.
    for k, v in list(portal.items()):
        if (
            isinstance(v, str)
            and "T" in v
            and (k.endswith("_date") or k == "date_of_death")
        ):
            portal[k] = v.split("T", 1)[0]
    portal.setdefault("total", portal.get("amount_total"))
    portal.setdefault("balance", portal.get("amount_due"))
    return PortalResponse(
        entity_type=base.entity_type,
        entity_id=base.entity_id,
        display_label=base.display_label,
        navigate_url=base.navigate_url,
        portal=portal,
    )


def _portal_contact(db: Session, user: User, entity_id: str) -> PortalResponse:
    resp = _wrap_peek("contact", db, user, entity_id)
    p = resp.portal
    if p.get("master_company_id"):
        resp.pivots.append(
            {
                "entity_type": "company_entity",
                "entity_id": p["master_company_id"],
                "label": p.get("company_name") or "Company",
                "context": "Company",
            }
        )
    if p.get("phone"):
        resp.actions.append({"kind": "tel", "label": "Call", "value": p["phone"]})
    if p.get("email"):
        resp.actions.append(
            {"kind": "mailto", "label": "Email", "value": p["email"]}
        )
    resp.actions.append(
        {"kind": "navigate", "label": "Open profile", "value": resp.navigate_url}
    )
    return resp


def _portal_fh_case(db: Session, user: User, entity_id: str) -> PortalResponse:
    resp = _wrap_peek("fh_case", db, user, entity_id)
    resp.actions.append(
        {"kind": "navigate", "label": "Open case", "value": resp.navigate_url}
    )
    return resp


def _portal_sales_order(
    db: Session, user: User, entity_id: str
) -> PortalResponse:
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.sales_order import SalesOrder

    resp = _wrap_peek("sales_order", db, user, entity_id)

    so = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.id == entity_id,
            SalesOrder.company_id == user.company_id,
        )
        .first()
    )
    if so is not None and so.customer_id:
        cust = (
            db.query(Customer).filter(Customer.id == so.customer_id).first()
        )
        if cust is not None and cust.master_company_id:
            resp.pivots.append(
                {
                    "entity_type": "company_entity",
                    "entity_id": cust.master_company_id,
                    "label": cust.name,
                    "context": "Customer",
                }
            )
        inv = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == user.company_id,
                Invoice.sales_order_id == so.id,
            )
            .first()
        )
        if inv is not None:
            resp.pivots.append(
                {
                    "entity_type": "invoice",
                    "entity_id": inv.id,
                    "label": inv.number,
                    "context": inv.status,
                }
            )
    resp.actions.append(
        {"kind": "navigate", "label": "Open order", "value": resp.navigate_url}
    )
    return resp


def _portal_invoice(db: Session, user: User, entity_id: str) -> PortalResponse:
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    resp = _wrap_peek("invoice", db, user, entity_id)

    inv = (
        db.query(Invoice)
        .filter(
            Invoice.id == entity_id,
            Invoice.company_id == user.company_id,
        )
        .first()
    )
    if inv is not None:
        if inv.customer_id:
            cust = (
                db.query(Customer).filter(Customer.id == inv.customer_id).first()
            )
            if cust is not None and cust.master_company_id:
                resp.pivots.append(
                    {
                        "entity_type": "company_entity",
                        "entity_id": cust.master_company_id,
                        "label": cust.name,
                        "context": "Customer",
                    }
                )
        if inv.sales_order_id:
            resp.pivots.append(
                {
                    "entity_type": "sales_order",
                    "entity_id": inv.sales_order_id,
                    "label": "Source order",
                    "context": "Order",
                }
            )
    resp.actions.append(
        {"kind": "navigate", "label": "Open invoice", "value": resp.navigate_url}
    )
    return resp


# ── product ─────────────────────────────────────────────────────────


def _portal_product(db: Session, user: User, entity_id: str) -> PortalResponse:
    from app.models.inventory_item import InventoryItem
    from app.models.product import Product

    prod = (
        db.query(Product)
        .filter(
            Product.id == entity_id,
            Product.company_id == user.company_id,
        )
        .first()
    )
    if prod is None:
        raise EntityNotFound(f"product {entity_id!r} not found")

    on_hand = None
    try:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.company_id == user.company_id,
                InventoryItem.product_id == prod.id,
            )
            .first()
        )
        if item is not None:
            on_hand = getattr(item, "quantity_on_hand", None)
            if on_hand is None:
                on_hand = getattr(item, "quantity", None)
    except Exception:  # inventory is optional context, never fatal
        on_hand = None

    portal = {
        "name": prod.name,
        "sku": prod.sku,
        "price": _money(prod.price),
        "unit_of_measure": prod.unit_of_measure,
        "is_active": prod.is_active,
        "on_hand": float(on_hand) if on_hand is not None else None,
        "description": (prod.description or "")[:160] or None,
    }

    return PortalResponse(
        entity_type="product",
        entity_id=prod.id,
        display_label=prod.name,
        navigate_url=f"/products/{prod.id}",
        portal=portal,
        actions=[
            {
                "kind": "navigate",
                "label": "Open product",
                "value": f"/products/{prod.id}",
            }
        ],
    )


# ── Dispatch ────────────────────────────────────────────────────────
# document + task deliberately OMITTED in S-1 (ruled scope): the
# document card renders thin (title/type/open — peek-grade, no
# portal lift), and task's transient inspect-need is already served
# by the peek system. Both can join additively later — one builder +
# one card each, no contract change.

PORTAL_BUILDERS: dict[
    str, Callable[[Session, User, str], PortalResponse]
] = {
    "company_entity": _portal_company_entity,
    "contact": _portal_contact,
    "fh_case": _portal_fh_case,
    "sales_order": _portal_sales_order,
    "invoice": _portal_invoice,
    "product": _portal_product,
}


def build_portal(
    db: Session, user: User, entity_type: str, entity_id: str
) -> PortalResponse:
    builder = PORTAL_BUILDERS.get(entity_type)
    if builder is None:
        raise UnknownEntityType(
            f"no portal builder for entity_type {entity_type!r}. "
            f"Available: {sorted(PORTAL_BUILDERS.keys())}"
        )
    return builder(db, user, entity_id)


__all__ = ["PORTAL_BUILDERS", "PortalResponse", "build_portal"]
