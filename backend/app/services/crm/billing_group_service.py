"""Billing Group Service — manage multi-location funeral home billing groups."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.sales_order import SalesOrder

logger = logging.getLogger(__name__)


def create_group(
    db: Session,
    tenant_id: str,
    group_name: str,
    billing_preference: str,
    location_company_entity_ids: list[str],
    billing_contact_customer_id: str | None = None,
) -> CompanyEntity:
    """Create a billing group and link locations to it."""
    group = CompanyEntity(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        name=group_name,
        is_billing_group=True,
        is_customer=True,
        is_funeral_home=True,
        customer_type="funeral_home",
        billing_preference=billing_preference,
    )
    db.add(group)
    db.flush()

    first_customer_id = None

    for ce_id in location_company_entity_ids:
        location = db.query(CompanyEntity).filter(
            CompanyEntity.id == ce_id,
            CompanyEntity.company_id == tenant_id,
        ).first()
        if not location:
            continue

        location.parent_company_id = group.id

        if billing_preference != "separate":
            customer = db.query(Customer).filter(
                Customer.master_company_id == ce_id,
                Customer.company_id == tenant_id,
            ).first()
            if customer:
                if first_customer_id is None:
                    first_customer_id = customer.id
                customer.billing_group_customer_id = (
                    billing_contact_customer_id or first_customer_id
                )

    db.commit()
    db.refresh(group)
    return group


def get_groups(db: Session, tenant_id: str) -> list[dict]:
    """List all billing groups for a tenant with summary stats."""
    groups = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.is_billing_group == True,
            CompanyEntity.is_active == True,
        )
        .order_by(CompanyEntity.name)
        .all()
    )

    result = []
    for g in groups:
        summary = get_group_summary(db, tenant_id, g.id)
        result.append(summary)
    return result


def get_group_summary(db: Session, tenant_id: str, group_id: str) -> dict:
    """Get detailed summary of a billing group with location stats."""
    group = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.id == group_id,
            CompanyEntity.company_id == tenant_id,
        )
        .first()
    )
    if not group:
        return {}

    locations_ce = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.parent_company_id == group_id,
            CompanyEntity.company_id == tenant_id,
        )
        .order_by(CompanyEntity.name)
        .all()
    )

    zero = Decimal("0.00")
    total_ar = zero
    total_revenue = zero
    total_orders = 0
    location_details = []

    now = datetime.now(timezone.utc)
    twelve_months_ago = now.replace(year=now.year - 1)

    for loc in locations_ce:
        customer = db.query(Customer).filter(
            Customer.master_company_id == loc.id,
            Customer.company_id == tenant_id,
        ).first()

        loc_ar = zero
        loc_revenue = zero
        loc_order_count = 0
        last_order_date = None

        if customer:
            # Open AR balance
            ar_result = (
                db.query(func.sum(Invoice.total - Invoice.amount_paid))
                .filter(
                    Invoice.customer_id == customer.id,
                    Invoice.company_id == tenant_id,
                    Invoice.status.in_(["sent", "partial", "overdue"]),
                )
                .scalar()
            )
            loc_ar = ar_result or zero

            # 12-month orders
            order_stats = (
                db.query(
                    func.count(SalesOrder.id),
                    func.sum(SalesOrder.total),
                    func.max(SalesOrder.created_at),
                )
                .filter(
                    SalesOrder.customer_id == customer.id,
                    SalesOrder.company_id == tenant_id,
                    SalesOrder.created_at >= twelve_months_ago,
                )
                .first()
            )
            if order_stats:
                loc_order_count = order_stats[0] or 0
                loc_revenue = order_stats[1] or zero
                last_order_date = order_stats[2]

        total_ar += loc_ar
        total_revenue += loc_revenue
        total_orders += loc_order_count

        location_details.append({
            "company_entity_id": loc.id,
            "name": loc.name,
            "customer_id": customer.id if customer else None,
            "customer_name": customer.name if customer else loc.name,
            "open_ar_balance": float(loc_ar),
            "last_order_date": last_order_date.isoformat() if last_order_date else None,
            "order_count_12mo": loc_order_count,
            "revenue_12mo": float(loc_revenue),
        })

    return {
        "id": group.id,
        "name": group.name,
        "billing_preference": group.billing_preference,
        "is_billing_group": True,
        "location_count": len(location_details),
        "locations": location_details,
        "totals": {
            "open_ar_balance": float(total_ar),
            "order_count_12mo": total_orders,
            "revenue_12mo": float(total_revenue),
        },
    }


def get_group_for_customer(db: Session, customer_id: str) -> dict | None:
    """Get the billing group a customer belongs to, if any."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer or not customer.master_company_id:
        return None

    location_ce = db.query(CompanyEntity).filter(
        CompanyEntity.id == customer.master_company_id
    ).first()
    if not location_ce or not location_ce.parent_company_id:
        return None

    group = db.query(CompanyEntity).filter(
        CompanyEntity.id == location_ce.parent_company_id
    ).first()
    if not group:
        return None

    return {
        "group_id": group.id,
        "group_name": group.name,
        "billing_preference": group.billing_preference,
    }


def add_location(
    db: Session,
    tenant_id: str,
    group_id: str,
    location_company_entity_id: str,
) -> bool:
    """Add a location to an existing billing group."""
    group = db.query(CompanyEntity).filter(
        CompanyEntity.id == group_id,
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_billing_group == True,
    ).first()
    if not group:
        return False

    location = db.query(CompanyEntity).filter(
        CompanyEntity.id == location_company_entity_id,
        CompanyEntity.company_id == tenant_id,
    ).first()
    if not location:
        return False

    location.parent_company_id = group.id

    if group.billing_preference != "separate":
        customer = db.query(Customer).filter(
            Customer.master_company_id == location_company_entity_id,
            Customer.company_id == tenant_id,
        ).first()
        if customer:
            # Find existing billing contact from group
            existing_billing_customer = (
                db.query(Customer)
                .filter(
                    Customer.billing_group_customer_id.isnot(None),
                    Customer.company_id == tenant_id,
                )
                .join(CompanyEntity, Customer.master_company_id == CompanyEntity.id)
                .filter(CompanyEntity.parent_company_id == group.id)
                .first()
            )
            if existing_billing_customer:
                customer.billing_group_customer_id = existing_billing_customer.billing_group_customer_id
            else:
                customer.billing_group_customer_id = customer.id

    db.commit()
    return True


def unlink_location(db: Session, tenant_id: str, location_company_entity_id: str) -> bool:
    """Remove a location from its billing group."""
    location = db.query(CompanyEntity).filter(
        CompanyEntity.id == location_company_entity_id,
        CompanyEntity.company_id == tenant_id,
    ).first()
    if not location or not location.parent_company_id:
        return False

    location.parent_company_id = None

    customer = db.query(Customer).filter(
        Customer.master_company_id == location_company_entity_id,
        Customer.company_id == tenant_id,
    ).first()
    if customer:
        customer.billing_group_customer_id = None

    db.commit()
    return True


def update_group(
    db: Session,
    tenant_id: str,
    group_id: str,
    name: str | None = None,
    billing_preference: str | None = None,
) -> CompanyEntity | None:
    """Update a billing group's name or billing preference."""
    group = db.query(CompanyEntity).filter(
        CompanyEntity.id == group_id,
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_billing_group == True,
    ).first()
    if not group:
        return None

    if name is not None:
        group.name = name

    if billing_preference is not None and billing_preference != group.billing_preference:
        group.billing_preference = billing_preference
        _update_customer_billing_links(db, tenant_id, group)

    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, tenant_id: str, group_id: str) -> bool:
    """Delete a billing group. All locations revert to independent billing."""
    group = db.query(CompanyEntity).filter(
        CompanyEntity.id == group_id,
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_billing_group == True,
    ).first()
    if not group:
        return False

    locations = db.query(CompanyEntity).filter(
        CompanyEntity.parent_company_id == group_id,
        CompanyEntity.company_id == tenant_id,
    ).all()

    for loc in locations:
        loc.parent_company_id = None
        customer = db.query(Customer).filter(
            Customer.master_company_id == loc.id,
            Customer.company_id == tenant_id,
        ).first()
        if customer:
            customer.billing_group_customer_id = None

    group.is_active = False
    db.commit()
    return True


def _update_customer_billing_links(db: Session, tenant_id: str, group: CompanyEntity):
    """Update customer billing links when billing preference changes."""
    locations = db.query(CompanyEntity).filter(
        CompanyEntity.parent_company_id == group.id,
        CompanyEntity.company_id == tenant_id,
    ).all()

    first_customer_id = None

    for loc in locations:
        customer = db.query(Customer).filter(
            Customer.master_company_id == loc.id,
            Customer.company_id == tenant_id,
        ).first()
        if not customer:
            continue

        if group.billing_preference == "separate":
            customer.billing_group_customer_id = None
        else:
            if first_customer_id is None:
                first_customer_id = customer.id
            customer.billing_group_customer_id = first_customer_id
