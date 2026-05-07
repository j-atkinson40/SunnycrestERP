"""Focus compositions service package — canvas-based Focus layout
composition (May 2026).
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
    update_composition,
)
