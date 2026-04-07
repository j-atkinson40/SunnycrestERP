"""Knowledge Base setup service.

Seeds system categories based on tenant vertical and enabled extensions.
Called during onboarding and when extensions are installed.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.kb_category import KBCategory
from app.models.kb_extension_notification import KBExtensionNotification

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category definitions by vertical
# ---------------------------------------------------------------------------

# Core categories available to all manufacturing tenants
MANUFACTURING_CATEGORIES = [
    {
        "slug": "pricing",
        "name": "Product Pricing",
        "description": "Price lists, rate sheets, and product pricing information",
        "icon": "DollarSign",
        "display_order": 1,
    },
    {
        "slug": "product_specs",
        "name": "Product Specifications",
        "description": "Product dimensions, materials, weight limits, and technical specs",
        "icon": "Package",
        "display_order": 2,
    },
    {
        "slug": "personalization_options",
        "name": "Personalization Options",
        "description": "Vault personalization types, colors, designs, and lead times",
        "icon": "Palette",
        "display_order": 3,
    },
    {
        "slug": "company_policies",
        "name": "Company Policies",
        "description": "Payment terms, delivery policies, cancellation fees, and warranties",
        "icon": "FileText",
        "display_order": 4,
    },
    {
        "slug": "cemetery_policies",
        "name": "Cemetery Requirements",
        "description": "Cemetery-specific equipment requirements, liner types, and contacts",
        "icon": "MapPin",
        "display_order": 5,
    },
    {
        "slug": "delivery_info",
        "name": "Delivery Information",
        "description": "Delivery zones, scheduling windows, equipment requirements",
        "icon": "Truck",
        "display_order": 6,
    },
    {
        "slug": "general",
        "name": "General Knowledge",
        "description": "FAQs, how-to guides, and miscellaneous reference material",
        "icon": "BookOpen",
        "display_order": 99,
    },
]

# Extension-specific categories
EXTENSION_CATEGORIES = {
    "wastewater": [
        {
            "slug": "wastewater_pricing",
            "name": "Wastewater Pricing",
            "description": "Septic tank and wastewater product pricing",
            "icon": "DollarSign",
            "display_order": 10,
        },
        {
            "slug": "wastewater_specs",
            "name": "Wastewater Specifications",
            "description": "Septic tank sizes, capacities, and installation requirements",
            "icon": "Package",
            "display_order": 11,
        },
    ],
    "redi_rock": [
        {
            "slug": "redirock_pricing",
            "name": "Redi-Rock Pricing",
            "description": "Retaining wall block pricing and contractor rates",
            "icon": "DollarSign",
            "display_order": 20,
        },
        {
            "slug": "redirock_specs",
            "name": "Redi-Rock Specifications",
            "description": "Block dimensions, engineering specs, and installation guides",
            "icon": "Package",
            "display_order": 21,
        },
    ],
    "rosetta": [
        {
            "slug": "rosetta_pricing",
            "name": "Rosetta Pricing",
            "description": "Hardscape product pricing",
            "icon": "DollarSign",
            "display_order": 30,
        },
        {
            "slug": "rosetta_specs",
            "name": "Rosetta Specifications",
            "description": "Hardscape product dimensions and installation guides",
            "icon": "Package",
            "display_order": 31,
        },
    ],
}

# Funeral home vertical categories
FUNERAL_HOME_CATEGORIES = [
    {
        "slug": "pricing",
        "name": "Service Pricing",
        "description": "Funeral service packages, casket pricing, and fee schedules",
        "icon": "DollarSign",
        "display_order": 1,
    },
    {
        "slug": "company_policies",
        "name": "Policies & Procedures",
        "description": "Funeral home policies, licensing, and compliance requirements",
        "icon": "FileText",
        "display_order": 2,
    },
    {
        "slug": "general",
        "name": "General Knowledge",
        "description": "FAQs and reference material",
        "icon": "BookOpen",
        "display_order": 99,
    },
]

# Cemetery vertical categories
CEMETERY_CATEGORIES = [
    {
        "slug": "pricing",
        "name": "Lot & Service Pricing",
        "description": "Cemetery lot pricing, interment fees, and perpetual care rates",
        "icon": "DollarSign",
        "display_order": 1,
    },
    {
        "slug": "company_policies",
        "name": "Cemetery Rules & Regulations",
        "description": "Monument requirements, decoration policies, visiting hours",
        "icon": "FileText",
        "display_order": 2,
    },
    {
        "slug": "general",
        "name": "General Knowledge",
        "description": "FAQs and reference material",
        "icon": "BookOpen",
        "display_order": 99,
    },
]

VERTICAL_CATEGORIES = {
    "manufacturing": MANUFACTURING_CATEGORIES,
    "funeral_home": FUNERAL_HOME_CATEGORIES,
    "cemetery": CEMETERY_CATEGORIES,
    "crematory": FUNERAL_HOME_CATEGORIES,  # Reuse funeral home categories
}


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_categories(
    db: Session,
    tenant_id: str,
    vertical: str = "manufacturing",
    enabled_extensions: list[str] | None = None,
) -> int:
    """Seed system KB categories for a tenant.

    Idempotent — skips categories that already exist (matched by slug + tenant_id).

    Returns:
        Number of categories created.
    """
    categories = VERTICAL_CATEGORIES.get(vertical, MANUFACTURING_CATEGORIES)
    created = 0

    for cat_def in categories:
        existing = (
            db.query(KBCategory)
            .filter(
                KBCategory.tenant_id == tenant_id,
                KBCategory.slug == cat_def["slug"],
            )
            .first()
        )
        if existing:
            continue

        cat = KBCategory(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=cat_def["name"],
            slug=cat_def["slug"],
            description=cat_def["description"],
            display_order=cat_def["display_order"],
            is_system=True,
            icon=cat_def.get("icon"),
        )
        db.add(cat)
        created += 1

    # Extension categories
    for ext_slug in (enabled_extensions or []):
        ext_cats = EXTENSION_CATEGORIES.get(ext_slug, [])
        for cat_def in ext_cats:
            existing = (
                db.query(KBCategory)
                .filter(
                    KBCategory.tenant_id == tenant_id,
                    KBCategory.slug == cat_def["slug"],
                )
                .first()
            )
            if existing:
                continue

            cat = KBCategory(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=cat_def["name"],
                slug=cat_def["slug"],
                description=cat_def["description"],
                display_order=cat_def["display_order"],
                is_system=True,
                icon=cat_def.get("icon"),
            )
            db.add(cat)
            created += 1

    if created:
        db.flush()
        logger.info("Seeded %d KB categories for tenant %s (vertical=%s)", created, tenant_id, vertical)

    return created


def seed_extension_categories(
    db: Session,
    tenant_id: str,
    extension_slug: str,
    extension_name: str,
) -> int:
    """Seed KB categories for a newly installed extension and create notification.

    Called when an extension is enabled for a tenant.

    Returns:
        Number of categories created.
    """
    created = seed_categories(db, tenant_id, enabled_extensions=[extension_slug])

    if created > 0:
        # Create notification for morning briefing
        notification = KBExtensionNotification(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            extension_slug=extension_slug,
            extension_name=extension_name,
            briefing_date=datetime.now(timezone.utc).date(),
        )
        db.add(notification)
        db.flush()
        logger.info(
            "Created KB extension notification for %s (tenant %s)",
            extension_slug, tenant_id,
        )

    return created


def get_pending_notifications(db: Session, tenant_id: str) -> list[dict]:
    """Get unacknowledged extension notifications for briefing integration."""
    notifications = (
        db.query(KBExtensionNotification)
        .filter(
            KBExtensionNotification.tenant_id == tenant_id,
            KBExtensionNotification.acknowledged == False,  # noqa: E712
        )
        .order_by(KBExtensionNotification.notified_at.desc())
        .all()
    )

    return [
        {
            "id": n.id,
            "extension_slug": n.extension_slug,
            "extension_name": n.extension_name,
            "notified_at": n.notified_at.isoformat() if n.notified_at else None,
        }
        for n in notifications
    ]


def acknowledge_notification(db: Session, notification_id: str) -> bool:
    """Mark an extension notification as acknowledged."""
    notification = db.query(KBExtensionNotification).filter(
        KBExtensionNotification.id == notification_id
    ).first()
    if not notification:
        return False
    notification.acknowledged = True
    db.flush()
    return True
