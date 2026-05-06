"""Component class configuration package — class-scoped prop
override storage for the Admin Visual Editor's class layer
(May 2026).

Mirrors the shape of `app.services.component_config` but operates
on class-scoped configurations instead of per-component
configurations. The two layers compose: class defaults apply to
every component in the class, then per-component scopes override.

See app/models/component_class_configuration.py for the data
model and migration r83 for the schema.
"""

from app.services.component_class_config.class_config_service import (  # noqa: F401
    ClassConfigError,
    ClassConfigNotFound,
    InvalidClassConfigShape,
    UnknownClass,
    create_class_config,
    get_class_config,
    list_class_configs,
    resolve_class_config,
    update_class_config,
)
from app.services.component_class_config.class_registry_snapshot import (  # noqa: F401
    CLASS_REGISTRY_SNAPSHOT,
    all_classes,
    lookup_class,
)
