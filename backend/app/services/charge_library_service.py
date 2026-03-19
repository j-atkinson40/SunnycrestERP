"""Charge Library Service — seed, list, and manage fee/surcharge templates."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.charge_library_item import ChargeLibraryItem

logger = logging.getLogger(__name__)

# ── Default charges seeded for manufacturing tenants ───────────────────────

DEFAULT_CHARGES: list[dict] = [
    # Delivery & Transportation
    {
        "charge_key": "delivery_fee",
        "charge_name": "Delivery Fee",
        "category": "delivery_transportation",
        "description": (
            "Charged on most orders for transporting the vault to the "
            "cemetery or job site."
        ),
        "auto_suggest": True,
        "auto_suggest_trigger": "always",
        "sort_order": 1,
    },
    {
        "charge_key": "mileage_fuel_surcharge",
        "charge_name": "Mileage / Fuel Surcharge",
        "category": "delivery_transportation",
        "description": (
            "An additional charge based on distance, separate from the "
            "base delivery fee."
        ),
        "pricing_type": "per_mile",
        "sort_order": 2,
    },
    {
        "charge_key": "after_hours_delivery",
        "charge_name": "After-Hours / Emergency Delivery",
        "category": "delivery_transportation",
        "description": (
            "Charged when delivery is requested outside normal business hours."
        ),
        "auto_suggest": True,
        "auto_suggest_trigger": "after_hours",
        "sort_order": 3,
    },
    {
        "charge_key": "rush_order_fee",
        "charge_name": "Rush Order Fee",
        "category": "delivery_transportation",
        "description": (
            "Charged when an order needs to be fulfilled faster than "
            "standard lead time."
        ),
        "auto_suggest": True,
        "auto_suggest_trigger": "rush_48h",
        "sort_order": 4,
    },
    {
        "charge_key": "return_trip_fee",
        "charge_name": "Return Trip Fee",
        "category": "delivery_transportation",
        "description": "Charged when a second delivery attempt is required.",
        "sort_order": 5,
    },
    # Services
    {
        "charge_key": "vault_personalization",
        "charge_name": "Vault Personalization / Engraving",
        "category": "services",
        "description": (
            "Charged when a family requests personalization, engraving, "
            "or a legacy print on the vault."
        ),
        "pricing_type": "fixed",
        "sort_order": 6,
    },
    {
        "charge_key": "disinterment_service",
        "charge_name": "Disinterment Service",
        "category": "services",
        "description": (
            "Charged for disinterment services. Amount typically varies "
            "by circumstances."
        ),
        "sort_order": 7,
    },
    {
        "charge_key": "re_interment_service",
        "charge_name": "Re-Interment Service",
        "category": "services",
        "description": "Charged for re-interment after disinterment.",
        "sort_order": 8,
    },
    {
        "charge_key": "liner_installation",
        "charge_name": "Liner Installation",
        "category": "services",
        "description": (
            "Charged when installation service is provided along with "
            "the liner."
        ),
        "sort_order": 9,
    },
    {
        "charge_key": "grave_space_setup",
        "charge_name": "Grave Space Setup",
        "category": "services",
        "description": "Charged for grave space preparation services.",
        "sort_order": 10,
    },
    # Labor
    {
        "charge_key": "overtime_weekend_labor",
        "charge_name": "Overtime / Weekend Labor",
        "category": "labor",
        "description": (
            "Charged when weekend or overtime labor is required for a "
            "delivery or service."
        ),
        "auto_suggest": True,
        "auto_suggest_trigger": "weekend",
        "sort_order": 11,
    },
    {
        "charge_key": "setup_crew",
        "charge_name": "Setup Crew",
        "category": "labor",
        "description": (
            "Charged when a setup crew is dispatched in addition to the driver."
        ),
        "sort_order": 12,
    },
]


def seed_default_charges(db: Session, tenant_id: str) -> list[ChargeLibraryItem]:
    """Create the default charge library items for a new tenant.

    Called during tenant onboarding initialization. Idempotent — skips
    any charge_key that already exists for the tenant.
    """
    existing_keys = {
        row.charge_key
        for row in db.query(ChargeLibraryItem.charge_key)
        .filter(ChargeLibraryItem.tenant_id == tenant_id)
        .all()
    }

    now = datetime.now(timezone.utc)
    created: list[ChargeLibraryItem] = []

    for charge_def in DEFAULT_CHARGES:
        if charge_def["charge_key"] in existing_keys:
            continue

        item = ChargeLibraryItem(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            charge_key=charge_def["charge_key"],
            charge_name=charge_def["charge_name"],
            category=charge_def["category"],
            description=charge_def.get("description"),
            is_enabled=False,
            is_system=True,
            pricing_type=charge_def.get("pricing_type", "variable"),
            auto_suggest=charge_def.get("auto_suggest", False),
            auto_suggest_trigger=charge_def.get("auto_suggest_trigger"),
            sort_order=charge_def.get("sort_order", 0),
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        created.append(item)

    if created:
        db.flush()
        logger.info(
            "Seeded %d default charges for tenant %s", len(created), tenant_id
        )

    return created


def list_charges(db: Session, tenant_id: str) -> list[ChargeLibraryItem]:
    """List all charge library items for a tenant, ordered by sort_order."""
    return (
        db.query(ChargeLibraryItem)
        .filter(ChargeLibraryItem.tenant_id == tenant_id)
        .order_by(ChargeLibraryItem.sort_order)
        .all()
    )


def bulk_save_charges(
    db: Session, tenant_id: str, charges: list[dict]
) -> list[ChargeLibraryItem]:
    """Bulk save/update charge configurations. Single transaction.

    Each item in `charges` must contain `charge_key` plus any fields
    to update (is_enabled, pricing_type, fixed_amount, etc.).
    """
    existing_map: dict[str, ChargeLibraryItem] = {
        item.charge_key: item
        for item in db.query(ChargeLibraryItem)
        .filter(ChargeLibraryItem.tenant_id == tenant_id)
        .all()
    }

    now = datetime.now(timezone.utc)
    updated: list[ChargeLibraryItem] = []

    for charge_data in charges:
        key = charge_data["charge_key"]
        item = existing_map.get(key)
        if not item:
            logger.warning(
                "Charge key %s not found for tenant %s — skipping", key, tenant_id
            )
            continue

        # Update mutable fields
        for field in (
            "is_enabled",
            "pricing_type",
            "fixed_amount",
            "per_mile_rate",
            "free_radius_miles",
            "guidance_min",
            "guidance_max",
            "variable_placeholder",
            "auto_suggest",
            "auto_suggest_trigger",
            "invoice_label",
            "notes",
        ):
            if field in charge_data:
                setattr(item, field, charge_data[field])

        # zone_config stored as JSON text
        if "zone_config" in charge_data:
            val = charge_data["zone_config"]
            item.zone_config = json.dumps(val) if val is not None else None

        item.updated_at = now
        updated.append(item)

    db.flush()
    return updated


def create_custom_charge(
    db: Session, tenant_id: str, **kwargs
) -> ChargeLibraryItem:
    """Create a custom charge library item."""
    # Generate a charge_key from the name
    name = kwargs.get("charge_name", "custom")
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    # Ensure uniqueness by appending short uuid if collision
    existing = (
        db.query(ChargeLibraryItem)
        .filter(
            ChargeLibraryItem.tenant_id == tenant_id,
            ChargeLibraryItem.charge_key == key,
        )
        .first()
    )
    if existing:
        key = f"{key}_{uuid.uuid4().hex[:6]}"

    # Determine next sort_order
    max_sort = (
        db.query(ChargeLibraryItem.sort_order)
        .filter(ChargeLibraryItem.tenant_id == tenant_id)
        .order_by(ChargeLibraryItem.sort_order.desc())
        .first()
    )
    next_sort = (max_sort[0] + 1) if max_sort else 1

    now = datetime.now(timezone.utc)
    item = ChargeLibraryItem(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        charge_key=key,
        charge_name=kwargs["charge_name"],
        category=kwargs.get("category", "other"),
        description=kwargs.get("description"),
        is_enabled=True,
        is_system=False,
        pricing_type=kwargs.get("pricing_type", "variable"),
        fixed_amount=kwargs.get("fixed_amount"),
        invoice_label=kwargs.get("invoice_label"),
        sort_order=next_sort,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    return item


def get_enabled_charges(db: Session, tenant_id: str) -> list[ChargeLibraryItem]:
    """Get only enabled charges — used by order creation to suggest charges."""
    return (
        db.query(ChargeLibraryItem)
        .filter(
            ChargeLibraryItem.tenant_id == tenant_id,
            ChargeLibraryItem.is_enabled == True,  # noqa: E712
        )
        .order_by(ChargeLibraryItem.sort_order)
        .all()
    )
