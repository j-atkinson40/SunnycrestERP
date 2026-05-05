"""Component Configuration service — Phase 3 of the Admin Visual
Editor. Per-component prop override storage + inheritance walk.
"""

from app.services.component_config.config_service import (
    ComponentConfigError,
    ComponentConfigNotFound,
    ConfigScopeMismatch,
    InvalidConfigShape,
    PropValidationError,
    UnknownComponent,
    create_configuration,
    get_configuration,
    list_configurations,
    resolve_configuration,
    update_configuration,
    validate_overrides,
)
from app.services.component_config.registry_snapshot import (
    REGISTRY_SNAPSHOT,
    all_components,
    lookup_component,
)

__all__ = [
    "ComponentConfigError",
    "ComponentConfigNotFound",
    "ConfigScopeMismatch",
    "InvalidConfigShape",
    "PropValidationError",
    "UnknownComponent",
    "REGISTRY_SNAPSHOT",
    "all_components",
    "create_configuration",
    "get_configuration",
    "list_configurations",
    "lookup_component",
    "resolve_configuration",
    "update_configuration",
    "validate_overrides",
]
