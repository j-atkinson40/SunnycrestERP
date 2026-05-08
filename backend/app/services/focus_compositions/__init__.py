"""Focus compositions service package — canvas-based Focus layout
composition (May 2026).

R-5.0 (May 2026) extended to support `kind="edge_panel"` compositions
alongside the original `kind="focus"` accessory rails. Same service
surface; kind discriminator selects the composition family.
"""

from app.services.focus_compositions.composition_service import (  # noqa: F401
    CompositionError,
    CompositionNotFound,
    CompositionScopeMismatch,
    InvalidCompositionShape,
    LegacyPayloadRejected,
    create_composition,
    get_composition,
    list_compositions,
    reject_legacy_placements_payload,
    resolve_composition,
    resolve_edge_panel,
    update_composition,
)
