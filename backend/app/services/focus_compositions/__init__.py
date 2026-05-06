"""Focus compositions service package — canvas-based Focus layout
composition (May 2026).
"""

from app.services.focus_compositions.composition_service import (  # noqa: F401
    CompositionError,
    CompositionNotFound,
    CompositionScopeMismatch,
    InvalidCompositionShape,
    create_composition,
    get_composition,
    list_compositions,
    resolve_composition,
    update_composition,
)
