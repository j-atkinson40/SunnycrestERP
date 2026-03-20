"""Functional area service — extension-aware loading and seeding.

Functional areas define what business functions an employee has access to.
Areas with a required_extension are only shown when that extension is active.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.functional_area_definition import FunctionalAreaDefinition
from app.services import extension_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data for manufacturing preset
# ---------------------------------------------------------------------------

MANUFACTURING_AREAS = [
    {
        "area_key": "funeral_scheduling",
        "display_name": "Funeral Scheduling",
        "description": "View and manage funeral service schedules, delivery assignments, and daily calendar",
        "icon": "Calendar",
        "required_extension": None,
        "sort_order": 10,
    },
    {
        "area_key": "production_log",
        "display_name": "Production",
        "description": "Daily production entry, vault manufacturing logs, and output tracking",
        "icon": "Factory",
        "required_extension": None,
        "sort_order": 20,
    },
    {
        "area_key": "invoicing_ar",
        "display_name": "Invoicing & AR",
        "description": "Create invoices, manage accounts receivable, and track payments",
        "icon": "Receipt",
        "required_extension": None,
        "sort_order": 30,
    },
    {
        "area_key": "customer_management",
        "display_name": "Customer Management",
        "description": "Manage funeral home accounts, contacts, pricing, and customer relationships",
        "icon": "Users",
        "required_extension": None,
        "sort_order": 40,
    },
    {
        "area_key": "safety_compliance",
        "display_name": "Safety & Compliance",
        "description": "Safety incident reporting, OSHA compliance, NPCA audit preparation",
        "icon": "ShieldCheck",
        "required_extension": None,
        "sort_order": 50,
    },
    {
        "area_key": "reporting",
        "display_name": "Reporting",
        "description": "Dashboards, KPIs, management reports, and data exports",
        "icon": "BarChart3",
        "required_extension": None,
        "sort_order": 60,
    },
    {
        "area_key": "precast_scheduling",
        "display_name": "Precast & Product Scheduling",
        "description": "Schedule and manage production for precast products, Redi-Rock, wastewater, and Rosetta lines",
        "icon": "Blocks",
        "required_extension": "any_product_extension",
        "sort_order": 70,
    },
    {
        "area_key": "full_admin",
        "display_name": "Full Admin",
        "description": "Complete system access — settings, user management, billing, and all modules",
        "icon": "Shield",
        "required_extension": None,
        "sort_order": 100,
    },
]

PRODUCT_EXTENSION_KEYS = ["wastewater_treatment", "redi_rock", "rosetta_hardscapes"]

PRODUCT_EXTENSION_NAMES = {
    "wastewater_treatment": "Wastewater Scheduling",
    "redi_rock": "Redi-Rock Scheduling",
    "rosetta_hardscapes": "Rosetta Scheduling",
}


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed_functional_areas(db: Session) -> None:
    """Seed manufacturing functional area definitions. Idempotent."""
    try:
        existing_keys = {
            r[0]
            for r in db.query(FunctionalAreaDefinition.area_key)
            .filter(FunctionalAreaDefinition.preset == "manufacturing")
            .all()
        }

        now = datetime.now(timezone.utc)
        added = 0

        for area in MANUFACTURING_AREAS:
            if area["area_key"] not in existing_keys:
                db.add(
                    FunctionalAreaDefinition(
                        id=str(uuid.uuid4()),
                        preset="manufacturing",
                        area_key=area["area_key"],
                        display_name=area["display_name"],
                        description=area["description"],
                        icon=area["icon"],
                        required_extension=area["required_extension"],
                        sort_order=area["sort_order"],
                        is_active=True,
                        created_at=now,
                    )
                )
                added += 1

        if added > 0:
            db.commit()
            logger.info("Seeded %d functional area definitions", added)
        else:
            logger.info("Functional area definitions already up to date")

    except Exception as e:
        logger.warning("Failed to seed functional areas: %s", e)
        db.rollback()


# ---------------------------------------------------------------------------
# Extension-aware loading
# ---------------------------------------------------------------------------


def get_areas_for_tenant(db: Session, tenant_id: str) -> list[dict]:
    """Return functional areas available for this tenant, filtered by active extensions.

    Areas with required_extension=None are always included.
    Areas with required_extension='any_product_extension' require at least one
    product line extension to be active.
    Other values are checked directly against active extension keys.

    The precast_scheduling area gets a dynamic display_name based on which
    product extensions are active.
    """
    all_areas = (
        db.query(FunctionalAreaDefinition)
        .filter(
            FunctionalAreaDefinition.preset == "manufacturing",
            FunctionalAreaDefinition.is_active.is_(True),
        )
        .order_by(FunctionalAreaDefinition.sort_order)
        .all()
    )

    active_ext_keys = extension_service.get_active_extension_keys(db, tenant_id)
    active_product_exts = [k for k in PRODUCT_EXTENSION_KEYS if k in active_ext_keys]
    has_any_product = len(active_product_exts) > 0

    result = []
    for area in all_areas:
        # Filter by required_extension
        if area.required_extension is None:
            pass  # always included
        elif area.required_extension == "any_product_extension":
            if not has_any_product:
                continue
        elif area.required_extension not in active_ext_keys:
            continue

        row = {
            "id": area.id,
            "area_key": area.area_key,
            "display_name": area.display_name,
            "description": area.description,
            "icon": area.icon,
            "required_extension": area.required_extension,
            "sort_order": area.sort_order,
        }

        # Dynamic display name for precast_scheduling
        if area.area_key == "precast_scheduling" and has_any_product:
            if len(active_product_exts) == 1:
                row["display_name"] = PRODUCT_EXTENSION_NAMES.get(
                    active_product_exts[0], area.display_name
                )
            # else: keep "Precast & Product Scheduling" for multiple

        result.append(row)

    return result


def get_active_areas_for_employee(
    employee_areas: list[str] | None,
    tenant_areas: list[dict],
) -> list[str]:
    """Filter an employee's functional_areas to only those available for the tenant.

    Areas that belong to disabled extensions are filtered out at read time.
    The employee's stored list is never modified — re-enabling an extension
    restores access automatically.
    """
    if not employee_areas:
        return []
    available_keys = {a["area_key"] for a in tenant_areas}
    return [k for k in employee_areas if k in available_keys]


def check_new_area_on_extension_install(
    db: Session,
    tenant_id: str,
    extension_key: str,
) -> dict | None:
    """Check if installing this extension activates a new functional area.

    Returns area info if the precast_scheduling area becomes newly available
    (the tenant had NO product extensions before this install).
    Returns None if no new area was activated.
    """
    if extension_key not in PRODUCT_EXTENSION_KEYS:
        return None

    # Check if tenant already had other product extensions BEFORE this one
    active_ext_keys = extension_service.get_active_extension_keys(db, tenant_id)
    other_product_exts = [
        k for k in PRODUCT_EXTENSION_KEYS
        if k in active_ext_keys and k != extension_key
    ]

    if other_product_exts:
        # Already had product extensions — precast_scheduling was already visible
        return None

    # This is the first product extension — precast_scheduling is newly available
    display_name = PRODUCT_EXTENSION_NAMES.get(extension_key, "Precast & Product Scheduling")
    return {
        "area_key": "precast_scheduling",
        "display_name": display_name,
        "extension_key": extension_key,
    }
