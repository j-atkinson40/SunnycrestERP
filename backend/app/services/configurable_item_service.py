"""Configurable Item Service — manages platform-wide registry and per-tenant config.

NEW: no existing equivalent. Handles compliance items, checklists, and other
configurable items that have a master registry with per-tenant overrides.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ConfigurableItemRegistry, TenantItemConfig

logger = logging.getLogger(__name__)


MANUFACTURING_COMPLIANCE_ITEMS = [
    {
        "item_key": "compliance.cdl_renewal",
        "display_name": "CDL Renewal Tracking",
        "tier": 2,
        "tags": ["cdl", "driver", "dot"],
        "description": "Track CDL expiration dates for all drivers",
        "default_config": {
            "warn_days_before": [60, 30, 14, 7],
            "auto_create_per_employee": True,
        },
    },
    {
        "item_key": "compliance.dot_registration",
        "display_name": "DOT Vehicle Registration",
        "tier": 2,
        "tags": ["dot", "vehicle", "annual"],
        "description": "Annual DOT vehicle registration renewal tracking",
        "default_config": {"frequency": "annual"},
    },
    {
        "item_key": "compliance.hut_filing",
        "display_name": "Highway Use Tax (HUT) Filing",
        "tier": 2,
        "tags": ["hut", "tax", "ny", "vehicle"],
        "description": "Required for overweight vehicles in NY",
        "default_config": {"frequency": "annual", "state": "NY"},
    },
    {
        "item_key": "compliance.osha_300_log",
        "display_name": "OSHA 300 Injury Log",
        "tier": 2,
        "tags": ["osha", "safety", "annual"],
        "description": "Annual OSHA 300 injury and illness log",
        "default_config": {"frequency": "annual"},
    },
    {
        "item_key": "compliance.npca_certification",
        "display_name": "NPCA Plant Certification",
        "tier": 2,
        "tags": ["npca", "quality", "precast"],
        "description": "Annual NPCA precast plant certification renewal",
        "default_config": {"frequency": "annual"},
    },
    {
        "item_key": "compliance.epa_stormwater",
        "display_name": "EPA Stormwater Permit",
        "tier": 3,
        "tags": ["epa", "environmental"],
        "description": "EPA stormwater discharge permit compliance",
        "default_config": {},
    },
    {
        "item_key": "compliance.forklift_cert",
        "display_name": "Forklift Operator Certification",
        "tier": 3,
        "tags": ["forklift", "safety", "osha"],
        "description": "OSHA forklift operator certification every 3 years",
        "default_config": {
            "frequency": "every_3_years",
            "auto_create_per_employee": True,
        },
    },
    {
        "item_key": "compliance.drug_testing",
        "display_name": "DOT Drug Testing Program",
        "tier": 3,
        "tags": ["dot", "drug", "cdl"],
        "description": "DOT drug and alcohol testing program for CDL drivers",
        "default_config": {},
    },
    {
        "item_key": "compliance.ifta_filing",
        "display_name": "IFTA Fuel Tax Filing",
        "tier": 3,
        "tags": ["ifta", "tax", "vehicle"],
        "description": "International Fuel Tax Agreement quarterly filing",
        "default_config": {"frequency": "quarterly"},
    },
    {
        "item_key": "compliance.forklift_inspection",
        "display_name": "Daily Forklift Inspection Log",
        "tier": 3,
        "tags": ["forklift", "safety"],
        "description": "Daily pre-shift forklift inspection documentation",
        "default_config": {"frequency": "daily"},
    },
    {
        "item_key": "compliance.fire_extinguisher",
        "display_name": "Fire Extinguisher Inspection",
        "tier": 3,
        "tags": ["fire", "safety"],
        "description": "Annual fire extinguisher inspection and maintenance",
        "default_config": {"frequency": "annual"},
    },
    {
        "item_key": "compliance.confined_space",
        "display_name": "Confined Space Entry Permit",
        "tier": 3,
        "tags": ["confined_space", "safety", "osha"],
        "description": "Confined space entry permit program per OSHA 1910.146",
        "default_config": {},
    },
]


VAULT_PERSONALIZATION_OPTIONS = [
    {
        "item_key": "personalization.standard_colors",
        "display_name": "Standard Wilbert Color Palette",
        "description": "Classic, Heritage, Bronze, Midnight Blue, and all standard Wilbert colors.",
        "tier": 1,
        "tags": ["vault", "color", "standard"],
        "default_config": {"applicable": "all", "price_configurable": False},
    },
    {
        "item_key": "personalization.emblems_nameplates",
        "display_name": "Emblems and Nameplates",
        "description": "Religious, military, sports, occupation, cultural, and custom emblems.",
        "tier": 2,
        "tags": ["vault", "casket", "monument", "emblem"],
        "default_config": {"applicable": "all", "price_configurable": True},
    },
    {
        "item_key": "personalization.legacy_photo",
        "display_name": "Legacy Family Photo Design",
        "description": "Family photo printed on vault top lid panel. Requires family-supplied digital photo.",
        "tier": 2,
        "tags": ["vault", "photo", "custom"],
        "default_config": {"applicable": "all", "price_configurable": True},
    },
    {
        "item_key": "personalization.custom_paint",
        "display_name": "Custom Paint Colors",
        "description": "Custom color matching via RAL or Pantone. Not all licensees offer this.",
        "tier": 3,
        "tags": ["vault", "paint", "custom"],
        "default_config": {"applicable": [], "price_configurable": True},
    },
    {
        "item_key": "personalization.specialty_finish",
        "display_name": "Specialty Finish",
        "description": "Bronze coating or high-polish finish. Available on select products.",
        "tier": 3,
        "tags": ["vault", "finish", "premium"],
        "default_config": {"applicable": [], "price_configurable": True},
    },
]


class ConfigurableItemService:
    """Manages platform-wide configurable item registry and per-tenant config."""

    @staticmethod
    def get_master_list(
        db: Session,
        registry_type: str,
        vertical: str,
        tags: list[str] | None = None,
    ) -> list[ConfigurableItemRegistry]:
        """Return the full master list of items, optionally filtered by tags.

        Args:
            db: Database session.
            registry_type: The type of registry (e.g. 'compliance').
            vertical: The vertical to filter by (e.g. 'manufacturing').
            tags: Optional list of tags to filter by (items matching ANY tag are included).
        """
        query = db.query(ConfigurableItemRegistry).filter(
            ConfigurableItemRegistry.registry_type == registry_type,
            ConfigurableItemRegistry.vertical == vertical,
            ConfigurableItemRegistry.is_active == True,  # noqa: E712
        )

        if tags:
            # JSONB array containment: match items that have any of the given tags
            from sqlalchemy import cast, String as SAString
            from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

            # Use OR logic: item matches if its tags array contains any of the filter tags
            from sqlalchemy import or_

            tag_filters = []
            for tag in tags:
                tag_filters.append(
                    ConfigurableItemRegistry.tags.op("@>")(f'["{tag}"]')
                )
            if tag_filters:
                query = query.filter(or_(*tag_filters))

        return query.order_by(ConfigurableItemRegistry.sort_order).all()

    @staticmethod
    def get_tenant_config(
        db: Session, company_id: str, registry_type: str
    ) -> list[TenantItemConfig]:
        """Return the tenant's current configuration for a registry type."""
        return (
            db.query(TenantItemConfig)
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.registry_type == registry_type,
            )
            .order_by(TenantItemConfig.sort_order)
            .all()
        )

    @staticmethod
    def enable_item(
        db: Session,
        company_id: str,
        item_key: str,
        registry_type: str,
        config: dict | None = None,
    ) -> TenantItemConfig:
        """Enable an item for a tenant. Idempotent — reactivates if disabled.

        Looks up the registry item for display_name and default_config fallback.
        """
        # Check for existing config
        existing = (
            db.query(TenantItemConfig)
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.item_key == item_key,
                TenantItemConfig.registry_type == registry_type,
            )
            .first()
        )

        if existing:
            existing.is_enabled = True
            if config is not None:
                existing.config = config
            existing.updated_at = datetime.now(timezone.utc)
            db.flush()
            return existing

        # Look up registry item for defaults
        registry_item = (
            db.query(ConfigurableItemRegistry)
            .filter(
                ConfigurableItemRegistry.item_key == item_key,
                ConfigurableItemRegistry.registry_type == registry_type,
            )
            .first()
        )

        tenant_config = TenantItemConfig(
            id=str(uuid.uuid4()),
            company_id=company_id,
            registry_id=registry_item.id if registry_item else None,
            item_key=item_key,
            registry_type=registry_type,
            is_enabled=True,
            is_custom=False,
            display_name=registry_item.display_name if registry_item else item_key,
            config=config or (registry_item.default_config if registry_item else {}),
            sort_order=registry_item.sort_order if registry_item else 0,
        )
        db.add(tenant_config)
        db.flush()
        logger.info(
            "Enabled item %s for company=%s registry_type=%s",
            item_key,
            company_id,
            registry_type,
        )
        return tenant_config

    @staticmethod
    def disable_item(
        db: Session, company_id: str, item_key: str, registry_type: str
    ) -> bool:
        """Disable an item for a tenant. Returns True if found and disabled."""
        existing = (
            db.query(TenantItemConfig)
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.item_key == item_key,
                TenantItemConfig.registry_type == registry_type,
            )
            .first()
        )
        if not existing:
            return False

        existing.is_enabled = False
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Disabled item %s for company=%s",
            item_key,
            company_id,
        )
        return True

    @staticmethod
    def create_custom_item(
        db: Session,
        company_id: str,
        registry_type: str,
        display_name: str,
        description: str | None = None,
        config: dict | None = None,
    ) -> TenantItemConfig:
        """Create a custom item for a tenant (not in the master registry).

        Custom items have is_custom=True and a generated item_key.
        """
        item_key = f"custom.{str(uuid.uuid4())[:8]}"

        tenant_config = TenantItemConfig(
            id=str(uuid.uuid4()),
            company_id=company_id,
            registry_id=None,
            item_key=item_key,
            registry_type=registry_type,
            is_enabled=True,
            is_custom=True,
            display_name=display_name,
            config=config or {},
            sort_order=999,
        )
        db.add(tenant_config)
        db.flush()
        logger.info(
            "Created custom item %s (%s) for company=%s",
            item_key,
            display_name,
            company_id,
        )
        return tenant_config

    @staticmethod
    def update_item_config(
        db: Session,
        company_id: str,
        item_key: str,
        registry_type: str,
        config: dict | None = None,
        display_name: str | None = None,
    ) -> TenantItemConfig | None:
        """Update config or display_name for a tenant item."""
        existing = (
            db.query(TenantItemConfig)
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.item_key == item_key,
                TenantItemConfig.registry_type == registry_type,
            )
            .first()
        )
        if not existing:
            return None

        if config is not None:
            existing.config = config
        if display_name is not None:
            existing.display_name = display_name
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    @staticmethod
    def delete_custom_item(
        db: Session, company_id: str, item_key: str, registry_type: str
    ) -> bool:
        """Delete a custom item. Only custom items (is_custom=True) can be deleted.

        Returns True if found and deleted.
        """
        existing = (
            db.query(TenantItemConfig)
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.item_key == item_key,
                TenantItemConfig.registry_type == registry_type,
                TenantItemConfig.is_custom == True,  # noqa: E712
            )
            .first()
        )
        if not existing:
            return False

        db.delete(existing)
        db.flush()
        logger.info(
            "Deleted custom item %s for company=%s",
            item_key,
            company_id,
        )
        return True

    @staticmethod
    def apply_defaults_for_company(
        db: Session,
        company_id: str,
        state: str | None = None,
        business_type: str = "precast_manufacturer",
    ) -> list[TenantItemConfig]:
        """Enable all tier-2 items from the registry for a company.

        Called during onboarding. Idempotent.
        """
        registry_items = (
            db.query(ConfigurableItemRegistry)
            .filter(
                ConfigurableItemRegistry.registry_type == "compliance",
                ConfigurableItemRegistry.vertical == "manufacturing",
                ConfigurableItemRegistry.tier <= 2,
                ConfigurableItemRegistry.is_active == True,  # noqa: E712
            )
            .all()
        )

        enabled = []
        for item in registry_items:
            tenant_config = ConfigurableItemService.enable_item(
                db,
                company_id,
                item.item_key,
                item.registry_type,
                config=item.default_config,
            )
            enabled.append(tenant_config)

        db.commit()
        logger.info(
            "Applied %d default compliance items for company=%s",
            len(enabled),
            company_id,
        )
        return enabled

    @staticmethod
    def _seed_items(
        db: Session,
        items: list[dict],
        registry_type: str,
        vertical: str,
    ) -> int:
        """Seed a list of item definitions into the registry.

        Idempotent — skips items that already exist (matched by item_key + registry_type).
        Returns the count of newly created items.
        """
        created = 0
        for idx, item_def in enumerate(items):
            existing = (
                db.query(ConfigurableItemRegistry)
                .filter(
                    ConfigurableItemRegistry.item_key == item_def["item_key"],
                    ConfigurableItemRegistry.registry_type == registry_type,
                )
                .first()
            )
            if existing:
                continue

            registry_item = ConfigurableItemRegistry(
                id=str(uuid.uuid4()),
                registry_type=registry_type,
                item_key=item_def["item_key"],
                display_name=item_def["display_name"],
                description=item_def.get("description"),
                tier=item_def["tier"],
                vertical=vertical,
                tags=item_def.get("tags", []),
                default_config=item_def.get("default_config", {}),
                is_active=True,
                sort_order=idx * 10,
            )
            db.add(registry_item)
            created += 1

        return created

    @staticmethod
    def seed_registry(db: Session) -> int:
        """Seed the platform-wide registry from all item definition lists.

        Idempotent — skips items that already exist (matched by item_key + registry_type).
        Returns the total count of newly created items.
        """
        total_created = 0

        total_created += ConfigurableItemService._seed_items(
            db, MANUFACTURING_COMPLIANCE_ITEMS, "compliance", "manufacturing"
        )
        total_created += ConfigurableItemService._seed_items(
            db, VAULT_PERSONALIZATION_OPTIONS, "personalization_option", "manufacturing"
        )

        if total_created:
            db.commit()
            logger.info("Seeded %d items into registry", total_created)
        return total_created
