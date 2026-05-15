"""Focus Template Inheritance service package (sub-arc B-1).

Three-tier inheritance for Focus authoring substrate:

    focus_cores (Tier 1, platform-owned)
        ← focus_templates (Tier 2, platform_default | vertical_default)
            ← focus_compositions (Tier 3, per-tenant delta)

The Tier 3 layer stores DELTAS (hidden / additional / reorder /
geometry overrides) rather than full canvas state — patterned on
the edge-panel resolver precedent (see `composition_service.
_apply_placement_overrides`), distinct from workflow templates'
locked-to-fork replace semantics.

Public surface re-exports services + resolver + custom exceptions
for API + test consumption.

Sub-arc A shipped schema substrate (models + migration). Sub-arc B-1
(this package) ships service-layer + resolver + admin API + seed.
Sub-arc B-2 rewrites legacy consumers of the prior
focus_compositions shape and removes the import-compat shim.
"""

from app.services.focus_template_inheritance.focus_cores_service import (  # noqa: F401
    CoreNotFound,
    CoreSlugImmutable,
    FocusCoreError,
    InvalidCoreShape,
    count_templates_referencing,
    create_core,
    get_core_by_id,
    get_core_by_slug,
    list_cores,
    update_core,
)
from app.services.focus_template_inheritance.focus_templates_service import (  # noqa: F401
    FocusTemplateError,
    InvalidTemplateShape,
    TemplateNotFound,
    TemplateScopeMismatch,
    count_compositions_referencing,
    create_template,
    get_template_by_id,
    get_template_by_slug,
    list_templates,
    update_template,
)
from app.services.focus_template_inheritance.focus_compositions_service import (  # noqa: F401
    CompositionNotFound,
    FocusCompositionError,
    InvalidCompositionShape,
    create_or_update_composition,
    get_composition_by_tenant_template,
    reset_composition_to_default,
    reset_placement_to_default,
)
from app.services.focus_template_inheritance.resolver import (  # noqa: F401
    FocusTemplateNotFound,
    ResolvedFocus,
    resolve_focus,
)
from app.services.focus_template_inheritance.chrome_validation import (  # noqa: F401
    CHROME_FIELDS,
    VALID_PRESETS,
    InvalidChromeShape,
    validate_chrome_blob,
)
from app.services.focus_template_inheritance.resolver import (  # noqa: F401
    PRESETS,
    SUBSTRATE_PRESETS,
    TYPOGRAPHY_PRESETS,
    expand_preset,
    expand_substrate_preset,
    expand_typography_preset,
)
from app.services.focus_template_inheritance.substrate_validation import (  # noqa: F401
    SUBSTRATE_FIELDS,
    VALID_SUBSTRATE_PRESETS,
    InvalidSubstrateShape,
    validate_substrate_blob,
)
from app.services.focus_template_inheritance.typography_validation import (  # noqa: F401
    TYPOGRAPHY_FIELDS,
    VALID_TYPOGRAPHY_PRESETS,
    InvalidTypographyShape,
    validate_typography_blob,
)
