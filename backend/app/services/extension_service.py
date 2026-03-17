"""Extension service — manages extension catalog, installs, and tenant enablement."""

import json
from datetime import UTC, datetime

from fastapi import HTTPException
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
    q = db.query(ExtensionDefinition).filter(ExtensionDefinition.is_active.is_(True))

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

    db.commit()
    db.refresh(te)

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
    # ── Active extensions ──
    {
        "extension_key": "funeral_kanban_scheduling",
        "module_key": "driver_delivery",
        "display_name": "Funeral Kanban Scheduler",
        "tagline": "Drag-and-drop funeral scheduling board organized by date and driver",
        "description": "A date-focused Kanban board for scheduling funeral vault deliveries by driver. Replicates a familiar drag-and-drop scheduling workflow where unscheduled orders are promoted into driver lanes by day. Saturday bookings automatically shift to Monday's view. Critical delivery windows are highlighted in red when service times are approaching.",
        "category": "scheduling",
        "applicable_verticals": ["funeral_home", "manufacturing"],
        "default_enabled_for": ["funeral_home", "manufacturing"],
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
        "sort_order": 10,
    },
    {
        "extension_key": "funeral_home_coordination",
        "module_key": "driver_delivery",
        "display_name": "Funeral Home Coordination",
        "tagline": "Automatic notifications to funeral homes and cemeteries at each delivery milestone",
        "description": "Keep funeral homes and cemeteries informed at every stage of the vault delivery process. Automatic notifications are sent when deliveries are scheduled, when drivers depart, arrive, and complete setup. Configure which events trigger notifications and choose between email, SMS, or both for each customer.",
        "category": "communications",
        "applicable_verticals": ["funeral_home", "manufacturing"],
        "default_enabled_for": ["funeral_home", "manufacturing"],
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
        "sort_order": 20,
    },
    {
        "extension_key": "osha_inspection_prep",
        "module_key": "safety_management",
        "display_name": "OSHA Inspection Prep",
        "tagline": "One-button OSHA inspection package — complete audit-ready documentation in seconds",
        "description": "Generate a complete OSHA inspection-ready document package with a single click. Includes compliance scores across all OSHA requirements, gap analysis with specific actionable items, annual safety calendar, and a ZIP export organized by OSHA standard. Perfect for preparing before scheduled inspections or responding quickly to surprise visits.",
        "category": "compliance",
        "applicable_verticals": ["all"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "active",
        "version": "1.0.0",
        "feature_bullets": [
            "Generates complete 7-section inspection document package",
            "Real-time compliance score across all OSHA requirements",
            "Gap analysis with specific actionable items",
            "Annual safety calendar auto-generated from your requirements",
            "ZIP export organized by OSHA standard",
        ],
        "setup_required": False,
        "sort_order": 30,
    },

    # ── Coming soon extensions ──
    {
        "extension_key": "npca_audit_automation",
        "module_key": "safety_management",
        "display_name": "NPCA Audit Automation",
        "tagline": "Automated NPCA plant certification audit preparation and compliance tracking",
        "description": "Streamline your NPCA plant certification process with automated audit preparation. Track all certification requirements, generate pre-audit checklists, and produce documentation packages that map directly to NPCA standards. Reduces audit preparation time from weeks to hours.",
        "category": "compliance",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Maps directly to NPCA plant certification standards",
            "Automated pre-audit checklist generation",
            "Documentation package builder for auditors",
            "Tracks certification renewal dates and requirements",
            "Historical audit result tracking and trend analysis",
        ],
        "setup_required": False,
        "sort_order": 200,
    },
    {
        "extension_key": "catholic_diocese_config",
        "module_key": "core",
        "display_name": "Catholic Diocese Configuration",
        "tagline": "Pre-configured cemetery management rules for Catholic diocese requirements",
        "description": "Automatically applies Catholic diocese-specific burial rules, section management, and record-keeping requirements. Includes templates for diocese reporting, consecration tracking, and compliance with canon law burial regulations.",
        "category": "industry_specific",
        "applicable_verticals": ["cemetery"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Pre-configured Catholic burial rules and section management",
            "Diocese reporting templates",
            "Consecration and blessing tracking",
            "Canon law compliance automation",
        ],
        "setup_required": True,
        "sort_order": 210,
    },
    {
        "extension_key": "cremation_recycling_integration",
        "module_key": "core",
        "display_name": "Cremation Recycling Integration",
        "tagline": "Automated tracking and reporting for post-cremation recycling programs",
        "description": "Track recycled materials from the cremation process with full chain-of-custody documentation. Integrates with major recycling partners, automates weight logging, and generates environmental impact reports and revenue reconciliation.",
        "category": "integrations",
        "applicable_verticals": ["crematory"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Chain-of-custody documentation for recycled materials",
            "Integration with recycling partner portals",
            "Automated weight logging and batch tracking",
            "Environmental impact and revenue reports",
        ],
        "setup_required": True,
        "sort_order": 220,
    },
    {
        "extension_key": "cemetery_equipment_ordering",
        "module_key": "purchasing",
        "display_name": "Cemetery Equipment Ordering",
        "tagline": "Streamlined equipment procurement for cemetery maintenance and operations",
        "description": "Simplified purchasing workflow designed for cemetery-specific equipment: lowering devices, tents, chairs, grave liners, and maintenance equipment. Includes vendor catalogs for major cemetery supply companies and automatic reorder points for consumable items.",
        "category": "integrations",
        "applicable_verticals": ["cemetery"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Cemetery-specific equipment catalogs",
            "Auto-reorder for consumable items",
            "Vendor catalog integration for major suppliers",
            "Equipment lifecycle tracking and replacement scheduling",
        ],
        "setup_required": False,
        "sort_order": 230,
    },
    {
        "extension_key": "columbarium_revenue_dashboard",
        "module_key": "sales",
        "display_name": "Columbarium Revenue Dashboard",
        "tagline": "Real-time niche sales, occupancy rates, and revenue forecasting for columbariums",
        "description": "Purpose-built analytics for columbarium management. Track niche sales velocity, occupancy rates by section, revenue per square foot, and forecast future capacity needs. Includes visual floorplan overlays and pre-need vs. at-need sales comparison.",
        "category": "reporting",
        "applicable_verticals": ["cemetery"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Real-time niche occupancy and sales dashboard",
            "Revenue per square foot and section comparison",
            "Pre-need vs. at-need sales analytics",
            "Capacity forecasting and expansion planning",
            "Visual floorplan overlay with status indicators",
        ],
        "setup_required": False,
        "sort_order": 240,
    },
    {
        "extension_key": "pre_need_lead_capture",
        "module_key": "sales",
        "display_name": "Pre-Need Lead Capture",
        "tagline": "Web forms and lead tracking for pre-need funeral and cemetery arrangements",
        "description": "Embed lead capture forms on your website to collect pre-need arrangement inquiries. Automatically creates leads in your CRM, assigns to counselors, and tracks the sales pipeline from inquiry to signed contract. Includes follow-up reminder automation.",
        "category": "workflow",
        "applicable_verticals": ["funeral_home"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Embeddable web forms for pre-need inquiries",
            "Automatic lead creation and counselor assignment",
            "Sales pipeline tracking from inquiry to contract",
            "Automated follow-up reminders",
            "Conversion rate analytics by source",
        ],
        "setup_required": True,
        "sort_order": 250,
    },
    {
        "extension_key": "mobile_po_entry",
        "module_key": "purchasing",
        "display_name": "Mobile PO Entry",
        "tagline": "Create and approve purchase orders from the plant floor or job site",
        "description": "A mobile-optimized interface for creating purchase orders on the go. Foremen and plant managers can snap a photo of what's needed, select from approved vendor catalogs, and submit POs for approval — all from their phone. Includes barcode scanning for quick product lookup.",
        "category": "workflow",
        "applicable_verticals": ["manufacturing"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Mobile-first PO creation interface",
            "Photo attachment for job site needs",
            "Barcode scanning for product lookup",
            "Multi-level approval workflow",
            "Push notifications for approval status",
        ],
        "setup_required": False,
        "sort_order": 260,
    },
    {
        "extension_key": "quickbooks_sync",
        "module_key": "core",
        "display_name": "QuickBooks Sync",
        "tagline": "Two-way synchronization with QuickBooks Online for invoices, payments, and accounts",
        "description": "Bidirectional sync between your platform and QuickBooks Online. Invoices, customer payments, vendor bills, and chart of accounts stay in sync automatically. Includes conflict resolution, sync monitoring dashboard, and manual push/pull controls.",
        "category": "integrations",
        "applicable_verticals": ["all"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Two-way sync for invoices, payments, and bills",
            "Chart of accounts mapping wizard",
            "Conflict detection and resolution",
            "Real-time sync monitoring dashboard",
            "Manual push/pull controls for individual records",
        ],
        "setup_required": True,
        "sort_order": 270,
    },
    {
        "extension_key": "monument_dealer_portal",
        "module_key": "sales",
        "display_name": "Monument Dealer Portal",
        "tagline": "Self-service portal for monument dealers to place orders and check status",
        "description": "Give your monument dealer partners a branded portal to browse your catalog, place orders, track delivery status, and manage their account. Includes dealer-specific pricing tiers, order history, and automated delivery notifications.",
        "category": "industry_specific",
        "applicable_verticals": ["cemetery"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Branded dealer portal with custom pricing",
            "Self-service order placement and tracking",
            "Dealer-specific catalog and price tiers",
            "Automated delivery status notifications",
        ],
        "setup_required": True,
        "sort_order": 280,
    },
    {
        "extension_key": "vet_clinic_intake_portal",
        "module_key": "core",
        "display_name": "Vet Clinic Intake Portal",
        "tagline": "Streamlined intake forms and scheduling for veterinary clinic cremation partners",
        "description": "A portal for veterinary clinic partners to submit cremation requests, track status, and manage their account. Includes configurable intake forms, automatic scheduling based on capacity, and return notification when cremation is complete.",
        "category": "integrations",
        "applicable_verticals": ["crematory"],
        "default_enabled_for": [],
        "access_model": "included",
        "status": "coming_soon",
        "version": "0.1.0",
        "feature_bullets": [
            "Configurable intake forms for vet clinic partners",
            "Automatic scheduling based on crematory capacity",
            "Real-time status tracking for clinic staff",
            "Return notification when cremation is complete",
            "Monthly statement generation per clinic",
        ],
        "setup_required": True,
        "sort_order": 290,
    },
]


def seed_extensions(db: Session) -> int:
    """Seed extension catalog. Idempotent — updates existing, creates new."""
    existing = {r.extension_key: r for r in db.query(ExtensionDefinition).all()}

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
