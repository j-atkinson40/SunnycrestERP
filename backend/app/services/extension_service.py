"""Extension service — manages extension definitions and per-tenant enablement."""

import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.extension_definition import ExtensionDefinition
from app.models.tenant_extension import TenantExtension


def list_extensions(db: Session) -> list[ExtensionDefinition]:
    return db.query(ExtensionDefinition).filter(
        ExtensionDefinition.is_active.is_(True)
    ).order_by(ExtensionDefinition.module_key, ExtensionDefinition.display_name).all()


def get_extension(db: Session, extension_key: str) -> ExtensionDefinition | None:
    return db.query(ExtensionDefinition).filter(
        ExtensionDefinition.extension_key == extension_key
    ).first()


def get_tenant_extension(db: Session, tenant_id: str, extension_key: str) -> TenantExtension | None:
    return db.query(TenantExtension).filter(
        TenantExtension.tenant_id == tenant_id,
        TenantExtension.extension_key == extension_key,
    ).first()


def is_extension_enabled(db: Session, tenant_id: str, extension_key: str) -> bool:
    te = get_tenant_extension(db, tenant_id, extension_key)
    return te is not None and te.enabled


def get_extension_config(db: Session, tenant_id: str, extension_key: str) -> dict:
    """Get merged config: schema defaults + tenant overrides."""
    ext_def = get_extension(db, extension_key)
    if not ext_def:
        return {}

    # Start with defaults from schema
    schema = ext_def.schema_dict
    defaults = {}
    for key, spec in schema.items():
        if "default" in spec:
            defaults[key] = spec["default"]

    # Merge tenant overrides
    te = get_tenant_extension(db, tenant_id, extension_key)
    if te:
        overrides = te.config_dict
        defaults.update(overrides)

    return defaults


def get_tenant_extensions(db: Session, tenant_id: str) -> list[dict]:
    """Get all extensions with their enabled state for a tenant."""
    all_exts = list_extensions(db)
    tenant_exts = db.query(TenantExtension).filter(
        TenantExtension.tenant_id == tenant_id
    ).all()
    tenant_map = {te.extension_key: te for te in tenant_exts}

    result = []
    for ext in all_exts:
        te = tenant_map.get(ext.extension_key)
        result.append({
            "extension_key": ext.extension_key,
            "module_key": ext.module_key,
            "display_name": ext.display_name,
            "description": ext.description,
            "version": ext.version,
            "enabled": te.enabled if te else False,
            "config": get_extension_config(db, tenant_id, ext.extension_key) if te and te.enabled else {},
        })
    return result


def enable_extension(
    db: Session,
    tenant_id: str,
    extension_key: str,
    config: dict | None = None,
    actor_id: str | None = None,
) -> TenantExtension:
    ext_def = get_extension(db, extension_key)
    if not ext_def:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_key}' not found")

    te = get_tenant_extension(db, tenant_id, extension_key)
    now = datetime.now(UTC)

    if te:
        te.enabled = True
        te.enabled_at = now
        te.enabled_by = actor_id
        if config is not None:
            te.config = json.dumps(config)
    else:
        te = TenantExtension(
            tenant_id=tenant_id,
            extension_key=extension_key,
            enabled=True,
            config=json.dumps(config) if config else None,
            enabled_at=now,
            enabled_by=actor_id,
        )
        db.add(te)

    db.commit()
    db.refresh(te)
    return te


def disable_extension(db: Session, tenant_id: str, extension_key: str) -> bool:
    te = get_tenant_extension(db, tenant_id, extension_key)
    if not te:
        return False
    te.enabled = False
    db.commit()
    return True


def update_extension_config(
    db: Session, tenant_id: str, extension_key: str, config: dict
) -> TenantExtension:
    te = get_tenant_extension(db, tenant_id, extension_key)
    if not te:
        raise HTTPException(status_code=404, detail="Extension not enabled for this tenant")
    te.config = json.dumps(config)
    db.commit()
    db.refresh(te)
    return te


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

FUNERAL_KANBAN_CONFIG_SCHEMA = {
    "default_view": {
        "type": "string",
        "enum": ["today", "tomorrow", "custom"],
        "default": "tomorrow",
        "label": "Default date view when opening the scheduler",
    },
    "saturday_default": {
        "type": "string",
        "enum": ["tomorrow", "monday"],
        "default": "monday",
        "label": "On Saturdays, default to showing Saturday's orders or Monday's orders",
    },
    "sunday_default": {
        "type": "string",
        "enum": ["tomorrow", "monday"],
        "default": "monday",
        "label": "On Sundays, default to showing Sunday's orders or Monday's orders",
    },
    "show_driver_count_badge": {
        "type": "boolean",
        "default": True,
        "label": "Show delivery count badge on each driver lane header",
    },
    "warn_driver_count": {
        "type": "number",
        "default": 4,
        "label": "Highlight driver lane header when delivery count reaches this number",
    },
    "card_show_cemetery": {
        "type": "boolean",
        "default": True,
        "label": "Show cemetery name on order card",
    },
    "card_show_funeral_home": {
        "type": "boolean",
        "default": True,
        "label": "Show funeral home name on order card",
    },
    "card_show_service_time": {
        "type": "boolean",
        "default": True,
        "label": "Show service time on order card",
    },
    "card_show_vault_type": {
        "type": "boolean",
        "default": True,
        "label": "Show vault type on order card",
    },
    "card_show_family_name": {
        "type": "boolean",
        "default": True,
        "label": "Show family name on order card",
    },
    "critical_window_hours": {
        "type": "number",
        "default": 4,
        "label": "Highlight order card red when this many hours from service time at scheduling",
    },
}


def seed_extensions(db: Session) -> int:
    """Seed extension definitions. Idempotent."""
    existing = {r[0] for r in db.query(ExtensionDefinition.extension_key).all()}

    EXTENSIONS = [
        {
            "extension_key": "funeral_kanban_scheduling",
            "module_key": "driver_delivery",
            "display_name": "Funeral Kanban Scheduler",
            "description": "A date-focused Kanban board for scheduling funeral vault deliveries by driver. Replicates a familiar drag-and-drop scheduling workflow where unscheduled orders are promoted into driver lanes by day.",
            "config_schema": json.dumps(FUNERAL_KANBAN_CONFIG_SCHEMA),
            "version": "1.0.0",
        },
    ]

    count = 0
    for ext in EXTENSIONS:
        if ext["extension_key"] not in existing:
            db.add(ExtensionDefinition(**ext))
            count += 1

    if count:
        db.flush()
    return count


def seed_tenant_extension_defaults(db: Session) -> int:
    """Enable funeral_kanban_scheduling for tenant 1 (first company). Idempotent."""
    from app.models.company import Company

    company = db.query(Company).order_by(Company.created_at).first()
    if not company:
        return 0

    existing = get_tenant_extension(db, company.id, "funeral_kanban_scheduling")
    if existing:
        return 0

    te = TenantExtension(
        tenant_id=company.id,
        extension_key="funeral_kanban_scheduling",
        enabled=True,
        enabled_at=datetime.now(UTC),
        config=None,  # uses all defaults
    )
    db.add(te)
    db.flush()
    return 1
