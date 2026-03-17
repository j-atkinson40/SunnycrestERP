"""Vault ordering service — cross-tenant ordering from manufacturer catalog."""

import uuid
from datetime import UTC, datetime, date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.fh_vault_order import FHVaultOrder
from app.models.fh_manufacturer_relationship import FHManufacturerRelationship
from app.models.fh_case import FHCase
from app.models.product import Product
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.company import Company
from app.services.case_service import log_activity

# ---------------------------------------------------------------------------
# Manufacturer status -> vault order status mapping
# ---------------------------------------------------------------------------

_MANUFACTURER_STATUS_MAP = {
    "draft": "submitted",
    "confirmed": "confirmed",
    "processing": "in_production",
    "shipped": "scheduled_for_delivery",
    "completed": "delivered",
    "canceled": "cancelled",
}


# ---------------------------------------------------------------------------
# Manufacturer relationships
# ---------------------------------------------------------------------------

def get_manufacturer_relationships(
    db: Session, tenant_id: str
) -> list[FHManufacturerRelationship]:
    """List all manufacturer relationships for this funeral home tenant."""
    return (
        db.query(FHManufacturerRelationship)
        .filter(FHManufacturerRelationship.funeral_home_tenant_id == tenant_id)
        .order_by(FHManufacturerRelationship.is_primary.desc())
        .all()
    )


def create_manufacturer_relationship(
    db: Session, tenant_id: str, data: dict
) -> FHManufacturerRelationship:
    """Link funeral home to a manufacturer tenant. Validates manufacturer exists."""
    manufacturer = (
        db.query(Company)
        .filter(Company.id == data["manufacturer_tenant_id"])
        .first()
    )
    if not manufacturer:
        raise HTTPException(
            status_code=404, detail="Manufacturer tenant not found"
        )

    # Check for existing relationship
    existing = (
        db.query(FHManufacturerRelationship)
        .filter(
            FHManufacturerRelationship.funeral_home_tenant_id == tenant_id,
            FHManufacturerRelationship.manufacturer_tenant_id == data["manufacturer_tenant_id"],
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Relationship with this manufacturer already exists",
        )

    rel = FHManufacturerRelationship(
        id=str(uuid.uuid4()),
        funeral_home_tenant_id=tenant_id,
        manufacturer_tenant_id=data["manufacturer_tenant_id"],
        account_number=data.get("account_number"),
        default_delivery_instructions=data.get("default_delivery_instructions"),
        is_primary=data.get("is_primary", False),
        negotiated_price_tier=data.get("negotiated_price_tier"),
        status=data.get("status", "active"),
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


# ---------------------------------------------------------------------------
# Manufacturer catalog
# ---------------------------------------------------------------------------

def get_manufacturer_catalog(
    db: Session,
    funeral_home_tenant_id: str,
    manufacturer_tenant_id: str,
) -> list[Product]:
    """Fetch vault products from the manufacturer's product catalog.

    Queries Product table WHERE company_id=manufacturer_tenant_id AND is_active=True.
    """
    # Verify relationship exists
    rel = (
        db.query(FHManufacturerRelationship)
        .filter(
            FHManufacturerRelationship.funeral_home_tenant_id == funeral_home_tenant_id,
            FHManufacturerRelationship.manufacturer_tenant_id == manufacturer_tenant_id,
        )
        .first()
    )
    if not rel:
        raise HTTPException(
            status_code=403,
            detail="No relationship established with this manufacturer",
        )

    products = (
        db.query(Product)
        .filter(
            Product.company_id == manufacturer_tenant_id,
            Product.is_active.is_(True),
        )
        .order_by(Product.name)
        .all()
    )
    return products


# ---------------------------------------------------------------------------
# Vault orders
# ---------------------------------------------------------------------------

def _next_vault_order_number(db: Session, company_id: str) -> str:
    """Generate next VO-YYYY-NNNN order number."""
    from sqlalchemy import func as sa_func

    year = datetime.now(UTC).year
    prefix = f"VO-{year}-"
    count = (
        db.query(sa_func.count(FHVaultOrder.id))
        .filter(
            FHVaultOrder.company_id == company_id,
            FHVaultOrder.order_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    return f"{prefix}{(count or 0) + 1:04d}"


def submit_vault_order(
    db: Session,
    tenant_id: str,
    case_id: str,
    data: dict,
    performed_by_id: str,
) -> FHVaultOrder:
    """Create vault order and cross-tenant sales order.

    1. Create FHVaultOrder record with status='submitted'
    2. Create SalesOrder in manufacturer's tenant
    3. Create SalesOrderLine for the vault product
    4. Set manufacturer_order_id on the vault order
    5. Log case activity
    6. Return vault order
    """
    # Verify case exists
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Verify manufacturer relationship
    manufacturer_tenant_id = data["manufacturer_tenant_id"]
    rel = (
        db.query(FHManufacturerRelationship)
        .filter(
            FHManufacturerRelationship.funeral_home_tenant_id == tenant_id,
            FHManufacturerRelationship.manufacturer_tenant_id == manufacturer_tenant_id,
        )
        .first()
    )
    if not rel:
        raise HTTPException(
            status_code=403,
            detail="No relationship with this manufacturer",
        )

    # Create vault order
    vault_order_id = str(uuid.uuid4())
    vault_order = FHVaultOrder(
        id=vault_order_id,
        company_id=tenant_id,
        case_id=case_id,
        manufacturer_tenant_id=manufacturer_tenant_id,
        order_number=_next_vault_order_number(db, tenant_id),
        status="submitted",
        vault_product_id=data.get("vault_product_id"),
        vault_product_name=data.get("vault_product_name"),
        vault_product_sku=data.get("vault_product_sku"),
        quantity=data.get("quantity", 1),
        unit_price=Decimal(str(data.get("unit_price", "0.00"))),
        requested_delivery_date=data.get("requested_delivery_date"),
        delivery_address=data.get("delivery_address", rel.default_delivery_instructions),
        delivery_contact_name=data.get("delivery_contact_name"),
        delivery_contact_phone=data.get("delivery_contact_phone"),
        special_instructions=data.get("special_instructions"),
        notes=data.get("notes"),
    )
    db.add(vault_order)
    db.flush()

    # Create cross-tenant SalesOrder in manufacturer's namespace
    from sqlalchemy import func as sa_func

    year = datetime.now(UTC).year
    so_prefix = f"SO-{year}-"
    so_count = (
        db.query(sa_func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == manufacturer_tenant_id,
            SalesOrder.number.like(f"{so_prefix}%"),
        )
        .scalar()
    )
    so_number = f"{so_prefix}{(so_count or 0) + 1:04d}"

    # Get funeral home company name for ship_to
    fh_company = db.query(Company).filter(Company.id == tenant_id).first()

    so_id = str(uuid.uuid4())
    sales_order = SalesOrder(
        id=so_id,
        company_id=manufacturer_tenant_id,
        number=so_number,
        customer_id=tenant_id,  # funeral home is the customer
        status="confirmed",
        order_date=datetime.now(UTC),
        required_date=data.get("requested_delivery_date"),
        ship_to_name=fh_company.name if fh_company else None,
        ship_to_address=data.get("delivery_address"),
        subtotal=vault_order.unit_price * vault_order.quantity,
        tax_amount=Decimal("0.00"),
        total=vault_order.unit_price * vault_order.quantity,
        notes=f"Funeral home portal order: {vault_order.order_number}",
        created_by=performed_by_id,
    )
    db.add(sales_order)
    db.flush()

    # Create sales order line
    sol = SalesOrderLine(
        id=str(uuid.uuid4()),
        sales_order_id=so_id,
        product_id=data.get("vault_product_id"),
        description=data.get("vault_product_name", "Vault"),
        quantity=vault_order.quantity,
        unit_price=vault_order.unit_price,
        line_total=vault_order.unit_price * vault_order.quantity,
        sort_order=1,
    )
    db.add(sol)

    # Link manufacturer order
    vault_order.manufacturer_order_id = so_id

    # Log activity
    log_activity(
        db,
        tenant_id,
        case_id,
        "vault_ordered",
        f"Vault order {vault_order.order_number} submitted to manufacturer",
        performed_by=performed_by_id,
        metadata={
            "vault_order_id": vault_order_id,
            "manufacturer_tenant_id": manufacturer_tenant_id,
            "product_name": data.get("vault_product_name"),
        },
    )

    db.commit()
    db.refresh(vault_order)
    return vault_order


def get_vault_order(db: Session, tenant_id: str, case_id: str) -> FHVaultOrder | None:
    """Get vault order for a case."""
    return (
        db.query(FHVaultOrder)
        .filter(
            FHVaultOrder.case_id == case_id,
            FHVaultOrder.company_id == tenant_id,
        )
        .first()
    )


def sync_vault_order_status(
    db: Session, tenant_id: str, vault_order_id: str
) -> FHVaultOrder:
    """Pull current status from manufacturer's order record.

    Read the SalesOrder from manufacturer tenant by manufacturer_order_id.
    Map manufacturer order status to vault order status.
    Update fh_vault_orders if changed, log activity if status changed.
    """
    vault_order = (
        db.query(FHVaultOrder)
        .filter(
            FHVaultOrder.id == vault_order_id,
            FHVaultOrder.company_id == tenant_id,
        )
        .first()
    )
    if not vault_order:
        raise HTTPException(status_code=404, detail="Vault order not found")

    if not vault_order.manufacturer_order_id:
        return vault_order

    # Read manufacturer's sales order
    manufacturer_so = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == vault_order.manufacturer_order_id)
        .first()
    )
    if not manufacturer_so:
        return vault_order

    # Map manufacturer status to vault order status
    new_status = _MANUFACTURER_STATUS_MAP.get(manufacturer_so.status)
    if new_status and new_status != vault_order.status:
        old_status = vault_order.status
        vault_order.status = new_status
        vault_order.delivery_status_last_updated_at = datetime.now(UTC)

        log_activity(
            db,
            tenant_id,
            vault_order.case_id,
            "vault_status_updated",
            f"Vault order status changed from {old_status} to {new_status}",
            metadata={
                "vault_order_id": vault_order_id,
                "old_status": old_status,
                "new_status": new_status,
            },
        )

        db.commit()
        db.refresh(vault_order)

    return vault_order


def get_delivery_readiness(db: Session, tenant_id: str, case_id: str) -> dict:
    """Check vault delivery status against service date.

    Returns: {status, warning_level (none/amber/red), message}
    """
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    vault_order = get_vault_order(db, tenant_id, case_id)
    if not vault_order:
        return {
            "status": "no_order",
            "warning_level": "none",
            "message": "No vault order exists for this case",
        }

    if vault_order.status == "delivered":
        return {
            "status": "delivered",
            "warning_level": "none",
            "message": "Vault has been delivered",
        }

    if vault_order.status == "cancelled":
        return {
            "status": "cancelled",
            "warning_level": "red",
            "message": "Vault order has been cancelled",
        }

    if not case.service_date:
        return {
            "status": vault_order.status,
            "warning_level": "none",
            "message": f"Vault status: {vault_order.status}. No service date set.",
        }

    today = date.today()
    service_date = case.service_date if isinstance(case.service_date, date) else case.service_date.date()
    days_until_service = (service_date - today).days

    if days_until_service <= 1:
        return {
            "status": vault_order.status,
            "warning_level": "red",
            "message": f"URGENT: Vault not delivered. Service is {'today' if days_until_service <= 0 else 'tomorrow'}.",
        }
    elif days_until_service <= 3:
        return {
            "status": vault_order.status,
            "warning_level": "amber",
            "message": f"Warning: Vault not delivered. Service in {days_until_service} days.",
        }

    return {
        "status": vault_order.status,
        "warning_level": "none",
        "message": f"Vault status: {vault_order.status}. Service in {days_until_service} days.",
    }


def sync_all_pending_orders(db: Session, tenant_id: str) -> int:
    """Sync status for all non-terminal vault orders. Called by background job.

    Returns count of orders synced.
    """
    terminal_statuses = ("delivered", "cancelled")
    pending_orders = (
        db.query(FHVaultOrder)
        .filter(
            FHVaultOrder.company_id == tenant_id,
            ~FHVaultOrder.status.in_(terminal_statuses),
            FHVaultOrder.manufacturer_order_id.isnot(None),
        )
        .all()
    )

    synced = 0
    for order in pending_orders:
        try:
            sync_vault_order_status(db, tenant_id, order.id)
            synced += 1
        except Exception:
            # Log but don't fail the whole batch
            continue

    return synced
