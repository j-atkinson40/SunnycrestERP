"""Price increase service — calculate, preview, apply, and activate price versions.

Handles:
- Percentage / flat / manual increases across products
- Rounding modes (none, nearest_dollar, nearest_quarter, nearest_five)
- Cascade updates to product_price_tiers and kb_pricing_entries
- Version lifecycle: draft → scheduled → active → archived
- Midnight activation of scheduled versions
"""

import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.kb_pricing_entry import KBPricingEntry
from app.models.price_list_item import PriceListItem
from app.models.price_list_version import PriceListVersion
from app.models.price_update_settings import PriceUpdateSettings
from app.models.product import Product
from app.models.product_price_tier import ProductPriceTier
from app.services import notification_service

# ── Rounding ──────────────────────────────────────────────────────────────

ROUNDING_MODES = {
    "none": lambda v: v,
    "nearest_dollar": lambda v: v.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
    "nearest_quarter": lambda v: (v * 4).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 4,
    "nearest_five": lambda v: (v / 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 5,
}


def _round_price(price: Decimal, mode: str) -> Decimal:
    fn = ROUNDING_MODES.get(mode, ROUNDING_MODES["none"])
    rounded = fn(price)
    return rounded.quantize(Decimal("0.01"))


# ── Settings ──────────────────────────────────────────────────────────────

def get_or_create_settings(db: Session, tenant_id: str) -> PriceUpdateSettings:
    settings = db.query(PriceUpdateSettings).filter(
        PriceUpdateSettings.tenant_id == tenant_id
    ).first()
    if not settings:
        settings = PriceUpdateSettings(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, tenant_id: str, data: dict) -> PriceUpdateSettings:
    settings = get_or_create_settings(db, tenant_id)
    for key in ("rounding_mode", "accept_manufacturer_updates"):
        if key in data:
            setattr(settings, key, data[key])
    db.commit()
    db.refresh(settings)
    return settings


# ── Version management ────────────────────────────────────────────────────

def get_versions(db: Session, tenant_id: str) -> list[PriceListVersion]:
    return (
        db.query(PriceListVersion)
        .filter(PriceListVersion.tenant_id == tenant_id)
        .order_by(PriceListVersion.version_number.desc())
        .all()
    )


def get_version(db: Session, tenant_id: str, version_id: str) -> PriceListVersion | None:
    return (
        db.query(PriceListVersion)
        .filter(
            PriceListVersion.tenant_id == tenant_id,
            PriceListVersion.id == version_id,
        )
        .first()
    )


def get_active_version(db: Session, tenant_id: str) -> PriceListVersion | None:
    return (
        db.query(PriceListVersion)
        .filter(
            PriceListVersion.tenant_id == tenant_id,
            PriceListVersion.status == "active",
        )
        .first()
    )


def _next_version_number(db: Session, tenant_id: str) -> int:
    max_num = db.query(func.max(PriceListVersion.version_number)).filter(
        PriceListVersion.tenant_id == tenant_id
    ).scalar()
    return (max_num or 0) + 1


# ── Calculate preview ─────────────────────────────────────────────────────

def calculate_price_increase(
    db: Session,
    tenant_id: str,
    increase_type: str,          # "percentage" | "flat" | "manual"
    increase_value: Decimal | None,  # percentage or flat amount
    effective_date: date,
    product_ids: list[str] | None = None,
    category_id: str | None = None,
    manual_prices: dict | None = None,  # {product_id: {"standard": "12.50", ...}}
    label: str | None = None,
    notes: str | None = None,
) -> dict:
    """Preview price changes without saving. Returns proposed items."""
    settings = get_or_create_settings(db, tenant_id)
    rounding = settings.rounding_mode

    # Query products
    q = db.query(Product).filter(
        Product.company_id == tenant_id,
        Product.is_active == True,  # noqa: E712
    )
    if product_ids:
        q = q.filter(Product.id.in_(product_ids))
    if category_id:
        q = q.filter(Product.category_id == category_id)
    products = q.order_by(Product.name).all()

    items = []
    for p in products:
        old_price = p.price or Decimal("0.00")

        if increase_type == "manual" and manual_prices and p.id in manual_prices:
            mp = manual_prices[p.id]
            new_price = Decimal(str(mp.get("standard", old_price)))
        elif increase_type == "percentage" and increase_value:
            new_price = old_price * (1 + increase_value / 100)
        elif increase_type == "flat" and increase_value:
            new_price = old_price + increase_value
        else:
            new_price = old_price

        new_price = _round_price(new_price, rounding)
        change = new_price - old_price
        pct_change = ((change / old_price) * 100) if old_price else Decimal("0")

        items.append({
            "product_id": p.id,
            "product_name": p.name,
            "product_code": p.sku,
            "category": p.category.name if p.category_id and hasattr(p, "category") and p.category else None,
            "current_price": str(old_price),
            "new_price": str(new_price),
            "change": str(change),
            "pct_change": str(pct_change.quantize(Decimal("0.01"))),
            "unit": p.unit_of_measure or "each",
        })

    return {
        "item_count": len(items),
        "items": items,
        "rounding_mode": rounding,
        "increase_type": increase_type,
        "increase_value": str(increase_value) if increase_value else None,
        "effective_date": effective_date.isoformat(),
    }


# ── Apply (create version) ───────────────────────────────────────────────

def apply_price_increase(
    db: Session,
    tenant_id: str,
    user_id: str,
    increase_type: str,
    increase_value: Decimal | None,
    effective_date: date,
    product_ids: list[str] | None = None,
    category_id: str | None = None,
    manual_prices: dict | None = None,
    label: str | None = None,
    notes: str | None = None,
) -> PriceListVersion:
    """Create a draft version with new prices. Does NOT update products yet."""
    preview = calculate_price_increase(
        db, tenant_id, increase_type, increase_value, effective_date,
        product_ids, category_id, manual_prices, label, notes,
    )

    version = PriceListVersion(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        version_number=_next_version_number(db, tenant_id),
        label=label or f"Price Update — {effective_date.isoformat()}",
        notes=notes,
        status="draft",
        effective_date=effective_date,
        created_by_user_id=user_id,
    )
    db.add(version)

    for idx, item in enumerate(preview["items"]):
        pli = PriceListItem(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            version_id=version.id,
            product_name=item["product_name"],
            product_code=item["product_code"],
            category=item["category"],
            unit=item["unit"],
            standard_price=Decimal(item["new_price"]),
            previous_standard_price=Decimal(item["current_price"]),
            display_order=idx,
        )
        db.add(pli)

    db.commit()
    db.refresh(version)
    return version


# ── Schedule / Activate ──────────────────────────────────────────────────

def schedule_version(db: Session, tenant_id: str, version_id: str) -> PriceListVersion:
    """Move version from draft → scheduled."""
    version = get_version(db, tenant_id, version_id)
    if not version or version.status != "draft":
        raise ValueError("Only draft versions can be scheduled")
    version.status = "scheduled"
    db.commit()
    db.refresh(version)
    return version


def activate_version(
    db: Session, tenant_id: str, version_id: str, user_id: str | None = None
) -> PriceListVersion:
    """Activate a version: archive current active, update product prices, cascade to KB."""
    version = get_version(db, tenant_id, version_id)
    if not version or version.status not in ("draft", "scheduled"):
        raise ValueError("Only draft or scheduled versions can be activated")

    # Archive current active version
    current = get_active_version(db, tenant_id)
    if current:
        current.status = "archived"

    # Update product prices from version items
    items = (
        db.query(PriceListItem)
        .filter(PriceListItem.version_id == version_id)
        .all()
    )

    updated_count = 0
    for item in items:
        # Match product by code or name
        product = None
        if item.product_code:
            product = db.query(Product).filter(
                Product.company_id == tenant_id,
                Product.sku == item.product_code,
            ).first()
        if not product:
            product = db.query(Product).filter(
                Product.company_id == tenant_id,
                Product.name == item.product_name,
            ).first()

        if product and item.standard_price is not None:
            product.price = item.standard_price
            updated_count += 1

            # Cascade to KB pricing entries
            kb_entries = db.query(KBPricingEntry).filter(
                KBPricingEntry.tenant_id == tenant_id,
                KBPricingEntry.product_name == product.name,
            ).all()
            for kb in kb_entries:
                kb.standard_price = item.standard_price
                if item.contractor_price is not None:
                    kb.contractor_price = item.contractor_price
                if item.homeowner_price is not None:
                    kb.homeowner_price = item.homeowner_price

    # Mark version active
    version.status = "active"
    version.activated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)

    # Notify admins
    try:
        notification_service.create_notification(
            db, tenant_id,
            user_id=user_id or version.created_by_user_id or "",
            title="Price List Activated",
            message=f"Version {version.version_number} ({version.label}) is now active. {updated_count} products updated.",
            type="success",
            category="pricing",
            link="/price-management",
        )
    except Exception:
        pass  # Don't fail activation over notification errors

    return version


# ── Midnight activation job ──────────────────────────────────────────────

def activate_scheduled_versions(db: Session) -> int:
    """Called by scheduler — activate all versions whose effective_date is today."""
    today = date.today()
    versions = (
        db.query(PriceListVersion)
        .filter(
            PriceListVersion.status == "scheduled",
            PriceListVersion.effective_date <= today,
        )
        .all()
    )
    count = 0
    for v in versions:
        try:
            activate_version(db, v.tenant_id, v.id)
            count += 1
        except Exception:
            continue
    return count


# ── Version items ────────────────────────────────────────────────────────

def get_version_items(db: Session, tenant_id: str, version_id: str) -> list[PriceListItem]:
    return (
        db.query(PriceListItem)
        .filter(
            PriceListItem.tenant_id == tenant_id,
            PriceListItem.version_id == version_id,
        )
        .order_by(PriceListItem.display_order)
        .all()
    )


def delete_version(db: Session, tenant_id: str, version_id: str) -> bool:
    """Delete a draft version and its items."""
    version = get_version(db, tenant_id, version_id)
    if not version or version.status != "draft":
        return False
    db.query(PriceListItem).filter(PriceListItem.version_id == version_id).delete()
    db.delete(version)
    db.commit()
    return True
