"""Extension service — manages extension catalog, installs, and tenant enablement."""

import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.extension_activity_log import ExtensionActivityLog
from app.models.extension_definition import ExtensionDefinition
from app.models.extension_notify_request import ExtensionNotifyRequest
from app.models.tenant_extension import TenantExtension


# ---------------------------------------------------------------------------
# Catalog queries
# ---------------------------------------------------------------------------

def list_extensions(db: Session) -> list[ExtensionDefinition]:
    return db.query(ExtensionDefinition).filter(
        ExtensionDefinition.is_active.is_(True)
    ).order_by(ExtensionDefinition.sort_order, ExtensionDefinition.display_name).all()


def list_catalog(
    db: Session,
    tenant_id: str,
    category: str | None = None,
    vertical: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Full catalog with tenant install status merged in."""
    q = db.query(ExtensionDefinition).filter(
        ExtensionDefinition.is_active.is_(True),
        ExtensionDefinition.hidden_from_catalog.isnot(True),
    )

    if category:
        q = q.filter(ExtensionDefinition.category == category)
    if status:
        q = q.filter(ExtensionDefinition.status == status)
    if search:
        term = f"%{search}%"
        q = q.filter(
            ExtensionDefinition.display_name.ilike(term)
            | ExtensionDefinition.tagline.ilike(term)
            | ExtensionDefinition.description.ilike(term)
        )

    exts = q.order_by(ExtensionDefinition.sort_order, ExtensionDefinition.display_name).all()

    # Get tenant installs
    tenant_exts = db.query(TenantExtension).filter(
        TenantExtension.tenant_id == tenant_id
    ).all()
    tenant_map = {te.extension_key: te for te in tenant_exts}

    result = []
    for ext in exts:
        # Vertical filter
        if vertical and vertical != "all":
            verts = ext.applicable_verticals_list
            if verts and "all" not in verts and vertical not in verts:
                continue

        te = tenant_map.get(ext.extension_key)
        item = _ext_to_catalog_item(ext, te)
        result.append(item)

    return result


def get_extension(db: Session, extension_key: str) -> ExtensionDefinition | None:
    return db.query(ExtensionDefinition).filter(
        ExtensionDefinition.extension_key == extension_key
    ).first()


def get_extension_by_id(db: Session, extension_id: str) -> ExtensionDefinition | None:
    return db.query(ExtensionDefinition).filter(
        ExtensionDefinition.id == extension_id
    ).first()


def get_extension_detail(db: Session, extension_key: str, tenant_id: str) -> dict | None:
    ext = get_extension(db, extension_key)
    if not ext:
        return None

    te = get_tenant_extension(db, tenant_id, extension_key)
    item = _ext_to_catalog_item(ext, te)
    item["config_schema"] = ext.schema_dict
    item["setup_config_schema"] = ext.setup_config_schema_dict
    item["hooks_registered"] = ext.hooks_registered_list
    item["module_key"] = ext.module_key
    item["requested_by_tenant_id"] = ext.requested_by_tenant_id
    item["created_at"] = ext.created_at
    item["updated_at"] = ext.updated_at
    return item


def get_installed_extensions(db: Session, tenant_id: str) -> list[dict]:
    """Get only extensions this tenant has active or pending_setup."""
    tenant_exts = db.query(TenantExtension).filter(
        TenantExtension.tenant_id == tenant_id,
        TenantExtension.status.in_(["active", "pending_setup"]),
    ).all()

    result = []
    for te in tenant_exts:
        ext = get_extension(db, te.extension_key)
        if ext:
            item = _ext_to_catalog_item(ext, te)
            result.append(item)
    return result


def _ext_to_catalog_item(ext: ExtensionDefinition, te: TenantExtension | None) -> dict:
    """Convert an extension + optional tenant record to a catalog item dict."""
    installed = te is not None and te.status in ("active", "pending_setup")
    return {
        "id": ext.id,
        "extension_key": ext.extension_key,
        "name": ext.display_name,
        "tagline": ext.tagline,
        "description": ext.description,
        "section": ext.section,
        "category": ext.category,
        "publisher": ext.publisher,
        "applicable_verticals": ext.applicable_verticals_list,
        "default_enabled_for": ext.default_enabled_for_list,
        "access_model": ext.access_model,
        "required_plan_tier": ext.required_plan_tier,
        "addon_price_monthly": float(ext.addon_price_monthly) if ext.addon_price_monthly else None,
        "status": ext.status,
        "version": ext.version,
        "screenshots": ext.screenshots_list,
        "feature_bullets": ext.feature_bullets_list,
        "setup_required": ext.setup_required,
        "is_customer_requested": ext.is_customer_requested,
        "notify_me_count": ext.notify_me_count or 0,
        "sort_order": ext.sort_order or 100,
        "installed": installed,
        "install_status": te.status if te else None,
        "tenant_config": te.configuration_dict if te and te.configuration else (te.config_dict if te and te.config else None),
        "enabled_at": te.enabled_at if te else None,
        "enabled_by": te.enabled_by if te else None,
        "version_at_install": te.version_at_install if te else None,
    }


# ---------------------------------------------------------------------------
# Tenant extension queries
# ---------------------------------------------------------------------------

def get_tenant_extension(db: Session, tenant_id: str, extension_key: str) -> TenantExtension | None:
    return db.query(TenantExtension).filter(
        TenantExtension.tenant_id == tenant_id,
        TenantExtension.extension_key == extension_key,
    ).first()


def is_extension_enabled(db: Session, tenant_id: str, extension_key: str) -> bool:
    """Check if extension is active for tenant. Used by FeatureGate."""
    te = get_tenant_extension(db, tenant_id, extension_key)
    if te is not None:
        return te.status == "active"

    # Fall back to default_enabled_for logic
    ext = get_extension(db, extension_key)
    if not ext:
        return False

    # Check if tenant's vertical preset is in default_enabled_for
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        return False

    defaults = ext.default_enabled_for_list
    if not defaults:
        return False

    preset = getattr(company, "vertical_preset", None) or ""
    return preset in defaults or "all" in defaults


def get_extension_config(db: Session, tenant_id: str, extension_key: str) -> dict:
    """Get merged config: schema defaults + tenant overrides."""
    ext_def = get_extension(db, extension_key)
    if not ext_def:
        return {}

    defaults = {}
    schema = ext_def.schema_dict
    for key, spec in schema.items():
        if "default" in spec:
            defaults[key] = spec["default"]

    te = get_tenant_extension(db, tenant_id, extension_key)
    if te:
        overrides = te.config_dict
        defaults.update(overrides)

    return defaults


def get_tenant_extensions_list(db: Session, tenant_id: str) -> list[dict]:
    """Get all extensions with their enabled state for a tenant (legacy)."""
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
            "enabled": te.status == "active" if te else False,
            "config": get_extension_config(db, tenant_id, ext.extension_key) if te and te.status == "active" else {},
        })
    return result


def get_active_extension_keys(db: Session, tenant_id: str) -> list[str]:
    """Return list of extension_keys that are active for this tenant."""
    tenant_exts = db.query(TenantExtension.extension_key).filter(
        TenantExtension.tenant_id == tenant_id,
        TenantExtension.status == "active",
    ).all()
    return [r[0] for r in tenant_exts]


# ---------------------------------------------------------------------------
# Install / disable / configure
# ---------------------------------------------------------------------------

_PRODUCT_LINE_EXTENSIONS: frozenset[str] = frozenset({"wastewater", "redi_rock", "rosetta", "urn_sales"})


def _update_extension_visibility(
    db: Session, tenant_id: str, extension_key: str, enabling: bool
) -> None:
    """Sync is_extension_hidden on sage-migrated customers/products when an extension is toggled."""
    if extension_key not in _PRODUCT_LINE_EXTENSIONS:
        return

    if enabling:
        # Unhide products that belong to this extension
        db.execute(
            text(
                "UPDATE products SET is_extension_hidden = false "
                "WHERE company_id = :tid AND visibility_requires_extension = :ext"
            ),
            {"tid": tenant_id, "ext": extension_key},
        )
        # Unhide contractors — any product-line extension is now active
        db.execute(
            text(
                "UPDATE customers SET is_extension_hidden = false "
                "WHERE company_id = :tid AND visibility_requires_extension = 'any_product_line'"
            ),
            {"tid": tenant_id},
        )
    else:
        # Hide products for this extension
        db.execute(
            text(
                "UPDATE products SET is_extension_hidden = true "
                "WHERE company_id = :tid AND visibility_requires_extension = :ext"
            ),
            {"tid": tenant_id, "ext": extension_key},
        )
        # Hide contractors only when no product-line extensions remain active
        active_count = db.execute(
            text(
                "SELECT COUNT(*) FROM tenant_extensions "
                "WHERE tenant_id = :tid "
                "AND extension_key IN ('wastewater', 'redi_rock', 'rosetta') "
                "AND status = 'active'"
            ),
            {"tid": tenant_id},
        ).scalar() or 0
        if active_count == 0:
            db.execute(
                text(
                    "UPDATE customers SET is_extension_hidden = true "
                    "WHERE company_id = :tid AND visibility_requires_extension = 'any_product_line'"
                ),
                {"tid": tenant_id},
            )
    db.flush()


def install_extension(
    db: Session,
    tenant_id: str,
    extension_key: str,
    actor_id: str | None = None,
) -> dict:
    """Install (enable) an extension for a tenant."""
    ext = get_extension(db, extension_key)
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_key}' not found")

    if ext.status == "coming_soon":
        raise HTTPException(status_code=400, detail="This extension is not yet available")

    if ext.status == "deprecated":
        raise HTTPException(status_code=400, detail="This extension has been deprecated")

    if ext.access_model == "plan_required":
        # TODO: check tenant plan tier
        pass

    te = get_tenant_extension(db, tenant_id, extension_key)
    now = datetime.now(UTC)

    new_status = "pending_setup" if ext.setup_required else "active"

    if te:
        te.enabled = True
        te.status = new_status
        te.enabled_at = now
        te.enabled_by = actor_id
        te.extension_id = ext.id
        te.version_at_install = ext.version
        te.disabled_at = None
        te.disabled_by = None
    else:
        te = TenantExtension(
            tenant_id=tenant_id,
            extension_key=extension_key,
            extension_id=ext.id,
            enabled=True,
            status=new_status,
            enabled_at=now,
            enabled_by=actor_id,
            version_at_install=ext.version,
        )
        db.add(te)

    _log_activity(db, tenant_id, ext.id, "enabled", actor_id, {"extension_key": extension_key})
    _update_extension_visibility(db, tenant_id, extension_key, True)

    db.commit()
    db.refresh(te)

    # Check if this extension activates a new functional area
    _notify_new_functional_area(db, tenant_id, extension_key, ext.display_name, actor_id)

    # Check if extension unlocks CRM-hidden contractor accounts
    _check_extension_crm_unlock(db, tenant_id, extension_key, ext.display_name)

    result = {
        "extension_key": extension_key,
        "status": new_status,
        "setup_config_schema": ext.setup_config_schema_dict if ext.setup_required else None,
        "message": (
            f"{ext.display_name} is now active"
            if not ext.setup_required
            else f"{ext.display_name} requires setup to complete activation"
        ),
    }
    return result


def configure_extension(
    db: Session,
    tenant_id: str,
    extension_key: str,
    configuration: dict,
    actor_id: str | None = None,
) -> dict:
    """Submit configuration for a pending_setup extension."""
    te = get_tenant_extension(db, tenant_id, extension_key)
    if not te:
        raise HTTPException(status_code=404, detail="Extension not installed")

    te.configuration = json.dumps(configuration)
    te.status = "active"
    te.enabled = True

    _log_activity(db, tenant_id, te.extension_id or "", "reconfigured", actor_id, {
        "extension_key": extension_key,
        "configuration": configuration,
    })

    db.commit()
    db.refresh(te)
    return {
        "extension_key": extension_key,
        "status": "active",
        "message": f"{extension_key} configuration saved and extension activated",
    }


def disable_extension(
    db: Session,
    tenant_id: str,
    extension_key: str,
    actor_id: str | None = None,
) -> bool:
    te = get_tenant_extension(db, tenant_id, extension_key)
    if not te:
        return False

    te.enabled = False
    te.status = "disabled"
    te.disabled_at = datetime.now(UTC)
    te.disabled_by = actor_id

    _log_activity(db, tenant_id, te.extension_id or "", "disabled", actor_id, {
        "extension_key": extension_key,
    })
    _update_extension_visibility(db, tenant_id, extension_key, False)

    db.commit()
    return True


def register_notify_interest(
    db: Session,
    tenant_id: str,
    extension_key: str,
    employee_id: str | None = None,
) -> dict:
    """Register interest in a coming_soon extension."""
    ext = get_extension(db, extension_key)
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")

    if ext.status != "coming_soon":
        raise HTTPException(status_code=400, detail="Notify is only available for coming soon extensions")

    existing = db.query(ExtensionNotifyRequest).filter(
        ExtensionNotifyRequest.tenant_id == tenant_id,
        ExtensionNotifyRequest.extension_id == ext.id,
    ).first()

    if existing:
        return {
            "extension_key": extension_key,
            "notify_me_count": ext.notify_me_count or 0,
            "message": "You're already on the notification list",
        }

    req = ExtensionNotifyRequest(
        tenant_id=tenant_id,
        extension_id=ext.id,
        employee_id=employee_id,
    )
    db.add(req)

    ext.notify_me_count = (ext.notify_me_count or 0) + 1
    db.commit()

    return {
        "extension_key": extension_key,
        "notify_me_count": ext.notify_me_count,
        "message": "You'll be notified when this extension is available",
    }


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------

def enable_extension(
    db: Session,
    tenant_id: str,
    extension_key: str,
    config: dict | None = None,
    actor_id: str | None = None,
) -> TenantExtension:
    """Legacy enable — used by platform admin routes."""
    ext = get_extension(db, extension_key)
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_key}' not found")

    te = get_tenant_extension(db, tenant_id, extension_key)
    now = datetime.now(UTC)

    if te:
        te.enabled = True
        te.status = "active"
        te.enabled_at = now
        te.enabled_by = actor_id
        te.extension_id = ext.id
        te.version_at_install = ext.version
        if config is not None:
            te.config = json.dumps(config)
    else:
        te = TenantExtension(
            tenant_id=tenant_id,
            extension_key=extension_key,
            extension_id=ext.id,
            enabled=True,
            status="active",
            config=json.dumps(config) if config else None,
            enabled_at=now,
            enabled_by=actor_id,
            version_at_install=ext.version,
        )
        db.add(te)

    _update_extension_visibility(db, tenant_id, extension_key, True)
    db.commit()
    db.refresh(te)
    return te


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
# Admin queries
# ---------------------------------------------------------------------------

def admin_list_extensions(db: Session) -> list[ExtensionDefinition]:
    """All extensions including inactive for admin management."""
    return db.query(ExtensionDefinition).order_by(
        ExtensionDefinition.sort_order, ExtensionDefinition.display_name
    ).all()


def admin_create_extension(db: Session, data: dict) -> ExtensionDefinition:
    """Create a new extension in the registry."""
    existing = get_extension(db, data["extension_key"])
    if existing:
        raise HTTPException(status_code=409, detail=f"Extension key '{data['extension_key']}' already exists")

    json_fields = ["applicable_verticals", "default_enabled_for", "screenshots",
                    "feature_bullets", "hooks_registered"]
    dict_fields = ["setup_config_schema", "config_schema"]

    kwargs = {}
    for k, v in data.items():
        if k in json_fields and isinstance(v, list):
            kwargs[k] = json.dumps(v)
        elif k in dict_fields and isinstance(v, dict):
            if k == "config_schema":
                kwargs["config_schema"] = json.dumps(v)
            else:
                kwargs[k] = json.dumps(v)
        elif k == "display_name":
            kwargs["display_name"] = v
        else:
            kwargs[k] = v

    ext = ExtensionDefinition(**kwargs)
    db.add(ext)
    db.commit()
    db.refresh(ext)
    return ext


def admin_update_extension(db: Session, extension_id: str, data: dict) -> ExtensionDefinition:
    """Update extension metadata."""
    ext = db.query(ExtensionDefinition).filter(ExtensionDefinition.id == extension_id).first()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")

    json_fields = ["applicable_verticals", "default_enabled_for", "screenshots",
                    "feature_bullets", "hooks_registered"]
    dict_fields = ["setup_config_schema", "config_schema"]

    for k, v in data.items():
        if v is None:
            continue
        if k in json_fields and isinstance(v, list):
            setattr(ext, k, json.dumps(v))
        elif k in dict_fields and isinstance(v, dict):
            if k == "config_schema":
                ext.config_schema = json.dumps(v)
            else:
                setattr(ext, k, json.dumps(v))
        elif k == "display_name":
            ext.display_name = v
        else:
            setattr(ext, k, v)

    db.commit()
    db.refresh(ext)
    return ext


def admin_get_extension_tenants(db: Session, extension_key: str) -> list[dict]:
    """Which tenants have this extension installed."""
    ext = get_extension(db, extension_key)
    if not ext:
        return []

    from app.models.company import Company

    tenants = (
        db.query(TenantExtension, Company.name)
        .join(Company, Company.id == TenantExtension.tenant_id)
        .filter(TenantExtension.extension_key == extension_key)
        .all()
    )

    return [
        {
            "tenant_id": te.tenant_id,
            "tenant_name": name,
            "status": te.status,
            "enabled_at": te.enabled_at,
        }
        for te, name in tenants
    ]


def admin_get_demand_signals(db: Session) -> list[dict]:
    """All extensions sorted by notify_me_count descending — product prioritization."""
    from app.models.company import Company

    exts = db.query(ExtensionDefinition).filter(
        ExtensionDefinition.status.in_(["coming_soon", "beta"])
    ).order_by(ExtensionDefinition.notify_me_count.desc()).all()

    result = []
    for ext in exts:
        # Get tenant names who requested
        requests = (
            db.query(ExtensionNotifyRequest, Company.name)
            .join(Company, Company.id == ExtensionNotifyRequest.tenant_id)
            .filter(ExtensionNotifyRequest.extension_id == ext.id)
            .all()
        )

        result.append({
            "id": ext.id,
            "extension_key": ext.extension_key,
            "name": ext.display_name,
            "category": ext.category,
            "tagline": ext.tagline,
            "notify_me_count": ext.notify_me_count or 0,
            "tenant_names": [name for _, name in requests],
            "status": ext.status,
        })

    return result


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------

def _log_activity(
    db: Session,
    tenant_id: str,
    extension_id: str,
    action: str,
    performed_by: str | None,
    details: dict | None = None,
):
    log = ExtensionActivityLog(
        tenant_id=tenant_id,
        extension_id=extension_id,
        action=action,
        performed_by=performed_by,
        details=json.dumps(details) if details else None,
    )
    db.add(log)


def _notify_new_functional_area(
    db: Session,
    tenant_id: str,
    extension_key: str,
    extension_display_name: str,
    actor_id: str | None,
):
    """If this extension activates a new functional area, notify owner/admins."""
    from app.services import functional_area_service, notification_service
    from app.models.user import User

    result = functional_area_service.check_new_area_on_extension_install(
        db, tenant_id, extension_key
    )
    if not result:
        return

    area_name = result["display_name"]

    # Log to activity
    _log_activity(db, tenant_id, "", "new_functional_area_available", actor_id, {
        "extension_key": extension_key,
        "area_key": result["area_key"],
        "area_display_name": area_name,
    })

    # Notify all owner/full_admin users for this tenant
    admins = (
        db.query(User)
        .filter(
            User.company_id == tenant_id,
            User.is_active.is_(True),
            User.role.in_(["owner", "admin"]),
        )
        .all()
    )

    for admin in admins:
        notification_service.create_notification(
            db,
            tenant_id,
            admin.id,
            title="New Team Area Available",
            message=(
                f"Installing {extension_display_name} unlocked a new functional area: "
                f"{area_name}. Assign employees to this area in Team Settings."
            ),
            type="info",
            category="employee",
            link="/admin/employees",
            actor_id=actor_id,
        )

    db.commit()


# ---------------------------------------------------------------------------
# Seed — full extension catalog
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

FUNERAL_COORDINATION_SETUP_SCHEMA = {
    "type": "object",
    "properties": {
        "notify_on_scheduled": {
            "type": "boolean",
            "default": True,
            "title": "Notify on scheduling confirmation",
        },
        "notify_on_departure": {
            "type": "boolean",
            "default": True,
            "title": "Notify on driver departure",
        },
        "notify_on_arrival": {
            "type": "boolean",
            "default": True,
            "title": "Notify on driver arrival",
        },
        "notify_on_setup_complete": {
            "type": "boolean",
            "default": True,
            "title": "Notify on setup complete",
        },
        "default_notification_method": {
            "type": "string",
            "enum": ["email", "sms", "both"],
            "default": "email",
            "title": "Default notification method",
        },
    },
}


EXTENSION_CATALOG = [
    # ── CORE (section: core) ──
    {
        "extension_key": "funeral_kanban_scheduler",
        "module_key": "driver_delivery",
        "display_name": "Funeral Kanban Scheduler",
        "tagline": "Drag-and-drop funeral scheduling board organized by date and driver",
        "description": "Date-based swimlane kanban board for scheduling funeral vault deliveries. Unassigned queue with drag to driver lanes. Saturday bookings auto-shift to Monday.",
        "section": "core",
        "category": "scheduling",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": ["manufacturing"],
        "cannot_disable": True,
        "hidden_from_catalog": True,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Date-based swimlane kanban board",
            "Unassigned queue with drag to driver lanes",
            "Saturday bookings auto-shift to Monday",
            "Color coding by service type",
            "Real-time across all dispatch staff",
        ],
        "setup_required": False,
        "config_schema": FUNERAL_KANBAN_CONFIG_SCHEMA,
        "sort_order": 1,
    },
    {
        "extension_key": "funeral_home_coordination",
        "module_key": "driver_delivery",
        "display_name": "Funeral Home Coordination",
        "tagline": "Automatic notifications to funeral homes and cemeteries at each delivery milestone",
        "description": "Notifies funeral homes and cemeteries automatically when deliveries are scheduled, departed, and completed. Configurable per customer.",
        "section": "core",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": ["manufacturing"],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Notifies funeral home at scheduling confirmation",
            "Departure and arrival alerts",
            "Setup complete confirmation",
            "Configurable notification recipients per customer",
            "SMS and email delivery",
        ],
        "setup_required": True,
        "setup_config_schema": FUNERAL_COORDINATION_SETUP_SCHEMA,
        "sort_order": 2,
    },
    {
        "extension_key": "npca_audit_prep",
        "module_key": "safety_management",
        "display_name": "NPCA Audit Prep",
        "tagline": "One-button NPCA inspection package — complete audit-ready documentation in seconds",
        "description": "Maintains a continuous audit readiness score across all NPCA requirements. Generates complete audit package on demand — every required document organized by audit section, formatted the way an NPCA plant certification auditor expects to see it.",
        "section": "core",
        "category": "compliance",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Real-time compliance score across all NPCA requirements",
            "Gap analysis with specific actionable items",
            "One-button audit package generation",
            "Annual safety calendar auto-generated",
            "ZIP export organized by NPCA standard",
        ],
        "setup_required": True,
        "sort_order": 3,
    },
    {
        "extension_key": "legacy_print_generator",
        "module_key": "core",
        "display_name": "Legacy Print Generator",
        "tagline": "Design personalized vault legacy prints live with families — TIF production files generated automatically",
        "description": "An interactive design tool that lets funeral directors build legacy print previews with families during arrangement conferences. Families approve via the portal. Production TIF files are automatically generated and sent to the vault manufacturer for Wilbert submission.",
        "section": "core",
        "category": "workflow",
        "applicable_verticals": ["manufacturing", "funeral_home"],
        "default_enabled_for": ["manufacturing"],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Live canvas designer — drag, drop, and preview in real time",
            "Family approves via portal — no in-person meeting required",
            "Production TIF generated automatically at print resolution",
            "File delivered directly to your vault manufacturer",
            "Supports photos, veteran emblems, religious symbols, and custom verses",
        ],
        "setup_required": True,
        "sort_order": 4,
    },

    # ── PRODUCT LINES (section: product_lines) ──
    {
        "extension_key": "wastewater_treatment",
        "module_key": "products",
        "display_name": "Wastewater Treatment Products",
        "tagline": "Septic tanks, pump chambers, and treatment products with permit-aware quoting",
        "description": "Adds wastewater product catalog templates, permit and engineering reference fields on quotes, and AI quoting intelligence for tank sizing conversations. Designed for operations selling to septic installers, general contractors, civil engineers, and municipalities.",
        "section": "product_lines",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Wastewater product catalog with standard tank configurations",
            "Permit number and engineering spec fields on every quote",
            "AI understands tank sizing shorthand — 1500 two-comp maps to the right product",
            "Buyer-appropriate quote templates for installers vs engineers",
            "Delivery notes for heavy equipment requirements",
        ],
        "setup_required": True,
        "sort_order": 1,
    },
    {
        "extension_key": "redi_rock",
        "module_key": "products",
        "display_name": "Redi-Rock Retaining Walls",
        "tagline": "Wall design assistance, block quantity calculation, and contractor-ready quoting",
        "description": "Adds Redi-Rock product catalog templates, AI-assisted wall quantity estimation, SketchUp CSV import for design-software-generated block lists, and quote templates appropriate for landscape contractors, civil engineers, and homeowners.",
        "section": "product_lines",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Three quoting paths: CSV import, manual entry, or AI-assisted estimation",
            "SketchUp CSV import auto-populates block quantities from Redi-Rock design software",
            "AI understands wall dimensions and calculates approximate block counts",
            "Contractor and homeowner quote templates with optional product photos",
            "Supports all Redi-Rock block sizes and texture variants",
        ],
        "setup_required": True,
        "sort_order": 2,
    },
    {
        "extension_key": "rosetta_hardscapes",
        "module_key": "products",
        "display_name": "Rosetta Hardscapes",
        "tagline": "Decorative concrete product catalog and visual quoting for landscape and hardscape projects",
        "description": "Adds Rosetta Hardscapes product catalog templates, visual quote presentations with product photos, and AI quoting intelligence for decorative concrete conversations. Designed for operations selling to landscape contractors and homeowners.",
        "section": "product_lines",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Rosetta product catalog with decorative concrete product line",
            "Visual quotes with product photos — homeowners see what they are buying",
            "AI understands Rosetta product names and application descriptions",
            "Separate templates for contractors and homeowners",
            "Square footage based quantity estimation for paver and wall products",
        ],
        "setup_required": True,
        "sort_order": 3,
    },
    {
        "extension_key": "urn_sales",
        "module_key": "products",
        "display_name": "Urn Sales & Catalog",
        "tagline": "Cremation urn catalog with Wilbert PDF ingestion, web enrichment, and markup pricing",
        "description": "Full cremation urn product management for Wilbert licensees. Import your Wilbert catalog PDF to populate 250+ SKUs with dimensions, materials, and product types automatically. Enrich with descriptions and images from wilbert.com. Set retail prices with bulk markup tools, CSV import, or inline editing. Track inventory for in-stock urns and manage drop-ship orders through Wilbert.",
        "section": "product_lines",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Import Wilbert PDF catalog — extracts SKUs, dimensions, materials, and product types automatically",
            "Web enrichment from wilbert.com — pulls descriptions, images, and related items",
            "Bulk markup pricing — set retail prices by material, type, or entire catalog with configurable rounding",
            "CSV and inline price editing — update costs and retail prices individually or in bulk",
            "In-stock and drop-ship inventory tracking with reorder points and Wilbert order management",
        ],
        "setup_required": True,
        "sort_order": 4,
    },

    # ── BASIC OPERATIONS (section: basic_operations) ──
    {
        "extension_key": "purchasing_vendors",
        "module_key": "purchasing",
        "display_name": "Purchasing & Vendors",
        "tagline": "Vendor management, purchase orders, and bill tracking — lean and straightforward",
        "description": "A focused purchasing workflow designed for small manufacturing operations. Manage your vendors, create and send purchase orders, receive against POs, and track what you owe. Syncs to QuickBooks. No complex approval workflows — just the purchasing flow a 15-person operation actually needs.",
        "section": "basic_operations",
        "category": "operations",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Vendor list with contact info and payment terms",
            "Create and send purchase orders",
            "Receive against POs — partial and full receipt",
            "Bill tracking and payment recording",
            "QuickBooks sync for AP transactions",
        ],
        "setup_required": True,
        "sort_order": 1,
    },
    {
        "extension_key": "hr_time_tracking",
        "module_key": "core",
        "display_name": "HR & Time Tracking",
        "tagline": "Employee hours, PTO balances, and payroll export — lean and mobile-friendly",
        "description": "Simple time tracking designed for manufacturing operations. Employees clock in and out from their phone. Managers approve timesheets. PTO balances tracked automatically. Payroll summary exports to CSV for your payroll provider. No complex HR workflows.",
        "section": "basic_operations",
        "category": "operations",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Mobile clock in and out — works on any phone browser",
            "Manager timesheet approval",
            "PTO balance tracking and requests",
            "Payroll summary CSV export",
            "Overtime calculation and alerts",
        ],
        "setup_required": True,
        "sort_order": 2,
    },
    {
        "extension_key": "point_of_sale",
        "module_key": "sales",
        "display_name": "Point of Sale",
        "tagline": "Walk-in counter sales with cash and card payments — built for the vault yard",
        "description": "A lean POS for manufacturers who sell direct at the counter or yard. Process walk-in sales, accept cash or card, print receipts. Inventory updates automatically. Syncs to QuickBooks. Designed for vault yards and precast operations, not retail stores.",
        "section": "basic_operations",
        "category": "operations",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Counter sales from any tablet or computer",
            "Cash and card payment processing",
            "Receipt printing and email",
            "Automatic inventory update on sale",
            "QuickBooks sync for sales transactions",
        ],
        "setup_required": True,
        "sort_order": 3,
    },
    {
        "extension_key": "scheduling_calendar",
        "module_key": "core",
        "display_name": "Staff Scheduling & Calendar",
        "tagline": "Shift scheduling, staff availability, and team calendar — separate from delivery scheduling",
        "description": "Staff scheduling for your manufacturing operation. Plan shifts, track who is available, and manage time-off requests. Separate from the delivery scheduling board — this is for managing your team, not your trucks.",
        "section": "basic_operations",
        "category": "scheduling",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "coming_soon",
        "version": "1.0.0",
        "feature_bullets": [
            "Shift planning with drag-and-drop schedule builder",
            "Staff availability and time-off management",
            "Team calendar view",
            "Shift notifications to employees",
            "Integrates with HR and Time Tracking extension",
        ],
        "setup_required": True,
        "sort_order": 4,
    },

    # ── ADVANCED MANUFACTURING (section: advanced_manufacturing) ──
    {
        "extension_key": "work_orders",
        "module_key": "work_orders",
        "display_name": "Work Orders & Production Scheduling",
        "tagline": "Formal work order tracking from sales order through production completion",
        "description": "For operations that want detailed production planning. Create work orders from sales orders, track production status through a formal kanban board, and manage the complete order-to-inventory lifecycle. Recommended for plants producing 50+ units per week or managing multiple product lines simultaneously.",
        "section": "advanced_manufacturing",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Work orders auto-created from confirmed sales orders",
            "Production board with kanban status tracking",
            "Connects to pour events and cure tracking when both extensions are enabled",
            "Inventory automatically updated on completion",
            "On-time production reporting",
        ],
        "setup_required": True,
        "sort_order": 1,
    },
    {
        "extension_key": "pour_events_cure_tracking",
        "module_key": "work_orders",
        "display_name": "Pour Events & Cure Tracking",
        "tagline": "Batch-level production traceability from pour through cure release",
        "description": "Track individual pour events, record batch ticket data, and manage cure schedules for each production run. Provides full traceability from finished product back to the batch it was poured in. Recommended for NPCA certified plants and operations that want batch-level quality documentation.",
        "section": "advanced_manufacturing",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Pour events link multiple work orders to a single production run",
            "Batch ticket records mix design, slump, temperatures, yield",
            "Cure schedule tracking with automatic release notifications",
            "Full traceability: finished unit to QC to batch to raw materials",
            "Feeds NPCA audit documentation automatically",
        ],
        "setup_required": True,
        "sort_order": 2,
    },
    {
        "extension_key": "qc_module_full",
        "module_key": "safety_management",
        "display_name": "Full QC Module",
        "tagline": "Detailed quality inspection workflows with pressure testing and mobile capture",
        "description": "Complete quality control system with product inspection checklists, pressure test cylinder tracking, photo documentation, defect classification, and disposition workflow. Builds on the basic QC capture in NPCA Audit Prep with full inspection depth. Recommended for NPCA certified plants.",
        "section": "advanced_manufacturing",
        "category": "compliance",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Mobile inspection interface for yard and shop floor",
            "Pressure test cylinder tracking linked to pour batches",
            "Photo documentation with defect annotation",
            "Pass/fail disposition with scrap tracking",
            "QC certificates generated automatically on pass",
        ],
        "setup_required": True,
        "sort_order": 3,
    },
    {
        "extension_key": "bill_of_materials",
        "module_key": "inventory",
        "display_name": "Bill of Materials",
        "tagline": "Mix designs, raw material requirements, and cost rollups per product",
        "description": "Define the raw material composition of every product you make. Calculate material requirements from open work orders. Track raw material costs and roll them up to product cost. Connects to purchasing for automatic reorder suggestions when materials run low.",
        "section": "advanced_manufacturing",
        "category": "operations",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Multi-level bill of materials per product",
            "Material requirements planning from open work orders",
            "Cost rollup to product cost",
            "Low material alerts and purchase order suggestions",
            "Connects to Pour Events for batch-level material consumption",
        ],
        "setup_required": True,
        "sort_order": 4,
    },
    {
        "extension_key": "equipment_maintenance",
        "module_key": "safety_management",
        "display_name": "Equipment Maintenance",
        "tagline": "Preventive maintenance schedules, work requests, and equipment lifecycle tracking",
        "description": "Track scheduled maintenance for your plant equipment — batch plant, mixer, forklifts, and other production assets. Log maintenance performed, track equipment downtime, and get alerts when PM is due. Separate from safety inspections — this is for keeping your equipment running.",
        "section": "advanced_manufacturing",
        "category": "operations",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Equipment asset registry with maintenance schedules",
            "PM alerts based on calendar or usage hours",
            "Maintenance work order logging",
            "Equipment downtime tracking",
            "Maintenance cost tracking per asset",
        ],
        "setup_required": True,
        "sort_order": 5,
    },
    {
        "extension_key": "capacity_planning",
        "module_key": "sales",
        "display_name": "Capacity Planning",
        "tagline": "Production capacity vs demand visibility — know before you are overcommitted",
        "description": "See your production capacity against committed order demand over the next 4-6 weeks. Know before you are in trouble — identify when demand exceeds capacity so you can accelerate production, set realistic customer expectations, or identify subcontract opportunities.",
        "section": "advanced_manufacturing",
        "category": "reporting",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Forward-looking capacity vs demand view",
            "Mold utilization tracking",
            "Cure schedule impact on available capacity",
            "Early warning when demand exceeds capacity",
            "Connects to work orders and production scheduling",
        ],
        "setup_required": True,
        "sort_order": 6,
    },
    {
        "extension_key": "mold_inventory",
        "module_key": "inventory",
        "display_name": "Mold Inventory",
        "tagline": "Track your molds, their condition, cycle counts, and maintenance history",
        "description": "Your molds are capital assets that directly constrain production capacity. Track which molds you own, what product they produce, their current condition, cycle count against rated life, maintenance history, and current status. Surfaces mold constraints on the production board.",
        "section": "advanced_manufacturing",
        "category": "operations",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "cannot_disable": False,
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Mold asset registry with product mapping",
            "Cycle count tracking against rated mold life",
            "Maintenance history per mold",
            "Current status tracking: available, in use, in cure, under repair",
            "Mold constraint visibility on production board",
        ],
        "setup_required": True,
        "sort_order": 7,
    },
]


def seed_extensions(db: Session) -> int:
    """Seed extension catalog. Idempotent — updates existing, creates new."""
    try:
        existing = {r.extension_key: r for r in db.query(ExtensionDefinition).all()}
    except Exception:
        # Table or column may not exist yet (migration pending) — skip seeding
        db.rollback()
        return 0

    count = 0
    for ext_data in EXTENSION_CATALOG:
        key = ext_data["extension_key"]

        # Prepare kwargs with JSON serialization
        kwargs = {}
        json_fields = ["applicable_verticals", "default_enabled_for", "feature_bullets",
                        "screenshots", "hooks_registered"]
        dict_fields = ["config_schema", "setup_config_schema"]

        for k, v in ext_data.items():
            if k in json_fields and isinstance(v, list):
                kwargs[k] = json.dumps(v)
            elif k in dict_fields and isinstance(v, dict):
                kwargs[k] = json.dumps(v)
            else:
                kwargs[k] = v

        if key in existing:
            # Update existing extension with new catalog data
            ext = existing[key]
            for k, v in kwargs.items():
                if k != "extension_key":
                    setattr(ext, k, v)
        else:
            db.add(ExtensionDefinition(**kwargs))
            count += 1

    if count:
        db.flush()
    return count


def seed_tenant_extension_defaults(db: Session) -> int:
    """Enable default extensions for tenant 1 (first company). Idempotent."""
    from app.models.company import Company

    company = db.query(Company).order_by(Company.created_at).first()
    if not company:
        return 0

    count = 0
    for ext_data in EXTENSION_CATALOG:
        if ext_data["status"] != "active":
            continue

        defaults = ext_data.get("default_enabled_for", [])
        # For now, enable all active extensions that have default_enabled_for set
        # (since we don't know the company's vertical preset reliably)
        if not defaults:
            continue

        existing = get_tenant_extension(db, company.id, ext_data["extension_key"])
        if existing:
            continue

        ext_def = get_extension(db, ext_data["extension_key"])
        if not ext_def:
            continue

        te = TenantExtension(
            tenant_id=company.id,
            extension_key=ext_data["extension_key"],
            extension_id=ext_def.id,
            enabled=True,
            status="active" if not ext_data.get("setup_required") else "pending_setup",
            enabled_at=datetime.now(UTC),
            version_at_install=ext_data.get("version", "1.0.0"),
        )
        db.add(te)
        count += 1

    if count:
        db.flush()
    return count


def _check_extension_crm_unlock(
    db: Session, tenant_id: str, extension_key: str, display_name: str
) -> None:
    """After extension enable, check if contractor accounts become CRM-visible.

    If so, log a message. A future version can create an onboarding checklist
    item to review newly-visible accounts.
    """
    try:
        from app.services.crm.crm_visibility_service import check_extension_crm_unlock
        unlocked = check_extension_crm_unlock(db, tenant_id, extension_key)
        if unlocked > 0:
            import logging
            logging.getLogger(__name__).info(
                "Extension %s unlocked %d contractor accounts in CRM for tenant %s",
                extension_key, unlocked, tenant_id,
            )
    except Exception:
        pass  # Non-critical — don't block extension install
