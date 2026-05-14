"""Edge Panel Inheritance service package (sub-arc B-1.5).

Two-tier inheritance for edge-panel authoring substrate:

    edge_panel_templates (Tier 2, platform_default | vertical_default)
        ← edge_panel_compositions (Tier 3, per-tenant lazy fork delta)
            ← User overrides (User.preferences, fourth resolver layer)

Edge-panels are pure composition; no Tier 1 core (distinct from Focus
Template Inheritance which carries a code-rendered core).

The Tier 3 layer stores DELTAS (recursive page-keyed outer + per-page
placement-keyed inner) rather than full canvas state — matching the
R-5.0 + R-5.1 User-preference vocabulary verbatim plus per-page
placement_geometry_overrides.

Public surface re-exports services + resolver + custom exceptions
for API + test consumption.
"""

from app.services.edge_panel_inheritance.edge_panel_templates_service import (  # noqa: F401
    EdgePanelTemplateError,
    EdgePanelTemplateNotFound,
    EdgePanelTemplateScopeMismatch,
    InvalidEdgePanelShape,
    count_compositions_referencing,
    create_template,
    get_template_by_id,
    get_template_by_key,
    list_templates,
    update_template,
)
from app.services.edge_panel_inheritance.edge_panel_compositions_service import (  # noqa: F401
    EdgePanelCompositionError,
    EdgePanelCompositionNotFound,
    get_composition_by_id,
    get_composition_by_tenant_template,
    reset_composition,
    reset_page,
    reset_placement,
    upsert_composition,
)
from app.services.edge_panel_inheritance.resolver import (  # noqa: F401
    EdgePanelTemplateResolveError,
    ResolvedEdgePanel,
    resolve_edge_panel,
)
