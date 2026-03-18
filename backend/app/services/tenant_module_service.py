"""Tenant module configuration service.

Manages module definitions, vertical presets, and per-tenant module state.
"""

import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.module_definition import ModuleDefinition
from app.models.preset_module import PresetModule
from app.models.tenant_module_config import TenantModuleConfig
from app.models.vertical_preset import VerticalPreset


# ---------------------------------------------------------------------------
# Module definitions
# ---------------------------------------------------------------------------

def list_module_definitions(db: Session) -> list[ModuleDefinition]:
    """Get all module definitions ordered by category and sort_order."""
    return (
        db.query(ModuleDefinition)
        .order_by(ModuleDefinition.category, ModuleDefinition.sort_order, ModuleDefinition.name)
        .all()
    )


def get_module_definition(db: Session, key: str) -> ModuleDefinition | None:
    return db.query(ModuleDefinition).filter(ModuleDefinition.key == key).first()


def get_modules_by_category(db: Session) -> dict[str, list[dict]]:
    """Return modules grouped by category for UI display."""
    modules = list_module_definitions(db)
    grouped: dict[str, list[dict]] = {}
    for m in modules:
        cat = m.category
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({
            "key": m.key,
            "name": m.name,
            "description": m.description,
            "category": m.category,
            "icon": m.icon,
            "is_core": m.is_core,
            "dependencies": m.dependency_list,
            "feature_flags": m.feature_flag_list,
            "sort_order": m.sort_order,
        })
    return grouped


# ---------------------------------------------------------------------------
# Vertical presets
# ---------------------------------------------------------------------------

def list_presets(db: Session) -> list[dict]:
    """Get all presets with their module lists."""
    presets = (
        db.query(VerticalPreset)
        .order_by(VerticalPreset.sort_order)
        .all()
    )
    result = []
    for p in presets:
        result.append({
            "id": p.id,
            "key": p.key,
            "name": p.name,
            "description": p.description,
            "icon": p.icon,
            "module_keys": [pm.module_key for pm in p.modules],
        })
    return result


def get_preset(db: Session, preset_key: str) -> dict | None:
    preset = db.query(VerticalPreset).filter(VerticalPreset.key == preset_key).first()
    if not preset:
        return None
    return {
        "id": preset.id,
        "key": preset.key,
        "name": preset.name,
        "description": preset.description,
        "icon": preset.icon,
        "module_keys": [pm.module_key for pm in preset.modules],
    }


# ---------------------------------------------------------------------------
# Tenant module config
# ---------------------------------------------------------------------------

def get_tenant_modules(db: Session, tenant_id: str) -> list[dict]:
    """Get all modules with their enabled/disabled state for a tenant."""
    definitions = list_module_definitions(db)
    configs = (
        db.query(TenantModuleConfig)
        .filter(TenantModuleConfig.tenant_id == tenant_id)
        .all()
    )
    config_map = {c.module_key: c for c in configs}

    result = []
    for m in definitions:
        cfg = config_map.get(m.key)
        result.append({
            "key": m.key,
            "name": m.name,
            "description": m.description,
            "category": m.category,
            "icon": m.icon,
            "is_core": m.is_core,
            "dependencies": m.dependency_list,
            "enabled": cfg.enabled if cfg else m.is_core,  # core modules default enabled
            "enabled_at": cfg.enabled_at.isoformat() if cfg and cfg.enabled_at else None,
            "enabled_by": cfg.enabled_by if cfg else None,
        })
    return result


def get_enabled_module_keys_for_tenant(db: Session, tenant_id: str) -> list[str]:
    """Get just the enabled module keys for a tenant."""
    # Get all core modules (always enabled)
    core_modules = (
        db.query(ModuleDefinition.key)
        .filter(ModuleDefinition.is_core.is_(True))
        .all()
    )
    core_keys = {r[0] for r in core_modules}

    # Get explicitly enabled
    enabled = (
        db.query(TenantModuleConfig.module_key)
        .filter(
            TenantModuleConfig.tenant_id == tenant_id,
            TenantModuleConfig.enabled.is_(True),
        )
        .all()
    )
    enabled_keys = {r[0] for r in enabled}

    return list(core_keys | enabled_keys)


def validate_dependencies(db: Session, tenant_id: str, module_key: str) -> list[str]:
    """Check if all dependencies are met for enabling a module.
    Returns list of missing dependency keys."""
    mod_def = get_module_definition(db, module_key)
    if not mod_def:
        return []

    deps = mod_def.dependency_list
    if not deps:
        return []

    enabled_keys = set(get_enabled_module_keys_for_tenant(db, tenant_id))
    missing = [d for d in deps if d not in enabled_keys]
    return missing


def check_dependents(db: Session, tenant_id: str, module_key: str) -> list[str]:
    """Check which enabled modules depend on this module.
    Returns list of dependent module keys that would break."""
    # Find all modules that list this module_key in their dependencies
    all_defs = list_module_definitions(db)
    enabled_keys = set(get_enabled_module_keys_for_tenant(db, tenant_id))

    dependents = []
    for m in all_defs:
        if m.key in enabled_keys and module_key in m.dependency_list:
            dependents.append(m.key)
    return dependents


def set_tenant_module(
    db: Session,
    tenant_id: str,
    module_key: str,
    enabled: bool,
    actor_id: str | None = None,
) -> dict:
    """Enable or disable a module for a tenant with dependency validation."""
    mod_def = get_module_definition(db, module_key)
    if not mod_def:
        raise HTTPException(status_code=404, detail=f"Module '{module_key}' not found")

    if mod_def.is_core and not enabled:
        raise HTTPException(status_code=400, detail=f"Core module '{module_key}' cannot be disabled")

    now = datetime.now(UTC)

    # Dependency checks
    if enabled:
        missing = validate_dependencies(db, tenant_id, module_key)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing dependencies: {', '.join(missing)}. Enable them first.",
            )
    else:
        # Check if anything depends on this module
        dependents = check_dependents(db, tenant_id, module_key)
        if dependents:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot disable '{module_key}': modules {', '.join(dependents)} depend on it. Disable them first.",
            )

    config = (
        db.query(TenantModuleConfig)
        .filter(
            TenantModuleConfig.tenant_id == tenant_id,
            TenantModuleConfig.module_key == module_key,
        )
        .first()
    )

    if config:
        config.enabled = enabled
        if enabled:
            config.enabled_at = now
            config.disabled_at = None
        else:
            config.disabled_at = now
        config.enabled_by = actor_id
    else:
        config = TenantModuleConfig(
            tenant_id=tenant_id,
            module_key=module_key,
            enabled=enabled,
            enabled_at=now if enabled else None,
            disabled_at=now if not enabled else None,
            enabled_by=actor_id,
        )
        db.add(config)

    db.commit()
    db.refresh(config)

    return {
        "tenant_id": tenant_id,
        "module_key": module_key,
        "enabled": config.enabled,
    }


def apply_preset_to_tenant(
    db: Session,
    tenant_id: str,
    preset_key: str,
    actor_id: str | None = None,
) -> dict:
    """Apply a vertical preset to a tenant — enables all preset modules + core modules."""
    preset = db.query(VerticalPreset).filter(VerticalPreset.key == preset_key).first()
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_key}' not found")

    # Get core modules and preset modules
    core_modules = (
        db.query(ModuleDefinition.key)
        .filter(ModuleDefinition.is_core.is_(True))
        .all()
    )
    core_keys = {r[0] for r in core_modules}
    preset_module_keys = {pm.module_key for pm in preset.modules}
    all_enabled_keys = core_keys | preset_module_keys

    # Get all module definitions for reference
    all_defs = {m.key: m for m in list_module_definitions(db)}

    now = datetime.now(UTC)

    # Delete existing configs for this tenant
    db.query(TenantModuleConfig).filter(
        TenantModuleConfig.tenant_id == tenant_id
    ).delete()

    # Create new configs
    created = 0
    for key in all_defs:
        enabled = key in all_enabled_keys
        config = TenantModuleConfig(
            tenant_id=tenant_id,
            module_key=key,
            enabled=enabled,
            enabled_at=now if enabled else None,
            enabled_by=actor_id,
        )
        db.add(config)
        if enabled:
            created += 1

    # Update company vertical
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if company:
        company.vertical = preset_key

    db.commit()

    return {
        "tenant_id": tenant_id,
        "preset_key": preset_key,
        "modules_enabled": created,
        "total_modules": len(all_defs),
    }


def bulk_set_tenant_modules(
    db: Session,
    tenant_id: str,
    module_keys: list[str],
    actor_id: str | None = None,
) -> dict:
    """Set the complete list of enabled modules for a tenant.
    Core modules are always included. Dependencies are validated."""
    all_defs = {m.key: m for m in list_module_definitions(db)}
    core_keys = {k for k, m in all_defs.items() if m.is_core}

    # Always include core
    enabled_keys = set(module_keys) | core_keys

    # Validate all dependencies
    for key in enabled_keys:
        mod = all_defs.get(key)
        if not mod:
            raise HTTPException(status_code=400, detail=f"Unknown module: {key}")
        for dep in mod.dependency_list:
            if dep not in enabled_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Module '{key}' requires '{dep}' which is not in the enabled set.",
                )

    now = datetime.now(UTC)

    # Delete existing and recreate
    db.query(TenantModuleConfig).filter(
        TenantModuleConfig.tenant_id == tenant_id
    ).delete()

    for key in all_defs:
        enabled = key in enabled_keys
        config = TenantModuleConfig(
            tenant_id=tenant_id,
            module_key=key,
            enabled=enabled,
            enabled_at=now if enabled else None,
            enabled_by=actor_id,
        )
        db.add(config)

    db.commit()

    return {
        "tenant_id": tenant_id,
        "enabled_count": len(enabled_keys),
        "total_modules": len(all_defs),
    }


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_module_definitions(db: Session) -> int:
    """Seed the module_definitions table. Idempotent — skips existing keys."""
    existing = {r[0] for r in db.query(ModuleDefinition.key).all()}

    MODULES = [
        # Core — always enabled, cannot be disabled
        {"key": "core", "name": "Core Platform", "description": "User management, authentication, company settings, and system configuration.", "category": "core", "icon": "Settings", "sort_order": 0, "is_core": True, "dependencies": None},
        {"key": "dashboard", "name": "Dashboard", "description": "Main dashboard with KPIs, charts, and quick-action widgets.", "category": "core", "icon": "LayoutDashboard", "sort_order": 1, "is_core": True, "dependencies": None},
        {"key": "notifications", "name": "Notifications", "description": "In-app notifications, email alerts, and notification preferences.", "category": "core", "icon": "Bell", "sort_order": 2, "is_core": True, "dependencies": None},
        {"key": "audit_logs", "name": "Audit Logs", "description": "System-wide audit trail for compliance and troubleshooting.", "category": "core", "icon": "ScrollText", "sort_order": 3, "is_core": True, "dependencies": None},

        # Business — common across verticals
        {"key": "products", "name": "Product Catalog", "description": "Product database with categories, pricing tiers, images, and bulk import.", "category": "business", "icon": "Package", "sort_order": 10, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "inventory", "name": "Inventory Management", "description": "Stock levels, transactions, reorder points, warehouse locations, and production entry.", "category": "business", "icon": "Warehouse", "sort_order": 11, "is_core": False, "dependencies": json.dumps(["products"])},
        {"key": "customers", "name": "Customer Management", "description": "Customer database, contacts, notes, credit terms, and communication history.", "category": "business", "icon": "Users", "sort_order": 12, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "sales", "name": "Sales & Quotes", "description": "Quotes, sales orders, and order management workflow.", "category": "business", "icon": "ShoppingCart", "sort_order": 13, "is_core": False, "dependencies": json.dumps(["customers", "products"])},
        {"key": "invoicing", "name": "Invoicing & AR", "description": "Invoice generation, accounts receivable, payment tracking, aging reports, and statements.", "category": "business", "icon": "Receipt", "sort_order": 14, "is_core": False, "dependencies": json.dumps(["sales"])},
        {"key": "purchasing", "name": "Purchasing & Vendors", "description": "Vendor database, purchase orders, receiving, and vendor management.", "category": "business", "icon": "Truck", "sort_order": 15, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "ap", "name": "Accounts Payable", "description": "Vendor bills, payment tracking, AP aging, and payment scheduling.", "category": "business", "icon": "CreditCard", "sort_order": 16, "is_core": False, "dependencies": json.dumps(["purchasing"])},
        {"key": "reporting", "name": "Reporting", "description": "Standard business reports, export to CSV/PDF, and scheduled report delivery.", "category": "business", "icon": "BarChart3", "sort_order": 17, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "document_mgmt", "name": "Document Management", "description": "File storage, document templates, version tracking, and digital signatures.", "category": "business", "icon": "FileText", "sort_order": 18, "is_core": False, "dependencies": json.dumps(["core"])},

        # Operations
        {"key": "hr_time", "name": "HR & Time Tracking", "description": "Clock in/out, break tracking, PTO management, early release, and payroll export.", "category": "operations", "icon": "Clock", "sort_order": 20, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "driver_delivery", "name": "Driver & Delivery", "description": "Route scheduling, mobile delivery confirmation, mileage logging, and stop management.", "category": "operations", "icon": "MapPin", "sort_order": 21, "is_core": False, "dependencies": json.dumps(["core", "customers"])},
        {"key": "pos", "name": "Point of Sale", "description": "Counter sales, barcode scanning, cash/card payments, receipts, and drawer reconciliation.", "category": "operations", "icon": "Monitor", "sort_order": 22, "is_core": False, "dependencies": json.dumps(["products", "customers"])},
        {"key": "project_mgmt", "name": "Project Management", "description": "Job creation, task assignment, timelines, resource allocation, and status reporting.", "category": "operations", "icon": "FolderKanban", "sort_order": 23, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "scheduling", "name": "Scheduling & Calendar", "description": "Staff scheduling, appointment booking, resource calendars, and availability management.", "category": "operations", "icon": "Calendar", "sort_order": 24, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "fleet_mgmt", "name": "Fleet Management", "description": "Vehicle tracking, maintenance schedules, fuel logs, and inspection records.", "category": "operations", "icon": "Car", "sort_order": 25, "is_core": False, "dependencies": json.dumps(["core"])},

        # Manufacturing vertical
        {"key": "production_scheduling", "name": "Production Scheduling", "description": "Production run planning, shift scheduling, and capacity management.", "category": "manufacturing", "icon": "Factory", "sort_order": 30, "is_core": False, "dependencies": json.dumps(["products", "inventory"])},
        {"key": "work_orders", "name": "Work Orders", "description": "Create, assign, and track work orders through production stages.", "category": "manufacturing", "icon": "ClipboardList", "sort_order": 31, "is_core": False, "dependencies": json.dumps(["production_scheduling"])},
        {"key": "bom", "name": "Bill of Materials", "description": "Multi-level BOMs, material requirements planning, and cost rollups.", "category": "manufacturing", "icon": "ListTree", "sort_order": 32, "is_core": False, "dependencies": json.dumps(["products"])},
        {"key": "quality_control", "name": "Quality Control", "description": "QC checkpoints, inspection records, non-conformance tracking, and certifications.", "category": "manufacturing", "icon": "CheckCircle", "sort_order": 33, "is_core": False, "dependencies": json.dumps(["production_scheduling"])},
        {"key": "batch_tracking", "name": "Batch & Lot Tracking", "description": "Full traceability from raw materials to finished goods with batch/lot numbers.", "category": "manufacturing", "icon": "Layers", "sort_order": 34, "is_core": False, "dependencies": json.dumps(["inventory"])},
        {"key": "equipment_maintenance", "name": "Equipment Maintenance", "description": "Preventive maintenance scheduling, work requests, and equipment lifecycle tracking.", "category": "manufacturing", "icon": "Wrench", "sort_order": 35, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "mix_designs", "name": "Mix Designs & Formulas", "description": "Concrete mix designs, batch formulas, strength testing, and compliance records.", "category": "manufacturing", "icon": "FlaskConical", "sort_order": 36, "is_core": False, "dependencies": json.dumps(["products", "quality_control"])},

        # Funeral Home vertical
        {"key": "case_management", "name": "Case Management", "description": "Funeral case tracking from first call through final disposition.", "category": "funeral", "icon": "BookOpen", "sort_order": 40, "is_core": False, "dependencies": json.dumps(["core", "customers"])},
        {"key": "arrangements", "name": "Arrangement Conference", "description": "Digital arrangement forms, package selection, and itemized pricing.", "category": "funeral", "icon": "FileSignature", "sort_order": 41, "is_core": False, "dependencies": json.dumps(["case_management"])},
        {"key": "obituaries", "name": "Obituaries & Tributes", "description": "Obituary composition, newspaper submission, and online memorial pages.", "category": "funeral", "icon": "Newspaper", "sort_order": 42, "is_core": False, "dependencies": json.dumps(["case_management"])},
        {"key": "memorial_services", "name": "Memorial Services", "description": "Service planning, chapel scheduling, music/reading selections, and programs.", "category": "funeral", "icon": "Heart", "sort_order": 43, "is_core": False, "dependencies": json.dumps(["case_management", "scheduling"])},
        {"key": "cremation_tracking", "name": "Cremation Tracking", "description": "Chain of custody, cremation scheduling, authorization forms, and ID verification.", "category": "funeral", "icon": "Flame", "sort_order": 44, "is_core": False, "dependencies": json.dumps(["case_management"])},
        {"key": "preneed", "name": "Preneed Contracts", "description": "Preneed sales, trust/insurance funding, contract management, and at-need conversion.", "category": "funeral", "icon": "FileCheck", "sort_order": 45, "is_core": False, "dependencies": json.dumps(["case_management", "customers"])},
        {"key": "aftercare", "name": "Aftercare Program", "description": "Bereavement follow-up, grief resources, anniversary reminders, and family outreach.", "category": "funeral", "icon": "HeartHandshake", "sort_order": 46, "is_core": False, "dependencies": json.dumps(["case_management"])},
        {"key": "embalming", "name": "Embalming Records", "description": "Embalming case reports, chemical tracking, and regulatory compliance.", "category": "funeral", "icon": "Stethoscope", "sort_order": 47, "is_core": False, "dependencies": json.dumps(["case_management"])},
        {"key": "funeral_transport", "name": "Funeral Transport", "description": "First call dispatch, vehicle scheduling, and transport logging.", "category": "funeral", "icon": "Ambulance", "sort_order": 48, "is_core": False, "dependencies": json.dumps(["case_management", "fleet_mgmt"])},

        # Cemetery vertical
        {"key": "lot_management", "name": "Lot & Plot Management", "description": "Cemetery mapping, lot inventory, ownership records, and availability tracking.", "category": "cemetery", "icon": "Map", "sort_order": 50, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "interment_records", "name": "Interment Records", "description": "Burial records, interment scheduling, disinterment tracking, and permit management.", "category": "cemetery", "icon": "Archive", "sort_order": 51, "is_core": False, "dependencies": json.dumps(["lot_management"])},
        {"key": "deed_management", "name": "Deed Management", "description": "Deed issuance, transfers, ownership history, and deed fee tracking.", "category": "cemetery", "icon": "Stamp", "sort_order": 52, "is_core": False, "dependencies": json.dumps(["lot_management", "customers"])},
        {"key": "memorial_sales", "name": "Memorial & Marker Sales", "description": "Monument, marker, and vase sales with installation scheduling.", "category": "cemetery", "icon": "Landmark", "sort_order": 53, "is_core": False, "dependencies": json.dumps(["lot_management", "products"])},
        {"key": "grounds_maintenance", "name": "Grounds Maintenance", "description": "Lawn care schedules, seasonal tasks, work orders, and grounds crew management.", "category": "cemetery", "icon": "TreePine", "sort_order": 54, "is_core": False, "dependencies": json.dumps(["lot_management"])},
        {"key": "endowment_care", "name": "Endowment Care Fund", "description": "Perpetual care fund tracking, investment reporting, and regulatory compliance.", "category": "cemetery", "icon": "Landmark", "sort_order": 55, "is_core": False, "dependencies": json.dumps(["lot_management"])},
        {"key": "cemetery_mapping", "name": "Cemetery Mapping", "description": "Interactive cemetery maps, GPS integration, and plot visualization.", "category": "cemetery", "icon": "MapPinned", "sort_order": 56, "is_core": False, "dependencies": json.dumps(["lot_management"])},

        # Crematory vertical
        {"key": "cremation_scheduling", "name": "Cremation Scheduling", "description": "Retort scheduling, capacity management, and multi-location coordination.", "category": "crematory", "icon": "CalendarClock", "sort_order": 60, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "chain_of_custody", "name": "Chain of Custody", "description": "Full chain of custody tracking with barcode/RFID scanning and photo verification.", "category": "crematory", "icon": "Link", "sort_order": 61, "is_core": False, "dependencies": json.dumps(["cremation_scheduling"])},
        {"key": "cremation_auth", "name": "Cremation Authorization", "description": "Digital authorization forms, medical examiner holds, and release documentation.", "category": "crematory", "icon": "ShieldCheck", "sort_order": 62, "is_core": False, "dependencies": json.dumps(["cremation_scheduling"])},
        {"key": "urn_inventory", "name": "Urn & Container Inventory", "description": "Urn catalog, inventory tracking, and container selection for families.", "category": "crematory", "icon": "Amphora", "sort_order": 63, "is_core": False, "dependencies": json.dumps(["cremation_scheduling", "products"])},
        {"key": "regulatory_compliance", "name": "Regulatory Compliance", "description": "EPA reporting, state reporting, inspection records, and compliance checklists.", "category": "crematory", "icon": "Scale", "sort_order": 64, "is_core": False, "dependencies": json.dumps(["cremation_scheduling"])},
        {"key": "retort_maintenance", "name": "Retort Maintenance", "description": "Retort maintenance logs, temperature records, and equipment lifecycle tracking.", "category": "crematory", "icon": "Thermometer", "sort_order": 65, "is_core": False, "dependencies": json.dumps(["cremation_scheduling", "equipment_maintenance"])},

        # Add-ons (cross-vertical)
        {"key": "analytics", "name": "Advanced Analytics", "description": "Custom dashboards, trend analysis, forecasting, and data visualization.", "category": "addon", "icon": "TrendingUp", "sort_order": 70, "is_core": False, "dependencies": json.dumps(["reporting"])},
        {"key": "ai_assistant", "name": "AI Assistant", "description": "Natural language commands, smart suggestions, and AI-powered insights.", "category": "addon", "icon": "Sparkles", "sort_order": 71, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "api_access", "name": "API Access", "description": "REST API access with API keys, rate limiting, and webhook support.", "category": "addon", "icon": "Code", "sort_order": 72, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "sms_notifications", "name": "SMS Notifications", "description": "Twilio-powered SMS alerts for deliveries, appointments, and reminders.", "category": "addon", "icon": "MessageSquare", "sort_order": 73, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "email_integration", "name": "Email Integration", "description": "Automated email campaigns, transactional emails, and email templates.", "category": "addon", "icon": "Mail", "sort_order": 74, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "customer_portal", "name": "Customer Portal", "description": "Self-service portal for customers to view orders, invoices, and delivery status.", "category": "addon", "icon": "Globe", "sort_order": 75, "is_core": False, "dependencies": json.dumps(["customers"])},
        {"key": "online_payments", "name": "Online Payments", "description": "Stripe integration for online invoice payments and deposit collection.", "category": "addon", "icon": "Wallet", "sort_order": 76, "is_core": False, "dependencies": json.dumps(["invoicing"])},
        {"key": "multi_location", "name": "Multi-Location", "description": "Multi-site management, inter-location transfers, and consolidated reporting.", "category": "addon", "icon": "Building2", "sort_order": 77, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "sage_integration", "name": "Sage 100 Integration", "description": "Automated CSV sync with Sage 100 for GL, AP, AR, and inventory.", "category": "addon", "icon": "RefreshCw", "sort_order": 78, "is_core": False, "dependencies": json.dumps(["core"])},
        {"key": "qbo_integration", "name": "QuickBooks Online", "description": "Direct API integration with QuickBooks Online for accounting sync.", "category": "addon", "icon": "RefreshCw", "sort_order": 79, "is_core": False, "dependencies": json.dumps(["core"])},
    ]

    count = 0
    for m in MODULES:
        if m["key"] not in existing:
            db.add(ModuleDefinition(**m))
            count += 1

    if count:
        db.flush()
    return count


def seed_vertical_presets(db: Session) -> int:
    """Seed vertical presets. Idempotent."""
    existing = {r[0] for r in db.query(VerticalPreset.key).all()}

    PRESETS = [
        {
            "key": "manufacturing",
            "name": "Manufacturing & Precast",
            "description": "Core manufacturing operations — orders, delivery, inventory, production logging, safety, and AI-assisted workflows.",
            "icon": "Factory",
            "sort_order": 0,
            "modules": [
                "ai_command_bar",
                "customers",
                "sales",
                "driver_delivery",
                "inventory",
                "daily_production_log",
                "safety_management",
            ],
        },
        {
            "key": "funeral_home",
            "name": "Funeral Home",
            "description": "Case management, FTC compliance, vault ordering, family portal, invoicing, and AI-assisted workflows.",
            "icon": "Heart",
            "sort_order": 1,
            "modules": [
                "ai_command_bar",
                "funeral_home",
            ],
        },
        {
            "key": "cemetery",
            "name": "Cemetery",
            "description": "Cemetery operations including lot management, interments, and grounds maintenance.",
            "icon": "TreePine",
            "sort_order": 2,
            "modules": [
                "ai_command_bar",
                "customers",
                "sales",
                "inventory",
            ],
        },
        {
            "key": "crematory",
            "name": "Crematory",
            "description": "Crematory operations with scheduling, chain of custody, and regulatory compliance.",
            "icon": "Flame",
            "sort_order": 3,
            "modules": [
                "ai_command_bar",
                "customers",
                "sales",
            ],
        },
    ]

    count = 0
    for p_data in PRESETS:
        module_keys = p_data.pop("modules")

        if p_data["key"] in existing:
            # Update existing preset — fix description, icon, and rebuild module list
            preset = db.query(VerticalPreset).filter(VerticalPreset.key == p_data["key"]).first()
            if preset:
                preset.name = p_data["name"]
                preset.description = p_data["description"]
                preset.icon = p_data["icon"]
                preset.sort_order = p_data["sort_order"]

                # Clear old preset modules and re-seed correct ones
                db.query(PresetModule).filter(PresetModule.preset_id == preset.id).delete()
                for mk in module_keys:
                    db.add(PresetModule(preset_id=preset.id, module_key=mk))
                count += 1
        else:
            # Create new preset
            preset = VerticalPreset(**p_data)
            db.add(preset)
            db.flush()

            for mk in module_keys:
                db.add(PresetModule(preset_id=preset.id, module_key=mk))
            count += 1

    # Remove "custom" preset if it exists — no longer offered
    custom = db.query(VerticalPreset).filter(VerticalPreset.key == "custom").first()
    if custom:
        db.query(PresetModule).filter(PresetModule.preset_id == custom.id).delete()
        db.delete(custom)

    if count:
        db.flush()
    return count


def seed_all(db: Session) -> dict:
    """Seed both module definitions and presets. Call on app startup."""
    mod_count = seed_module_definitions(db)
    preset_count = seed_vertical_presets(db)
    if mod_count or preset_count:
        db.commit()
    return {"modules_created": mod_count, "presets_created": preset_count}
