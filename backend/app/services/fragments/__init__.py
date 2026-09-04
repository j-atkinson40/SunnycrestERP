"""Fragment contract — the substrate the note surface renders.

Per DECISIONS 2026-09-04. Public surface is deliberately narrow: declare types
in `platform_defaults` (or via `register_fragment` from a feature module), and
read them through `emit_for_user`.
"""

from app.services.fragments.emission import (  # noqa: F401
    EmittedFragment,
    FragmentEmissionError,
    audience_admits,
    emit_for_user,
)
from app.services.fragments.registry import (  # noqa: F401
    get_fragment,
    get_registry,
    register_fragment,
    reset_registry,
)
from app.services.fragments.types import (  # noqa: F401
    Audience,
    EndTransition,
    FragmentDeclaration,
    FragmentDeclarationError,
    FragmentInstance,
    FragmentKind,
    FragmentPayload,
    ReferencedItem,
    TargetSurface,
)
