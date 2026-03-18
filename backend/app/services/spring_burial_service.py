"""Spring Burial management service."""

import logging
from datetime import date, datetime, timezone
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.sales_order import SalesOrder
from app.models.customer import Customer

logger = logging.getLogger(__name__)


def list_spring_burials(
    db: Session,
    tenant_id: str,
    *,
    group_by: str = "funeral_home",
    funeral_home_id: str | None = None,
) -> list[dict]:
    """Get all spring burial orders, grouped by funeral home or cemetery."""
    query = (
        db.query(SalesOrder, Customer)
        .join(Customer, SalesOrder.customer_id == Customer.id)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.is_spring_burial.is_(True),
            SalesOrder.status == "spring_burial",
        )
    )
    if funeral_home_id:
        query = query.filter(SalesOrder.customer_id == funeral_home_id)

    results = query.order_by(Customer.name, SalesOrder.created_at).all()

    groups: dict[str, dict] = {}
    for order, customer in results:
        if group_by == "cemetery":
            key = order.ship_to_name or "Unknown Cemetery"
            name = key
        else:
            key = customer.id
            name = customer.name

        if key not in groups:
            groups[key] = {
                "group_key": key,
                "group_name": name,
                "order_count": 0,
                "earliest_opening": customer.typical_opening_date,
                "orders": [],
            }

        days = _days_until_opening(customer.typical_opening_date)
        groups[key]["orders"].append({
            "id": order.id,
            "order_number": order.number,
            "deceased_name": order.ship_to_name,
            "funeral_home_id": customer.id,
            "funeral_home_name": customer.name,
            "cemetery_name": order.ship_to_address,
            "vault_product": order.notes,  # simplified — real impl uses line items
            "spring_burial_added_at": order.spring_burial_added_at,
            "spring_burial_notes": order.spring_burial_notes,
            "typical_opening_date": customer.typical_opening_date,
            "days_until_opening": days,
        })
        groups[key]["order_count"] += 1

        # Track earliest opening
        if customer.typical_opening_date:
            existing = groups[key].get("earliest_opening")
            if not existing or customer.typical_opening_date < existing:
                groups[key]["earliest_opening"] = customer.typical_opening_date

    return list(groups.values())


def get_stats(db: Session, tenant_id: str) -> dict:
    """Get spring burial summary stats."""
    orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.is_spring_burial.is_(True),
            SalesOrder.status == "spring_burial",
        )
        .all()
    )

    total = len(orders)
    funeral_homes = set(o.customer_id for o in orders)

    # Find soonest opening cemetery
    soonest = None
    soonest_date = None
    soonest_days = None

    if orders:
        customers = {
            c.id: c
            for c in db.query(Customer)
            .filter(Customer.id.in_([o.customer_id for o in orders]))
            .all()
        }
        for o in orders:
            cust = customers.get(o.customer_id)
            if cust and cust.typical_opening_date:
                days = _days_until_opening(cust.typical_opening_date)
                if days is not None and (soonest_days is None or days < soonest_days):
                    soonest = cust.name
                    soonest_date = cust.typical_opening_date
                    soonest_days = days

    return {
        "total_count": total,
        "funeral_home_count": len(funeral_homes),
        "soonest_cemetery": soonest,
        "soonest_opening_date": soonest_date,
        "days_until_soonest": soonest_days,
    }


def mark_as_spring_burial(
    db: Session,
    tenant_id: str,
    order_id: str,
    user_id: str,
    notes: str | None = None,
) -> dict:
    """Mark an order as spring burial."""
    order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == order_id, SalesOrder.company_id == tenant_id)
        .first()
    )
    if not order:
        raise ValueError("Order not found")

    order.is_spring_burial = True
    order.status = "spring_burial"
    order.spring_burial_added_at = datetime.now(timezone.utc)
    order.spring_burial_added_by = user_id
    order.spring_burial_notes = notes
    db.commit()
    db.refresh(order)
    return {"id": order.id, "number": order.number, "status": order.status}


def schedule_spring_burial(
    db: Session,
    tenant_id: str,
    order_id: str,
    user_id: str,
    delivery_date: date,
    time_preference: str | None = None,
    driver_id: str | None = None,
    instructions: str | None = None,
) -> dict:
    """Schedule a spring burial for delivery."""
    order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == order_id, SalesOrder.company_id == tenant_id)
        .first()
    )
    if not order:
        raise ValueError("Order not found")
    if not order.is_spring_burial:
        raise ValueError("Order is not a spring burial")

    order.status = "confirmed"
    order.required_date = datetime.combine(delivery_date, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    order.spring_burial_scheduled_at = datetime.now(timezone.utc)
    order.spring_burial_scheduled_by = user_id

    db.commit()
    db.refresh(order)
    return {"id": order.id, "number": order.number, "status": order.status}


def bulk_schedule(
    db: Session,
    tenant_id: str,
    user_id: str,
    items: list[dict],
) -> list[dict]:
    """Schedule multiple spring burials."""
    results = []
    for item in items:
        try:
            result = schedule_spring_burial(
                db, tenant_id, item["order_id"], user_id,
                delivery_date=item["delivery_date"],
                time_preference=item.get("time_preference"),
                driver_id=item.get("driver_id"),
                instructions=item.get("instructions"),
            )
            results.append(result)
        except Exception as e:
            results.append({"order_id": item["order_id"], "error": str(e)})
    return results


def remove_spring_burial(
    db: Session,
    tenant_id: str,
    order_id: str,
    user_id: str,
) -> dict:
    """Remove spring burial status — back to confirmed."""
    order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == order_id, SalesOrder.company_id == tenant_id)
        .first()
    )
    if not order:
        raise ValueError("Order not found")

    order.is_spring_burial = False
    order.status = "confirmed"
    db.commit()
    db.refresh(order)
    return {"id": order.id, "number": order.number, "status": order.status}


def get_report(db: Session, tenant_id: str, year: int | None = None) -> dict:
    """Spring burial summary report."""
    target_year = year or date.today().year
    query = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.is_spring_burial.is_(True),
        )
    )
    orders = query.all()

    # Filter by year
    year_orders = [
        o for o in orders
        if o.spring_burial_added_at
        and o.spring_burial_added_at.year == target_year
    ]

    # Average days held
    days_held = []
    for o in year_orders:
        if o.spring_burial_added_at and o.spring_burial_scheduled_at:
            delta = o.spring_burial_scheduled_at - o.spring_burial_added_at
            days_held.append(delta.days)
    avg_days = sum(days_held) / len(days_held) if days_held else None

    # By funeral home
    fh_counts: dict[str, int] = defaultdict(int)
    for o in year_orders:
        cust = db.query(Customer).filter(Customer.id == o.customer_id).first()
        if cust:
            fh_counts[cust.name] += 1

    return {
        "year": target_year,
        "total_orders": len(year_orders),
        "avg_days_held": round(avg_days, 1) if avg_days else None,
        "by_funeral_home": [
            {"name": k, "count": v}
            for k, v in sorted(fh_counts.items(), key=lambda x: -x[1])
        ],
        "by_cemetery": [],  # TODO: implement when cemetery tracking is richer
    }


def _days_until_opening(opening_date_str: str | None) -> int | None:
    """Calculate days until a MM-DD opening date."""
    if not opening_date_str:
        return None
    try:
        month, day = opening_date_str.split("-")
        today = date.today()
        opening = date(today.year, int(month), int(day))
        if opening < today:
            opening = date(today.year + 1, int(month), int(day))
        return (opening - today).days
    except (ValueError, TypeError):
        return None
