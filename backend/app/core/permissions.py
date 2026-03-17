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
}


def get_all_permission_keys() -> list[str]:
    """Return flat list of all permission keys, e.g. ['dashboard.view', 'users.view', ...]"""
    return [
        f"{module}.{action}"
        for module, actions in PERMISSIONS.items()
        for action in actions
    ]


# Default permissions for seeded roles
EMPLOYEE_DEFAULT_PERMISSIONS = ["dashboard.view", "delivery.view", "drivers.view", "routes.view", "safety.view"]

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
