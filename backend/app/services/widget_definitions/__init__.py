"""Widget Builder substrate (WB-1+).

Service-layer package that owns composition-blob validation,
versioning, and CRUD orchestration for composed widget definitions.

WB-1 ships the validator only. The CRUD + auto-save hook ship in
WB-3+. Existing hand-coded widget definitions continue to live
under `app/services/widgets/` — this package is the additive
substrate for the composition path.
"""

from app.services.widget_definitions.validators import (
    CompositionBlobValidationError,
    validate_composition_blob,
    validate_widget_definition_write,
)
from app.services.widget_definitions.publish import (
    CannotPublishWithoutDraftError,
    WidgetDefinitionConflictError,
    WidgetDefinitionNotFoundError,
    create_widget_definition,
    publish_draft,
    save_draft,
    serialize_widget,
)

__all__ = [
    "CompositionBlobValidationError",
    "validate_composition_blob",
    "validate_widget_definition_write",
    "CannotPublishWithoutDraftError",
    "WidgetDefinitionConflictError",
    "WidgetDefinitionNotFoundError",
    "create_widget_definition",
    "publish_draft",
    "save_draft",
    "serialize_widget",
]
