"""
Cemetery management service.

Handles cemetery CRUD, equipment prefill logic, and funeral home
cemetery history tracking.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.cemetery import Cemetery
from app.models.customer import Customer
from app.models.funeral_home_cemetery_history import FuneralHomeCemeteryHistory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_equipment_note(cemetery: Cemetery) -> str:
    """Build a human-readable equipment note from cemetery settings."""
    provides: list[str] = []
    if cemetery.cemetery_provides_lowering_device:
        provides.append("lowering device")
    if cemetery.cemetery_provides_grass:
        provides.append("grass service")
    if cemetery.cemetery_provides_tent:
        provides.append("tent")
    if cemetery.cemetery_provides_chairs:
        provides.append("chairs")

    if not provides:
        return "Cemetery provides no equipment — full service available."
    if len(provides) == len(["lowering_device", "grass", "tent", "chairs"]):
        return "Cemetery provides all graveside equipment."
    return f"Cemetery provides: {', '.join(provides)}."


# ---------------------------------------------------------------------------
# Cemetery CRUD
# ---------------------------------------------------------------------------


def list_cemeteries(
    db: Session,
    company_id: str,
    search: str | None = None,
    state: str | None = None,
    county: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    query = db.query(Cemetery).filter(
        Cemetery.company_id == company_id,
        Cemetery.is_active == True,  # noqa: E712
    )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Cemetery.name.ilike(pattern),
                Cemetery.city.ilike(pattern),
                Cemetery.county.ilike(pattern),
            )
        )

    if state:
        query = query.filter(Cemetery.state == state.upper())

    if county:
        query = query.filter(Cemetery.county.ilike(f"%{county}%"))

    total = query.count()
    items = (
        query.order_by(Cemetery.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_cemetery(db: Session, cemetery_id: str, company_id: str) -> Cemetery:
    cemetery = (
        db.query(Cemetery)
        .filter(
            Cemetery.id == cemetery_id,
            Cemetery.company_id == company_id,
            Cemetery.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not cemetery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cemetery not found"
        )
    return cemetery


def create_cemetery(
    db: Session,
    company_id: str,
    name: str,
    state: str | None = None,
    county: str | None = None,
    city: str | None = None,
    address: str | None = None,
    zip_code: str | None = None,
    phone: str | None = None,
    contact_name: str | None = None,
    cemetery_provides_lowering_device: bool = False,
    cemetery_provides_grass: bool = False,
    cemetery_provides_tent: bool = False,
    cemetery_provides_chairs: bool = False,
    access_notes: str | None = None,
) -> Cemetery:
    cemetery = Cemetery(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=name,
        state=state.upper() if state else None,
        county=county,
        city=city,
        address=address,
        zip_code=zip_code,
        phone=phone,
        contact_name=contact_name,
        cemetery_provides_lowering_device=cemetery_provides_lowering_device,
        cemetery_provides_grass=cemetery_provides_grass,
        cemetery_provides_tent=cemetery_provides_tent,
        cemetery_provides_chairs=cemetery_provides_chairs,
        access_notes=access_notes,
    )
    cemetery.equipment_note = _build_equipment_note(cemetery)
    db.add(cemetery)
    db.commit()
    db.refresh(cemetery)
    return cemetery


def update_cemetery(
    db: Session,
    cemetery_id: str,
    company_id: str,
    **fields,
) -> Cemetery:
    cemetery = get_cemetery(db, cemetery_id, company_id)
    for key, value in fields.items():
        if value is not None or key in (
            "access_notes",
            "contact_name",
            "phone",
        ):
            if key == "state" and isinstance(value, str):
                value = value.upper()
            setattr(cemetery, key, value)
    cemetery.equipment_note = _build_equipment_note(cemetery)
    cemetery.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cemetery)
    return cemetery


def delete_cemetery(db: Session, cemetery_id: str, company_id: str) -> None:
    cemetery = get_cemetery(db, cemetery_id, company_id)
    cemetery.is_active = False
    cemetery.updated_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------------------
# Equipment Prefill (Part 4)
# ---------------------------------------------------------------------------

# Map equipment flags to display labels
_EQUIPMENT_LABELS = {
    "lowering_device": "lowering device",
    "grass": "grass service",
    "tent": "tent",
    "chairs": "chairs",
}


def get_equipment_prefill(cemetery: Cemetery) -> dict:
    """
    Return what equipment we can provide for a given cemetery, based on
    what the cemetery handles themselves.

    Returns:
        {
          "can_provide": ["lowering_device", "grass", "tent", "chairs"],
          "cemetery_provides": ["tent"],
          "equipment_note": "Cemetery provides tent. We will suggest lowering device, grass service.",
          "suggestion_label": "Lowering Device & Grass",
          "nothing_needed": False,
        }
    """
    provides: list[str] = []
    can_provide: list[str] = []

    if cemetery.cemetery_provides_lowering_device:
        provides.append("lowering_device")
    else:
        can_provide.append("lowering_device")

    if cemetery.cemetery_provides_grass:
        provides.append("grass")
    else:
        can_provide.append("grass")

    if cemetery.cemetery_provides_tent:
        provides.append("tent")
    else:
        can_provide.append("tent")

    if cemetery.cemetery_provides_chairs:
        provides.append("chairs")
    else:
        can_provide.append("chairs")

    nothing_needed = len(can_provide) == 0

    # Build suggestion label
    if nothing_needed:
        suggestion_label = "No equipment needed"
        equipment_note = "Cemetery provides all graveside equipment. No equipment charges needed."
    else:
        can_labels = [_EQUIPMENT_LABELS[k] for k in can_provide]
        if len(can_provide) == 4:
            suggestion_label = "Full Equipment"
        elif can_provide == ["lowering_device", "grass", "tent"]:
            suggestion_label = "Full Equipment (no chairs)"
        elif can_provide == ["lowering_device", "grass"]:
            suggestion_label = "Lowering Device & Grass"
        elif can_provide == ["lowering_device"]:
            suggestion_label = "Lowering Device Only"
        elif can_provide == ["tent"]:
            suggestion_label = "Tent Only"
        elif can_provide == ["grass"]:
            suggestion_label = "Grass Only"
        else:
            suggestion_label = " & ".join(
                label.title() for label in can_labels
            )

        if provides:
            prov_labels = [_EQUIPMENT_LABELS[k] for k in provides]
            equipment_note = (
                f"Cemetery provides {', '.join(prov_labels)}. "
                f"We will suggest: {suggestion_label}."
            )
        else:
            equipment_note = f"We will suggest: {suggestion_label} (cemetery provides nothing)."

    return {
        "can_provide": can_provide,
        "cemetery_provides": provides,
        "equipment_note": equipment_note,
        "suggestion_label": suggestion_label,
        "nothing_needed": nothing_needed,
    }


# ---------------------------------------------------------------------------
# Funeral home cemetery shortlist (Part 4)
# ---------------------------------------------------------------------------

_MIN_HISTORY_RECORDS = 3


def get_fh_cemetery_shortlist(
    db: Session,
    company_id: str,
    customer_id: str,
    limit: int = 5,
) -> list[dict]:
    """
    Return the top cemeteries used by a funeral home, ordered by order_count.
    Returns empty list if fewer than MIN_HISTORY_RECORDS distinct cemeteries.
    """
    records = (
        db.query(FuneralHomeCemeteryHistory)
        .filter(
            FuneralHomeCemeteryHistory.company_id == company_id,
            FuneralHomeCemeteryHistory.customer_id == customer_id,
        )
        .order_by(FuneralHomeCemeteryHistory.order_count.desc())
        .limit(limit)
        .all()
    )

    if len(records) < _MIN_HISTORY_RECORDS:
        return []

    result = []
    for rec in records:
        cemetery = (
            db.query(Cemetery)
            .filter(Cemetery.id == rec.cemetery_id)
            .first()
        )
        if cemetery and cemetery.is_active:
            result.append(
                {
                    "cemetery_id": rec.cemetery_id,
                    "cemetery_name": cemetery.name,
                    "order_count": rec.order_count,
                    "last_order_date": rec.last_order_date.isoformat()
                    if rec.last_order_date
                    else None,
                }
            )
    return result


# ---------------------------------------------------------------------------
# History upsert (called when a funeral order is saved)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Geographic Shortlist (cold-start)
# ---------------------------------------------------------------------------


def get_geographic_shortlist(
    db: Session,
    company_id: str,
    customer_id: str,
    limit: int = 5,
) -> list[dict]:
    """Return cemeteries geographically near a funeral home's address.

    Used when the funeral home has < MIN_HISTORY_RECORDS in their usage history.
    Falls back to county/state match when cemetery lat/lng not available.
    Returns empty list if history threshold is already met.
    """
    # Check if history threshold already met
    history_count = (
        db.query(func.count(FuneralHomeCemeteryHistory.id))
        .filter(
            FuneralHomeCemeteryHistory.company_id == company_id,
            FuneralHomeCemeteryHistory.customer_id == customer_id,
        )
        .scalar()
        or 0
    )
    if history_count >= _MIN_HISTORY_RECORDS:
        return []

    # Load funeral home address for geographic matching
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        return []

    # Load active cemeteries
    cemeteries = (
        db.query(Cemetery)
        .filter(Cemetery.company_id == company_id, Cemetery.is_active.is_(True))
        .order_by(Cemetery.name)
        .all()
    )

    results = []
    for c in cemeteries:
        # State-based match as primary filter
        if c.state and customer.state:
            if c.state.upper() == (customer.state or "").upper():
                results.append({
                    "cemetery_id": c.id,
                    "cemetery_name": c.name,
                    "distance_miles": None,
                    "county": c.county,
                    "state": c.state,
                    "city": c.city,
                })
        elif c.state is None and customer.state is None:
            results.append({
                "cemetery_id": c.id,
                "cemetery_name": c.name,
                "distance_miles": None,
                "county": c.county,
                "state": c.state,
                "city": c.city,
            })

    # Deduplicate and limit
    seen: set[str] = set()
    unique = []
    for r in results:
        if r["cemetery_id"] not in seen:
            seen.add(r["cemetery_id"])
            unique.append(r)

    return unique[:limit]


# ---------------------------------------------------------------------------
# Cemetery Order History
# ---------------------------------------------------------------------------


def get_cemetery_order_history(
    db: Session,
    company_id: str,
    cemetery_id: str,
    limit: int = 10,
) -> list[dict]:
    """Return recent sales orders for a cemetery (by cemetery_id FK)."""
    from app.models.sales_order import SalesOrder

    # Verify cemetery belongs to company
    get_cemetery(db, cemetery_id, company_id)

    orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.cemetery_id == cemetery_id,
        )
        .order_by(SalesOrder.order_date.desc())
        .limit(limit)
        .all()
    )

    results = []
    for o in orders:
        customer_name = None
        if o.customer:
            customer_name = o.customer.name
        results.append({
            "order_id": o.id,
            "order_number": o.number,
            "customer_name": customer_name,
            "order_date": o.order_date.isoformat() if o.order_date else None,
            "scheduled_date": o.scheduled_date.isoformat() if o.scheduled_date else None,
            "status": o.status,
            "total": float(o.total),
        })
    return results


def get_cemetery_funeral_homes(
    db: Session,
    company_id: str,
    cemetery_id: str,
) -> list[dict]:
    """Return funeral homes that have used this cemetery, ordered by usage."""
    get_cemetery(db, cemetery_id, company_id)

    history = (
        db.query(FuneralHomeCemeteryHistory)
        .filter(
            FuneralHomeCemeteryHistory.company_id == company_id,
            FuneralHomeCemeteryHistory.cemetery_id == cemetery_id,
        )
        .order_by(FuneralHomeCemeteryHistory.order_count.desc())
        .all()
    )

    results = []
    for h in history:
        customer = (
            db.query(Customer)
            .filter(Customer.id == h.customer_id)
            .first()
        )
        results.append({
            "customer_id": h.customer_id,
            "customer_name": customer.name if customer else "Unknown",
            "order_count": h.order_count,
            "last_order_date": h.last_order_date.isoformat() if h.last_order_date else None,
        })
    return results


def link_billing_customer(
    db: Session,
    company_id: str,
    cemetery_id: str,
    customer_id: str,
) -> dict:
    """Link a billing customer record to an operational cemetery."""
    cemetery = get_cemetery(db, cemetery_id, company_id)
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    cemetery.customer_id = customer_id
    db.commit()
    db.refresh(cemetery)
    return {"cemetery_id": cemetery.id, "customer_id": cemetery.customer_id}


def create_billing_account(
    db: Session,
    company_id: str,
    cemetery_id: str,
    actor_id: str | None = None,
) -> dict:
    """Create a billing customer for this cemetery and link it."""
    import uuid as _uuid
    cemetery = get_cemetery(db, cemetery_id, company_id)

    new_customer = Customer(
        id=str(_uuid.uuid4()),
        company_id=company_id,
        name=cemetery.name,
        customer_type="cemetery",
        payment_terms="net_30",
        account_status="active",
        address_line1=cemetery.address,
        city=cemetery.city,
        state=cemetery.state,
        zip_code=cemetery.zip_code,
        phone=cemetery.phone,
        contact_name=cemetery.contact_name,
        created_by=actor_id,
    )
    db.add(new_customer)
    db.flush()

    cemetery.customer_id = new_customer.id
    db.commit()
    db.refresh(cemetery)

    return {
        "customer_id": new_customer.id,
        "customer_name": new_customer.name,
        "cemetery_id": cemetery.id,
    }


def record_funeral_home_cemetery_usage(
    db: Session,
    company_id: str,
    customer_id: str,
    cemetery_id: str,
    order_date: date | None = None,
) -> None:
    """
    Upsert a FuneralHomeCemeteryHistory record.
    Increments order_count; updates last_order_date if newer.
    """
    existing = (
        db.query(FuneralHomeCemeteryHistory)
        .filter(
            FuneralHomeCemeteryHistory.company_id == company_id,
            FuneralHomeCemeteryHistory.customer_id == customer_id,
            FuneralHomeCemeteryHistory.cemetery_id == cemetery_id,
        )
        .first()
    )

    effective_date = order_date or date.today()

    if existing:
        existing.order_count += 1
        if not existing.last_order_date or effective_date > existing.last_order_date:
            existing.last_order_date = effective_date
        existing.updated_at = datetime.now(timezone.utc)
    else:
        record = FuneralHomeCemeteryHistory(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=customer_id,
            cemetery_id=cemetery_id,
            order_count=1,
            last_order_date=effective_date,
        )
        db.add(record)

    db.commit()
