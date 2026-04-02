"""
Permission registry — single source of truth for all available permissions.

Each module defines a list of actions. New modules are added here as they're built.
The flat permission key format is "module.action" (e.g., "users.view").
"""

PERMISSIONS: dict[str, list[str]] = {
    "audit": ["view"],
    "company": ["view", "edit"],
    "dashboard": ["view"],
    "employees": ["view", "edit", "view_notes"],
    "users": ["view", "create", "edit", "delete"],
    "roles": ["view", "create", "edit", "delete"],
    "departments": ["view", "create", "edit", "delete"],
    "products": ["view", "create", "edit", "delete"],
    "inventory": ["view", "create", "edit", "delete"],
    "equipment": ["view", "create", "edit", "delete"],
    "customers": ["view", "create", "edit", "delete"],
    "vendors": ["view", "create", "edit", "delete"],
    "ap": [
        "view",
        "create_po",
        "receive",
        "create_bill",
        "approve_bill",
        "record_payment",
        "export",
        "void",
    ],
    "ar": [
        "view",
        "create_quote",
        "create_order",
        "create_invoice",
        "record_payment",
        "void",
    ],
    "delivery": ["view", "create", "edit", "delete", "dispatch", "track"],
    "drivers": ["view", "create", "edit", "delete"],
    "vehicles": ["view", "create", "edit", "delete"],
    "routes": ["view", "create", "edit", "delete", "dispatch"],
    "carriers": ["view", "create", "edit", "delete"],
    "qc": ["view", "create", "edit", "delete"],
    "safety": ["view", "create", "edit", "delete"],
    "fh_cases": ["view", "create", "edit", "delete"],
    "fh_price_list": ["view", "create", "edit"],
    "fh_vault_orders": ["view", "create", "edit"],
    "fh_obituaries": ["view", "create", "edit"],
    "fh_invoices": ["view", "create", "edit", "void"],
    "fh_compliance": ["view"],
    "fh_portal": ["manage"],
    "production_log": ["view", "create", "edit", "delete"],
    "work_orders": ["view", "create", "edit", "delete"],
    "pour_events": ["view", "create", "edit"],
    "mix_designs": ["view", "create", "edit", "delete"],
    "cure_schedules": ["view", "create", "edit", "delete"],
    # ── New modules ──────────────────────────────────────────────────────────
    "legacy_studio": ["view", "create", "edit", "approve", "send", "delete"],
    "announcements": ["view", "create", "edit", "delete"],
    "personalization": ["view", "create", "complete", "approve"],
}


def get_all_permission_keys() -> list[str]:
    """Return flat list of all permission keys, e.g. ['dashboard.view', 'users.view', ...]"""
    return [
        f"{module}.{action}"
        for module, actions in PERMISSIONS.items()
        for action in actions
    ]


# ── Default permissions for seeded system roles ──────────────────────────────

EMPLOYEE_DEFAULT_PERMISSIONS = [
    "dashboard.view",
    "delivery.view",
    "drivers.view",
    "routes.view",
    "safety.view",
    "work_orders.view",
]

ACCOUNTING_DEFAULT_PERMISSIONS = [
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
    "ar.create_invoice",
    "ar.record_payment",
    "ar.void",
]

# Manager — everything except user/role deletion
MANAGER_DEFAULT_PERMISSIONS = [
    k for k in get_all_permission_keys()
    if k not in ("users.delete", "roles.delete")
]

OFFICE_STAFF_DEFAULT_PERMISSIONS = [
    "dashboard.view",
    "customers.view",
    "customers.create",
    "customers.edit",
    "products.view",
    "ar.view",
    "ar.create_quote",
    "ar.create_order",
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
]

DRIVER_DEFAULT_PERMISSIONS = [
    "dashboard.view",
    "delivery.view",
    "routes.view",
    "drivers.view",
    "safety.view",
]

PRODUCTION_DEFAULT_PERMISSIONS = [
    "dashboard.view",
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
]

LEGACY_DESIGNER_DEFAULT_PERMISSIONS = [
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
