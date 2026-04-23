"""
Permission registry — single source of truth for all available permissions.

Each module defines a list of actions. New modules are added here as they're built.
The flat permission key format is "module.action" (e.g., "users.view").

Permissions are grouped by category for the UI.
"""

# ── Permission definitions by category ──────────────────────────────────────

PERMISSION_CATEGORIES: dict[str, dict[str, list[str]]] = {
    "financials": {
        "financials": ["view"],
        "financials.invoices": ["view", "create", "edit", "void"],
        "financials.payments": ["view", "create"],
        "financials.ar": ["view", "action"],
        "financials.statements": ["view", "create"],
        "financials.price_management": ["view", "edit"],
        "financials.ap": ["view", "action"],
        "orders": ["view_from_invoice"],
        "purchase_orders": ["view_from_ap"],
        "invoice": ["approve"],
        "reports": ["view"],
    },
    "operations": {
        "operations": ["view"],
        "orders": ["view", "create", "edit", "edit_status", "edit_scheduling_fields", "view_assigned", "mark_delivered"],
        "order_station": ["view"],
        "operations_board": ["view", "edit"],
        "scheduling_board": ["view"],
        "driver.console": ["view"],
    },
    "production": {
        "production_hub": ["view", "edit"],
        "production_log": ["view", "create", "edit", "delete"],
        "work_orders": ["view", "create", "edit", "delete"],
        "qc": ["view", "create", "edit", "delete"],
        "pour_events": ["view", "create", "edit"],
        "mix_designs": ["view", "create", "edit", "delete"],
        "cure_schedules": ["view", "create", "edit", "delete"],
    },
    "crm": {
        "crm": ["view"],
        "crm.companies": ["create", "edit"],
        "crm.contacts": ["create", "edit"],
        "crm.call_log": ["view"],
    },
    "legacy": {
        "legacy": ["view", "create", "review"],
        "legacy_studio": ["view", "create", "edit", "approve", "send", "delete"],
        "personalization": ["view", "create", "complete", "approve"],
    },
    "disinterment": {
        "disinterments": ["view", "manage", "schedule", "sign"],
        "disinterment_settings": ["manage"],
        "union_rotations": ["view", "manage"],
    },
    "knowledge_training": {
        "knowledge_base": ["view", "edit"],
        "training": ["view", "edit", "admin"],
    },
    "settings": {
        "settings": ["view"],
        "settings.users": ["manage"],
        "settings.billing": ["view", "edit"],
        "settings.integrations": ["manage"],
        "settings.permissions": ["manage"],
    },
    "other": {
        "dashboard": ["view"],
        "audit": ["view"],
        "company": ["view", "edit"],
        "employees": ["view", "edit", "view_notes"],
        "users": ["view", "create", "edit", "delete"],
        "roles": ["view", "create", "edit", "delete"],
        "departments": ["view", "create", "edit", "delete"],
        "products": ["view", "create", "edit", "delete"],
        "inventory": ["view", "create", "edit", "delete"],
        "equipment": ["view", "create", "edit", "delete"],
        "customers": ["view", "create", "edit", "delete"],
        "vendors": ["view", "create", "edit", "delete"],
        "delivery": ["view", "create", "edit", "delete", "dispatch", "track", "assign_driver", "finalize_schedule", "edit_hole_dug"],
        "drivers": ["view", "create", "edit", "delete"],
        "vehicles": ["view", "create", "edit", "delete"],
        "routes": ["view", "create", "edit", "delete", "dispatch"],
        "carriers": ["view", "create", "edit", "delete"],
        "safety": ["view", "create", "edit", "delete"],
        "safety.trainer": ["view", "generate", "approve"],
        "announcements": ["view", "create", "edit", "delete"],
        # Funeral home modules
        "fh_cases": ["view", "create", "edit", "delete"],
        "fh_price_list": ["view", "create", "edit"],
        "fh_vault_orders": ["view", "create", "edit"],
        "fh_obituaries": ["view", "create", "edit"],
        "fh_invoices": ["view", "create", "edit", "void"],
        "fh_compliance": ["view"],
        "fh_portal": ["manage"],
        # AP module (legacy keys)
        "ap": [
            "view", "create_po", "receive", "create_bill",
            "approve_bill", "record_payment", "export", "void",
        ],
        # AR module (legacy keys)
        "ar": [
            "view", "create_quote", "create_order", "update_order",
            "create_invoice", "record_payment", "void",
        ],
    },
}

# Backward-compatible flat dict for existing code that uses PERMISSIONS
PERMISSIONS: dict[str, list[str]] = {}
for _cat_modules in PERMISSION_CATEGORIES.values():
    for _module, _actions in _cat_modules.items():
        if _module in PERMISSIONS:
            existing = set(PERMISSIONS[_module])
            existing.update(_actions)
            PERMISSIONS[_module] = sorted(existing)
        else:
            PERMISSIONS[_module] = _actions


def get_all_permission_keys() -> list[str]:
    """Return flat list of all permission keys, e.g. ['dashboard.view', 'users.view', ...]"""
    return [
        f"{module}.{action}"
        for module, actions in PERMISSIONS.items()
        for action in actions
    ]


def get_permissions_by_category() -> dict[str, list[dict]]:
    """Return permissions grouped by category for the UI."""
    result: dict[str, list[dict]] = {}
    for category, modules in PERMISSION_CATEGORIES.items():
        perms = []
        for module, actions in modules.items():
            for action in actions:
                slug = f"{module}.{action}"
                perms.append({
                    "slug": slug,
                    "name": _slug_to_name(slug),
                    "category": category,
                })
        result[category] = perms
    return result


def _slug_to_name(slug: str) -> str:
    """Convert 'financials.invoices.view' → 'View Invoices'."""
    parts = slug.split(".")
    if len(parts) == 2:
        module, action = parts
        return f"{action.replace('_', ' ').title()} {module.replace('_', ' ').title()}"
    elif len(parts) == 3:
        _, sub, action = parts
        return f"{action.replace('_', ' ').title()} {sub.replace('_', ' ').title()}"
    return slug.replace(".", " ").replace("_", " ").title()


# ── PERMISSION DISPLAY NAMES ────────────────────────────────────────────────
# Used in the UI for human-readable permission names

PERMISSION_DISPLAY_NAMES: dict[str, str] = {
    "financials.view": "View Financials",
    "financials.invoices.view": "View Invoices",
    "financials.invoices.create": "Create Invoices",
    "financials.invoices.edit": "Edit Invoices",
    "financials.invoices.void": "Void Invoices",
    "financials.payments.view": "View Payments",
    "financials.payments.create": "Record Payments",
    "financials.ar.view": "View AR",
    "financials.ar.action": "Take Action on AR",
    "financials.statements.view": "View Statements",
    "financials.statements.create": "Create Statements",
    "financials.price_management.view": "View Price Management",
    "financials.price_management.edit": "Edit Price Management",
    "financials.ap.view": "View AP",
    "financials.ap.action": "Take Action on AP",
    "orders.view_from_invoice": "View Orders from Invoice Context",
    "purchase_orders.view_from_ap": "View POs from AP Context",
    "invoice.approve": "Approve Invoices",
    "reports.view": "View Reports",
    "operations.view": "View Operations",
    "orders.view": "View Orders",
    "orders.create": "Create Orders",
    "orders.edit": "Edit Orders",
    "orders.edit_status": "Update Order Status",
    "orders.view_assigned": "View Assigned Orders",
    "orders.mark_delivered": "Mark Orders Delivered",
    "order_station.view": "View Order Station",
    "operations_board.view": "View Operations Board",
    "operations_board.edit": "Edit Operations Board",
    "scheduling_board.view": "View Scheduling Board",
    "driver.console.view": "Access Driver Console",
    "production_hub.view": "View Production Hub",
    "production_hub.edit": "Edit Production Hub",
    "crm.view": "View CRM",
    "crm.companies.create": "Create Companies",
    "crm.companies.edit": "Edit Companies",
    "crm.contacts.create": "Create Contacts",
    "crm.contacts.edit": "Edit Contacts",
    "crm.call_log.view": "View Call Log",
    "legacy.view": "View Legacy Proofs",
    "legacy.create": "Create Legacy Proofs",
    "legacy.review": "Review/Approve Legacy Proofs",
    "knowledge_base.view": "View Knowledge Base",
    "knowledge_base.edit": "Edit Knowledge Base",
    "training.view": "View Training",
    "training.edit": "Edit Training",
    "training.admin": "Administer Training",
    "settings.view": "View Settings",
    "settings.users.manage": "Manage Users",
    "settings.billing.view": "View Billing",
    "settings.billing.edit": "Edit Billing",
    "settings.integrations.manage": "Manage Integrations",
    "settings.permissions.manage": "Manage Permissions",
    # Disinterment
    "disinterments.view": "View Disinterment Cases",
    "disinterments.manage": "Manage Disinterment Cases",
    "disinterments.schedule": "Schedule Disinterments",
    "disinterments.sign": "Sign Disinterment Documents",
    "disinterment_settings.manage": "Manage Disinterment Settings",
    "union_rotations.view": "View Union Rotation Lists",
    "union_rotations.manage": "Manage Union Rotation Lists",
    # Safety trainer
    "safety.trainer.view": "View Safety Programs",
    "safety.trainer.generate": "Generate Safety Programs",
    "safety.trainer.approve": "Approve Safety Programs",
}


# ── Default permissions for seeded system roles ──────────────────────────────

ADMIN_DEFAULT_PERMISSIONS: list[str] = []  # Wildcard — handled by permission_service.py

ACCOUNTANT_DEFAULT_PERMISSIONS = [
    "financials.view",
    "financials.invoices.view",
    "financials.invoices.create",
    "financials.invoices.edit",
    "financials.invoices.void",
    "financials.payments.view",
    "financials.payments.create",
    "financials.ar.view",
    "financials.ar.action",
    "financials.statements.view",
    "financials.statements.create",
    "financials.price_management.view",
    "financials.price_management.edit",
    "financials.ap.view",
    "financials.ap.action",
    "crm.view",
    "orders.view_from_invoice",
    "purchase_orders.view_from_ap",
    "reports.view",
    "invoice.approve",
    # Legacy keys kept for backward compat
    "dashboard.view",
    "products.view",
    "inventory.view",
    "audit.view",
    "company.view",
    "departments.view",
    "employees.view",
    "customers.view",
    "vendors.view",
    "ap.view",
    "ap.create_po",
    "ap.create_bill",
    "ap.approve_bill",
    "ap.record_payment",
    "ap.export",
    "ap.void",
    "ar.view",
    "ar.create_quote",
    "ar.create_order",
    "ar.update_order",
    "ar.create_invoice",
    "ar.record_payment",
    "ar.void",
]

# Backward compat alias
ACCOUNTING_DEFAULT_PERMISSIONS = ACCOUNTANT_DEFAULT_PERMISSIONS

OFFICE_STAFF_DEFAULT_PERMISSIONS = [
    "operations.view",
    "orders.view",
    "orders.create",
    "orders.edit",
    "order_station.view",
    "scheduling_board.view",
    "crm.view",
    "crm.companies.create",
    "crm.companies.edit",
    "crm.contacts.create",
    "crm.contacts.edit",
    "crm.call_log.view",
    "knowledge_base.view",
    "training.view",
    # Legacy keys kept for backward compat
    "dashboard.view",
    "customers.view",
    "customers.create",
    "customers.edit",
    "products.view",
    "ar.view",
    "ar.create_quote",
    "ar.create_order",
    "ar.update_order",
    "ar.create_invoice",
    "ar.record_payment",
    "delivery.view",
    "drivers.view",
    "routes.view",
    "safety.view",
    "announcements.view",
    "announcements.create",
    "legacy_studio.view",
    "legacy_studio.create",
    "legacy_studio.edit",
    "inventory.view",
    "equipment.view",
    "work_orders.view",
    "personalization.view",
    # Disinterment
    "disinterments.view",
    "disinterments.manage",
]

# Optional toggles for office_staff (off by default, can be granted per-user)
OFFICE_STAFF_OPTIONAL_TOGGLES = [
    "financials.view",
    "financials.ar.view",
    "financials.ar.action",
    "financials.invoices.view",
    "financials.invoices.create",
    "operations_board.view",
    "invoice.approve",
    "legacy.create",
    "legacy.review",
]

PRODUCTION_DEFAULT_PERMISSIONS = [
    "operations_board.view",
    "operations_board.edit",
    "scheduling_board.view",
    "production_hub.view",
    "production_hub.edit",
    "orders.view",
    "orders.edit_status",
    "crm.view",
    "knowledge_base.view",
    "training.view",
    # Legacy keys kept for backward compat
    "dashboard.view",
    "ar.view",
    "ar.update_order",
    "production_log.view",
    "production_log.create",
    "production_log.edit",
    "work_orders.view",
    "work_orders.create",
    "qc.view",
    "qc.create",
    "safety.view",
    "safety.create",
    "equipment.view",
    "inventory.view",
    "announcements.view",
    "personalization.view",
    # Disinterment
    "disinterments.view",
    "disinterments.manage",
    "disinterments.schedule",
    "union_rotations.view",
]

# Optional toggles for production (off by default)
PRODUCTION_OPTIONAL_TOGGLES = [
    "order_station.view",
]

# Dispatcher — Phase B Session 1. Scheduling-focused role for the
# Dispatch Monitor + Scheduling Focus workflow. Manages driver
# assignments, delivery schedules, and hole-dug status. Read access
# to orders and related customer/cemetery records; no financial
# permissions. Explicitly NOT admin.
DISPATCHER_DEFAULT_PERMISSIONS = [
    # Dashboard + core navigation
    "dashboard.view",
    # Delivery operations — primary role focus
    "delivery.view",
    "delivery.edit",
    "delivery.create",
    "delivery.dispatch",
    "delivery.track",
    "delivery.assign_driver",
    "delivery.finalize_schedule",
    "delivery.edit_hole_dug",
    # Routes + drivers — need to see + assign
    "routes.view",
    "routes.edit",
    "routes.dispatch",
    "drivers.view",
    "vehicles.view",
    # Orders — read access + scheduling-field edits only
    "orders.view",
    "orders.edit_scheduling_fields",
    "orders.view_assigned",
    # Scheduling board + operations board for context
    "scheduling_board.view",
    "operations_board.view",
    # Customers + CRM read access for context
    "customers.view",
    "crm.view",
    # Legacy delivery-module keys kept for backward compat
    "ar.view",
    "ar.update_order",
]

DRIVER_DEFAULT_PERMISSIONS = [
    "driver.console.view",
    "orders.view_assigned",
    "orders.mark_delivered",
    # Legacy keys kept for backward compat
    "dashboard.view",
    "ar.view",
    "ar.update_order",
    "orders.view",
    "delivery.view",
    "delivery.update_status",
    "delivery.mark_delivered",
    "routes.view",
    "drivers.view",
    "safety.view",
]

EMPLOYEE_DEFAULT_PERMISSIONS = [
    "dashboard.view",
    "delivery.view",
    "drivers.view",
    "routes.view",
    "safety.view",
    "work_orders.view",
]

# Manager — everything except user/role deletion
MANAGER_DEFAULT_PERMISSIONS = [
    k for k in get_all_permission_keys()
    if k not in ("users.delete", "roles.delete")
]

LEGACY_DESIGNER_DEFAULT_PERMISSIONS = [
    "legacy.view",
    "legacy.create",
    "legacy.review",
    # Legacy keys kept for backward compat
    "dashboard.view",
    "legacy_studio.view",
    "legacy_studio.create",
    "legacy_studio.edit",
    "legacy_studio.approve",
    "legacy_studio.send",
    "ar.view",
    "customers.view",
    "delivery.view",
    "announcements.view",
    "personalization.view",
]

# ── Role slug → default permissions mapping ──────────────────────────────────

ROLE_DEFAULTS: dict[str, list[str]] = {
    "admin": ADMIN_DEFAULT_PERMISSIONS,
    "accountant": ACCOUNTANT_DEFAULT_PERMISSIONS,
    "office_staff": OFFICE_STAFF_DEFAULT_PERMISSIONS,
    "production": PRODUCTION_DEFAULT_PERMISSIONS,
    "dispatcher": DISPATCHER_DEFAULT_PERMISSIONS,
    "driver": DRIVER_DEFAULT_PERMISSIONS,
    "employee": EMPLOYEE_DEFAULT_PERMISSIONS,
    "manager": MANAGER_DEFAULT_PERMISSIONS,
    "legacy_designer": LEGACY_DESIGNER_DEFAULT_PERMISSIONS,
}
