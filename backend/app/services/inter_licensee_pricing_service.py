"""Inter-licensee pricing service — price lists, lookups, requests, approvals."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.inter_licensee_pricing import (
    InterLicenseePriceList,
    InterLicenseePriceListItem,
    TransferPriceRequest,
)
from app.models.licensee_transfer import LicenseeTransfer

logger = logging.getLogger(__name__)


def get_area_price_list(db: Session, area_tenant_id: str) -> dict | None:
    """Get area licensee's published inter-licensee price list."""
    pl = (
        db.query(InterLicenseePriceList)
        .filter(
            InterLicenseePriceList.tenant_id == area_tenant_id,
            InterLicenseePriceList.is_active.is_(True),
            InterLicenseePriceList.visible_to_all_licensees.is_(True),
        )
        .first()
    )
    if not pl:
        return None

    result = {
        "id": pl.id,
        "name": pl.name,
        "pricing_method": pl.pricing_method,
        "retail_adjustment_percentage": float(pl.retail_adjustment_percentage) if pl.retail_adjustment_percentage else 0,
        "auto_created": getattr(pl, "auto_created", False),
    }

    # For retail method, items are resolved dynamically — don't need price list items
    if pl.pricing_method in ("retail", "retail_minus", "retail_plus"):
        result["items"] = []
        return result

    items = (
        db.query(InterLicenseePriceListItem)
        .filter(InterLicenseePriceListItem.price_list_id == pl.id, InterLicenseePriceListItem.is_active.is_(True))
        .all()
    )
    result["items"] = [
        {
            "id": i.id,
            "product_name": i.product_name,
            "product_code": i.product_code,
            "unit_price": float(i.unit_price) if i.unit_price else None,
            "unit": i.unit,
            "notes": i.notes,
        }
        for i in items
    ]
    return result


def lookup_transfer_pricing(db: Session, transfer_id: str) -> dict:
    """Look up pricing for a transfer. Tries retail catalog first, then price list items, then sends request."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or not transfer.area_tenant_id:
        return {"found": False, "error": "Transfer not found or no area licensee"}

    price_list_data = get_area_price_list(db, transfer.area_tenant_id)

    # If no price list exists, auto-create one from retail catalog
    if not price_list_data:
        price_list_data = _auto_create_retail_price_list(db, transfer.area_tenant_id)

    if price_list_data:
        pricing_method = price_list_data.get("pricing_method", "fixed")
        adjustment_pct = Decimal(str(price_list_data.get("retail_adjustment_percentage", 0)))

        # For 'retail' or 'retail_minus'/'retail_plus': resolve from product catalog
        if pricing_method in ("retail", "retail_minus", "retail_plus"):
            return _resolve_retail_pricing(db, transfer, pricing_method, adjustment_pct)

        # For 'fixed': match against explicit price list items
        if price_list_data.get("items"):
            return _resolve_fixed_pricing(db, transfer, price_list_data["items"])

    # No price list and no catalog — send price request
    send_price_request(db, transfer_id)
    return {"found": False, "request_sent": True}


def _auto_create_retail_price_list(db: Session, area_tenant_id: str) -> dict | None:
    """Auto-create an inter-licensee price list from the tenant's retail catalog."""
    from app.models.product import Product

    # Check if tenant has products with prices
    product_count = (
        db.query(Product)
        .filter(Product.company_id == area_tenant_id, Product.is_active.is_(True))
        .count()
    )
    if product_count == 0:
        return None

    # Auto-create price list with retail method
    pl = InterLicenseePriceList(
        id=str(uuid.uuid4()),
        tenant_id=area_tenant_id,
        name="Inter-Licensee Transfer Pricing",
        pricing_method="retail",
        is_active=True,
        visible_to_all_licensees=True,
        auto_created=True,
        notes="Automatically created — uses your standard retail pricing. Adjust in Settings → Inter-Licensee Pricing.",
    )
    db.add(pl)
    db.flush()

    logger.info(f"Auto-created retail inter-licensee price list for tenant {area_tenant_id}")

    return {
        "id": pl.id,
        "name": pl.name,
        "pricing_method": "retail",
        "retail_adjustment_percentage": 0,
        "items": [],
    }


def _resolve_retail_pricing(
    db: Session, transfer: LicenseeTransfer, pricing_method: str, adjustment_pct: Decimal,
) -> dict:
    """Resolve transfer pricing from the area licensee's product catalog."""
    from app.models.product import Product

    products = (
        db.query(Product)
        .filter(Product.company_id == transfer.area_tenant_id, Product.is_active.is_(True))
        .all()
    )

    # Build lookup structures
    product_by_code = {p.sku.lower(): p for p in products if getattr(p, "sku", None)}
    product_by_name = {p.name.lower(): p for p in products}

    matched_prices = []
    total = Decimal("0")

    for idx, item in enumerate(transfer.transfer_items or []):
        desc = item.get("description", "").lower()
        code = (item.get("product_code") or "").lower()
        qty = item.get("quantity", 1)
        matched_product = None
        match_score = 0

        # Step 1: exact code match
        if code and code in product_by_code:
            matched_product = product_by_code[code]
            match_score = 1.0

        # Step 2: name similarity
        if not matched_product:
            best_score = 0
            for pname, prod in product_by_name.items():
                if desc in pname or pname in desc:
                    matched_product = prod
                    match_score = 0.9
                    break
                desc_words = set(desc.split())
                p_words = set(pname.split())
                overlap = len(desc_words & p_words) / max(len(desc_words | p_words), 1)
                if overlap > best_score and overlap >= 0.3:
                    matched_product = prod
                    best_score = overlap
                    match_score = overlap

        if matched_product and match_score >= 0.3:
            # Get retail price
            retail_price = getattr(matched_product, "base_price", None) or getattr(matched_product, "price", None) or Decimal("0")
            retail_price = Decimal(str(retail_price))

            # Apply adjustment
            if pricing_method == "retail_minus":
                unit_price = (retail_price * (Decimal("1") - adjustment_pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif pricing_method == "retail_plus":
                unit_price = (retail_price * (Decimal("1") + adjustment_pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                unit_price = retail_price

            line_total = unit_price * Decimal(str(qty))
            matched_prices.append({
                "transfer_item_index": idx,
                "description": item.get("description"),
                "unit_price": float(unit_price),
                "quantity": qty,
                "line_total": float(line_total),
                "price_source": "retail_catalog",
                "product_id": matched_product.id,
                "match_confidence": round(match_score, 2),
            })
            total += line_total
        else:
            matched_prices.append({
                "transfer_item_index": idx,
                "description": item.get("description"),
                "unit_price": None,
                "quantity": qty,
                "line_total": 0,
                "price_source": "not_found",
                "needs_manual_price": True,
                "match_confidence": 0,
            })

    all_priced = all(p["unit_price"] is not None for p in matched_prices)

    transfer.area_unit_prices = matched_prices
    transfer.area_charge_amount = total if all_priced else None
    transfer.pricing_status = "price_found"
    db.commit()

    if all_priced:
        _create_pricing_alert(db, transfer, "price_found", float(total))
    else:
        # Some items unresolved — alert area licensee
        unresolved = [p for p in matched_prices if p["unit_price"] is None]
        _create_alert(
            db, transfer.area_tenant_id,
            "transfer_pricing_incomplete",
            f"Transfer {transfer.transfer_number} needs manual pricing",
            f"{len(unresolved)} item(s) not found in your catalog. Complete pricing for this transfer.",
            "Complete Pricing",
            f"/transfers/{transfer.id}/submit-pricing",
        )

    return {"found": all_priced, "prices": matched_prices, "total": float(total), "pricing_method": "retail"}


def _resolve_fixed_pricing(db: Session, transfer: LicenseeTransfer, price_list_items: list[dict]) -> dict:
    """Resolve transfer pricing from explicit fixed price list items."""
    matched_prices = []
    total = Decimal("0")

    for idx, item in enumerate(transfer.transfer_items or []):
        desc = item.get("description", "").lower()
        qty = item.get("quantity", 1)
        best_match = None
        best_score = 0

        for pl_item in price_list_items:
            pl_name = pl_item["product_name"].lower()
            if desc in pl_name or pl_name in desc:
                best_match = pl_item
                best_score = 0.9
                break
            desc_words = set(desc.split())
            pl_words = set(pl_name.split())
            overlap = len(desc_words & pl_words) / max(len(desc_words | pl_words), 1)
            if overlap > best_score:
                best_match = pl_item
                best_score = overlap

        if best_match and best_match["unit_price"] and best_score >= 0.3:
            line_total = Decimal(str(best_match["unit_price"])) * Decimal(str(qty))
            matched_prices.append({
                "transfer_item_index": idx,
                "description": item.get("description"),
                "unit_price": best_match["unit_price"],
                "quantity": qty,
                "line_total": float(line_total),
                "price_source": "catalog",
                "price_list_item_id": best_match["id"],
                "match_confidence": round(best_score, 2),
            })
            total += line_total
        else:
            matched_prices.append({
                "transfer_item_index": idx,
                "description": item.get("description"),
                "unit_price": None,
                "quantity": qty,
                "line_total": 0,
                "price_source": "not_found",
                "price_list_item_id": None,
                "match_confidence": 0,
            })

    all_priced = all(p["unit_price"] is not None for p in matched_prices)

    transfer.area_unit_prices = matched_prices
    transfer.area_charge_amount = total if all_priced else None
    transfer.pricing_status = "price_found" if all_priced else "price_requested"
    db.commit()

    if all_priced:
        _create_pricing_alert(db, transfer, "price_found", float(total))

    return {"found": all_priced, "prices": matched_prices, "total": float(total), "pricing_method": "fixed"}


def send_price_request(db: Session, transfer_id: str) -> TransferPriceRequest | None:
    """Send a price request to the area licensee."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or not transfer.area_tenant_id:
        return None

    request = TransferPriceRequest(
        id=str(uuid.uuid4()),
        transfer_id=transfer_id,
        requesting_tenant_id=transfer.home_tenant_id,
        area_tenant_id=transfer.area_tenant_id,
        status="pending",
        items_requested=transfer.transfer_items or [],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(request)

    transfer.pricing_status = "price_requested"

    # Alert area licensee
    _create_alert(
        db, transfer.area_tenant_id,
        "transfer_price_request",
        f"Price request for transfer {transfer.transfer_number}",
        f"Pricing needed for {len(transfer.transfer_items or [])} items at {transfer.cemetery_name}, {transfer.cemetery_state}. Respond within 24 hours.",
        "Submit Pricing",
        f"/transfers/{transfer.id}/submit-pricing",
    )

    db.commit()
    db.refresh(request)
    return request


def respond_to_price_request(
    db: Session, transfer_id: str, response_items: list[dict], response_notes: str | None, area_user_id: str,
) -> dict:
    """Area licensee responds to a price request."""
    request = (
        db.query(TransferPriceRequest)
        .filter(TransferPriceRequest.transfer_id == transfer_id, TransferPriceRequest.status == "pending")
        .first()
    )
    if not request:
        return {"error": "No pending price request found"}

    request.status = "responded"
    request.responded_at = datetime.now(timezone.utc)
    request.responded_by = area_user_id
    request.response_items = response_items
    request.response_notes = response_notes

    # Update transfer
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if transfer:
        total = sum(Decimal(str(i.get("unit_price", 0))) * Decimal(str(i.get("quantity", 1))) for i in response_items)
        formatted = [
            {
                "transfer_item_index": idx,
                "description": i.get("description"),
                "unit_price": i.get("unit_price"),
                "quantity": i.get("quantity", 1),
                "line_total": float(Decimal(str(i.get("unit_price", 0))) * Decimal(str(i.get("quantity", 1)))),
                "price_source": "requested",
            }
            for idx, i in enumerate(response_items)
        ]
        transfer.area_unit_prices = formatted
        transfer.area_charge_amount = total
        transfer.area_pricing_notes = response_notes
        transfer.pricing_status = "price_received"

        _create_pricing_alert(db, transfer, "price_received", float(total))

    db.commit()
    return {"status": "responded", "total": float(total)}


def review_and_approve_pricing(
    db: Session, transfer_id: str, markup_percentage: float, review_notes: str | None, home_user_id: str,
) -> dict:
    """Home licensee reviews and approves transfer pricing."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or not transfer.area_charge_amount:
        return {"error": "Transfer not found or no charge amount"}

    markup = Decimal(str(markup_percentage))
    charge = transfer.area_charge_amount
    passthrough = (charge * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    transfer.markup_percentage = markup
    transfer.passthrough_amount = passthrough
    transfer.price_reviewed_by = home_user_id
    transfer.price_reviewed_at = datetime.now(timezone.utc)
    transfer.price_review_notes = review_notes
    transfer.pricing_status = "approved"
    transfer.fh_price_visible = False
    db.commit()

    return {
        "area_charge": float(charge),
        "markup_percentage": float(markup),
        "passthrough_amount": float(passthrough),
        "margin": float(passthrough - charge),
    }


def make_price_visible_to_fh(db: Session, transfer_id: str, home_user_id: str) -> dict:
    """Make transfer price visible to the funeral home."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer:
        return {"error": "Transfer not found"}

    transfer.fh_price_visible = True
    transfer.fh_price_visible_at = datetime.now(timezone.utc)
    transfer.pricing_status = "shown_to_fh"
    db.commit()

    return {"visible": True, "passthrough_amount": float(transfer.passthrough_amount) if transfer.passthrough_amount else 0}


# ── Price list CRUD ──


def get_own_price_list(db: Session, tenant_id: str) -> dict | None:
    """Get tenant's own price list for settings page."""
    pl = db.query(InterLicenseePriceList).filter(InterLicenseePriceList.tenant_id == tenant_id).first()
    if not pl:
        return None
    items = db.query(InterLicenseePriceListItem).filter(InterLicenseePriceListItem.price_list_id == pl.id).order_by(InterLicenseePriceListItem.product_name).all()
    return {
        "id": pl.id,
        "name": pl.name,
        "is_active": pl.is_active,
        "visible_to_all_licensees": pl.visible_to_all_licensees,
        "pricing_method": pl.pricing_method,
        "retail_adjustment_percentage": float(pl.retail_adjustment_percentage) if pl.retail_adjustment_percentage else 0,
        "notes": pl.notes,
        "items": [
            {
                "id": i.id,
                "product_name": i.product_name,
                "product_code": i.product_code,
                "unit_price": float(i.unit_price) if i.unit_price else None,
                "unit": i.unit,
                "is_active": i.is_active,
                "notes": i.notes,
            }
            for i in items
        ],
    }


def create_or_update_price_list(db: Session, tenant_id: str, data: dict, user_id: str) -> dict:
    """Create or update inter-licensee price list settings."""
    pl = db.query(InterLicenseePriceList).filter(InterLicenseePriceList.tenant_id == tenant_id).first()
    if not pl:
        pl = InterLicenseePriceList(id=str(uuid.uuid4()), tenant_id=tenant_id, created_by=user_id)
        db.add(pl)

    for key in ("name", "is_active", "visible_to_all_licensees", "pricing_method", "notes"):
        if key in data:
            setattr(pl, key, data[key])
    if "retail_adjustment_percentage" in data:
        pl.retail_adjustment_percentage = Decimal(str(data["retail_adjustment_percentage"]))

    db.commit()
    db.refresh(pl)
    return {"id": pl.id}


def add_price_list_item(db: Session, tenant_id: str, price_list_id: str, data: dict) -> dict:
    """Add item to inter-licensee price list."""
    item = InterLicenseePriceListItem(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        price_list_id=price_list_id,
        product_name=data["product_name"],
        product_code=data.get("product_code"),
        unit_price=Decimal(str(data["unit_price"])) if data.get("unit_price") else None,
        unit=data.get("unit", "each"),
        notes=data.get("notes"),
    )
    db.add(item)
    db.commit()
    return {"id": item.id}


def update_price_list_item(db: Session, item_id: str, tenant_id: str, data: dict) -> bool:
    """Update a price list item."""
    item = (
        db.query(InterLicenseePriceListItem)
        .filter(InterLicenseePriceListItem.id == item_id, InterLicenseePriceListItem.tenant_id == tenant_id)
        .first()
    )
    if not item:
        return False
    for key in ("product_name", "product_code", "unit", "is_active", "notes"):
        if key in data:
            setattr(item, key, data[key])
    if "unit_price" in data:
        item.unit_price = Decimal(str(data["unit_price"])) if data["unit_price"] else None
    db.commit()
    return True


def delete_price_list_item(db: Session, item_id: str, tenant_id: str) -> bool:
    """Delete a price list item."""
    item = (
        db.query(InterLicenseePriceListItem)
        .filter(InterLicenseePriceListItem.id == item_id, InterLicenseePriceListItem.tenant_id == tenant_id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


# ── Helpers ──


def _create_pricing_alert(db: Session, transfer: LicenseeTransfer, alert_type: str, total: float) -> None:
    _create_alert(
        db, transfer.home_tenant_id,
        f"transfer_{alert_type}",
        f"Transfer {transfer.transfer_number} pricing ready",
        f"Area licensee pricing: ${total:,.2f}. Review and set your passthrough price.",
        "Review Pricing",
        f"/transfers/{transfer.id}/pricing",
    )


def _create_alert(db: Session, tenant_id: str, alert_type: str, title: str, message: str, action_label: str, action_url: str) -> None:
    try:
        from app.models.agent import AgentAlert
        alert = AgentAlert(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            alert_type=alert_type,
            severity="action_required",
            title=title,
            message=message,
            action_label=action_label,
            action_url=action_url,
        )
        db.add(alert)
    except Exception as e:
        logger.warning(f"Could not create pricing alert: {e}")
