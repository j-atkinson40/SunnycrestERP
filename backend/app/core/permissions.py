"""
Permission registry — single source of truth for all available permissions.

Each module defines a list of actions. New modules are added here as they're built.
The flat permission key format is "module.action" (e.g., "users.view").
"""

PERMISSIONS: dict[str, list[str]] = {
    "audit": ["view"],
    "dashboard": ["view"],
    "users": ["view", "create", "edit", "delete"],
    "roles": ["view", "create", "edit", "delete"],
    # Future modules:
    # "products": ["view", "create", "edit", "delete"],
    # "inventory": ["view", "create", "edit", "delete"],
    # "sales": ["view", "create", "edit", "delete"],
    # "customers": ["view", "create", "edit", "delete"],
    # "driver_scheduling": ["view", "create", "edit", "delete"],
    # "reports": ["view", "export"],
}


def get_all_permission_keys() -> list[str]:
    """Return flat list of all permission keys, e.g. ['dashboard.view', 'users.view', ...]"""
    return [
        f"{module}.{action}"
        for module, actions in PERMISSIONS.items()
        for action in actions
    ]


# Default permissions for seeded roles
EMPLOYEE_DEFAULT_PERMISSIONS = ["dashboard.view"]
