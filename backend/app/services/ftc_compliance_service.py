"""FTC Funeral Rule compliance service."""

import uuid
from datetime import UTC, datetime, date

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.models.fh_price_list import FHPriceListItem, FHPriceListVersion

# ---------------------------------------------------------------------------
# FTC Required Items
# ---------------------------------------------------------------------------

FTC_REQUIRED_ITEMS = [
    {
        "item_code": "FTC-001",
        "item_name": "Basic Services of Funeral Director and Staff",
        "category": "professional_services",
        "ftc_disclosure_text": (
            "This fee for our basic services will be added to the total cost of the "
            "funeral arrangements you select. This fee is already included in our "
            "charges for direct cremations, immediate burials, and forwarding or "
            "receiving remains."
        ),
        "is_required_by_law": True,
    },
    {
        "item_code": "FTC-002",
        "item_name": "Embalming",
        "category": "professional_services",
        "ftc_disclosure_text": (
            "Except in certain special cases, embalming is not required by law. "
            "Embalming may be necessary, however, if you select certain funeral "
            "arrangements, such as a funeral with viewing. If you do not want "
            "embalming, you usually have the right to choose an arrangement that "
            "does not require you to pay for it, such as direct cremation or "
            "immediate burial."
        ),
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-003",
        "item_name": "Other Preparation of the Body",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-004",
        "item_name": "Transfer of Remains to Funeral Home",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-005",
        "item_name": "Use of Facilities and Staff for Viewing",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-006",
        "item_name": "Use of Facilities and Staff for Funeral Ceremony",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-007",
        "item_name": "Use of Equipment and Staff for Graveside Service",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-008",
        "item_name": "Hearse",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-009",
        "item_name": "Limousine/Service Vehicle",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-010",
        "item_name": "Immediate Burial",
        "category": "packages",
        "ftc_disclosure_text": (
            "This charge includes transfer of remains to the funeral home, basic "
            "services of the funeral director and staff, and local transportation "
            "to the cemetery or crematory."
        ),
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-011",
        "item_name": "Direct Cremation",
        "category": "packages",
        "ftc_disclosure_text": (
            "If you want to arrange a direct cremation, you can use an alternative "
            "container. Alternative containers encase the body and can be made of "
            "materials like fiberboard or composition materials (with or without an "
            "outside covering). The containers we provide are [describe]."
        ),
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-012",
        "item_name": "Forwarding of Remains to Another Funeral Home",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-013",
        "item_name": "Receiving of Remains from Another Funeral Home",
        "category": "professional_services",
        "ftc_disclosure_text": None,
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-014",
        "item_name": "Caskets",
        "category": "merchandise",
        "ftc_disclosure_text": "A complete price list will be provided at the funeral home.",
        "is_required_by_law": False,
    },
    {
        "item_code": "FTC-015",
        "item_name": "Outer Burial Containers",
        "category": "merchandise",
        "ftc_disclosure_text": (
            "A complete price list will be provided at the funeral home. In most "
            "areas of the country, state or local law does not require that you buy "
            "a container to surround the casket in the grave. However, many "
            "cemeteries require that you have such a container so that the grave "
            "will not sink in."
        ),
        "is_required_by_law": False,
    },
]


# ---------------------------------------------------------------------------
# Seed & GPL management
# ---------------------------------------------------------------------------

def seed_ftc_price_list(db: Session, tenant_id: str) -> int:
    """Seed all FTC-required items into fh_price_list for a new funeral home tenant.

    All items seeded with unit_price=0.00 (forcing tenant to set real prices).
    Returns count of items created.
    """
    from decimal import Decimal

    existing_codes = set(
        r[0]
        for r in db.query(FHPriceListItem.item_code)
        .filter(FHPriceListItem.company_id == tenant_id)
        .all()
    )

    count = 0
    for idx, item in enumerate(FTC_REQUIRED_ITEMS):
        if item["item_code"] in existing_codes:
            continue

        pli = FHPriceListItem(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            item_code=item["item_code"],
            category=item["category"],
            item_name=item["item_name"],
            description=item["item_name"],
            unit_price=Decimal("0.00"),
            price_type="unit",
            is_ftc_required_disclosure=True,
            ftc_disclosure_text=item.get("ftc_disclosure_text"),
            is_required_by_law=item.get("is_required_by_law", False),
            is_active=True,
            effective_date=date.today(),
            sort_order=idx * 10,
        )
        db.add(pli)
        count += 1

    if count:
        db.commit()
    return count


def validate_gpl(db: Session, tenant_id: str) -> dict:
    """Check GPL (General Price List) compliance.

    Returns dict with compliance assessment.
    """
    from decimal import Decimal

    # Get all price list items for this tenant
    items = (
        db.query(FHPriceListItem)
        .filter(FHPriceListItem.company_id == tenant_id, FHPriceListItem.is_active.is_(True))
        .all()
    )
    item_map = {i.item_code: i for i in items}

    required_codes = [ftc["item_code"] for ftc in FTC_REQUIRED_ITEMS]
    present_codes = set(item_map.keys())

    missing_items = [code for code in required_codes if code not in present_codes]
    items_missing_prices = [
        code
        for code in required_codes
        if code in present_codes and item_map[code].unit_price == Decimal("0.00")
    ]
    items_missing_disclosure = [
        code
        for code in required_codes
        if code in present_codes
        and _ftc_needs_disclosure(code)
        and not item_map[code].ftc_disclosure_text
    ]

    # GPL version age
    latest_version = (
        db.query(FHPriceListVersion)
        .filter(FHPriceListVersion.company_id == tenant_id)
        .order_by(FHPriceListVersion.version_number.desc())
        .first()
    )

    gpl_age_days = None
    gpl_overdue = False
    if latest_version and latest_version.created_at:
        gpl_age_days = (datetime.now(UTC) - latest_version.created_at).days
        gpl_overdue = gpl_age_days > 365

    # Calculate compliance score
    total_checks = len(required_codes) * 3  # present + priced + disclosure
    passed_checks = 0
    for code in required_codes:
        if code in present_codes:
            passed_checks += 1
            if item_map[code].unit_price != Decimal("0.00"):
                passed_checks += 1
            if not _ftc_needs_disclosure(code) or item_map[code].ftc_disclosure_text:
                passed_checks += 1

    compliance_score = round((passed_checks / total_checks) * 100) if total_checks > 0 else 0

    # Human-readable issues
    issues = []
    if missing_items:
        issues.append(f"{len(missing_items)} FTC-required items missing from price list")
    if items_missing_prices:
        issues.append(f"{len(items_missing_prices)} items have $0.00 price (must be set)")
    if items_missing_disclosure:
        issues.append(f"{len(items_missing_disclosure)} items missing required FTC disclosure text")
    if gpl_overdue:
        issues.append(f"GPL is {gpl_age_days} days old (review recommended annually)")
    if not latest_version:
        issues.append("No GPL version has been created yet")

    return {
        "all_required_items_present": len(missing_items) == 0,
        "missing_items": missing_items,
        "items_missing_prices": items_missing_prices,
        "items_missing_disclosure": items_missing_disclosure,
        "gpl_age_days": gpl_age_days,
        "gpl_overdue": gpl_overdue,
        "compliance_score": compliance_score,
        "issues": issues,
    }


def _ftc_needs_disclosure(item_code: str) -> bool:
    """Check if this FTC item code requires disclosure text."""
    for item in FTC_REQUIRED_ITEMS:
        if item["item_code"] == item_code:
            return item.get("ftc_disclosure_text") is not None
    return False


def get_compliance_dashboard(db: Session, tenant_id: str) -> dict:
    """Full compliance dashboard data."""
    from app.models.fh_case import FHCase

    gpl_data = validate_gpl(db, tenant_id)

    total_cases = (
        db.query(sa_func.count(FHCase.id))
        .filter(FHCase.company_id == tenant_id)
        .scalar()
    ) or 0

    versions = get_gpl_versions(db, tenant_id)

    last_review_date = None
    if versions:
        last_review_date = versions[0].created_at if hasattr(versions[0], "created_at") else None

    gpl_data.update({
        "total_cases": total_cases,
        "last_review_date": last_review_date,
        "gpl_versions": versions,
    })
    return gpl_data


def create_gpl_version(
    db: Session,
    tenant_id: str,
    notes: str,
    created_by_id: str,
    pdf_url: str | None = None,
) -> FHPriceListVersion:
    """Create a new GPL version record. Auto-increments version_number per tenant."""
    max_version = (
        db.query(sa_func.max(FHPriceListVersion.version_number))
        .filter(FHPriceListVersion.company_id == tenant_id)
        .scalar()
    ) or 0

    version = FHPriceListVersion(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        version_number=max_version + 1,
        effective_date=date.today(),
        notes=notes,
        created_by=created_by_id,
        pdf_url=pdf_url,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


# ---------------------------------------------------------------------------
# Price list CRUD
# ---------------------------------------------------------------------------

def get_price_list(
    db: Session,
    tenant_id: str,
    category: str | None = None,
    active_only: bool = True,
) -> list[FHPriceListItem]:
    """List all price list items, optionally filtered by category."""
    query = db.query(FHPriceListItem).filter(FHPriceListItem.company_id == tenant_id)

    if active_only:
        query = query.filter(FHPriceListItem.is_active.is_(True))
    if category:
        query = query.filter(FHPriceListItem.category == category)

    return query.order_by(FHPriceListItem.sort_order, FHPriceListItem.item_name).all()


def create_price_list_item(db: Session, tenant_id: str, data: dict) -> FHPriceListItem:
    """Add item to price list."""
    from decimal import Decimal

    item = FHPriceListItem(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        item_code=data["item_code"],
        category=data.get("category", "other"),
        item_name=data["item_name"],
        description=data.get("description"),
        unit_price=Decimal(str(data.get("unit_price", "0.00"))),
        price_type=data.get("price_type", "unit"),
        is_ftc_required_disclosure=data.get("is_ftc_required_disclosure", False),
        ftc_disclosure_text=data.get("ftc_disclosure_text"),
        is_required_by_law=data.get("is_required_by_law", False),
        is_active=data.get("is_active", True),
        effective_date=data.get("effective_date", date.today()),
        sort_order=data.get("sort_order", 100),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_price_list_item(
    db: Session, tenant_id: str, item_id: str, data: dict
) -> FHPriceListItem:
    """Update price list item. Flags if price changed for GPL version review."""
    from decimal import Decimal

    item = (
        db.query(FHPriceListItem)
        .filter(FHPriceListItem.id == item_id, FHPriceListItem.company_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Price list item not found")

    old_price = item.unit_price
    price_changed = False

    updatable_fields = (
        "item_code", "category", "item_name", "description", "unit_price",
        "price_type", "is_ftc_required_disclosure", "ftc_disclosure_text",
        "is_required_by_law", "is_active", "effective_date", "sort_order",
    )
    for key in updatable_fields:
        if key in data:
            if key == "unit_price":
                new_price = Decimal(str(data[key]))
                if new_price != old_price:
                    price_changed = True
                setattr(item, key, new_price)
            else:
                setattr(item, key, data[key])

    db.commit()
    db.refresh(item)

    # Return item with price_changed flag for caller to decide on GPL version
    item._price_changed = price_changed  # type: ignore[attr-defined]
    return item


def get_gpl_versions(db: Session, tenant_id: str) -> list[FHPriceListVersion]:
    """List all GPL versions ordered by version_number desc."""
    return (
        db.query(FHPriceListVersion)
        .filter(FHPriceListVersion.company_id == tenant_id)
        .order_by(FHPriceListVersion.version_number.desc())
        .all()
    )
